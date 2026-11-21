"""Neo4j PoC — Evidence Tree 단서 그래프 적재.

목적
----
김병우 (Discord 2026-05-26) 제안 — paradigm doc §17.E 의 Neo4j 거부 결정 재검토.
단서→단서 전이 + 사고유형 가설 가중치 + ATT&CK 기법 매핑을 Neo4j 그래프로 적재해서
시연 영상의 "단서 시각화" 임팩트가 정량 가능한지 본다.

데이터 소스 (KBW/backend/data/triage/)
--------------------------------------
- next_clue_graph.json : ClueCategory -[LEADS_TO]-> ClueCategory + hypothesis_boost
- clue_to_attack.json  : Clue -[MAPS_TO]-> Technique
- priors.json          : IncidentType (uniform 1/8)

그래프 스키마
-------------
노드:
  (:ClueCategory {name, observation})        -- 6 (IP_ADDRESS / ACCOUNT / ...)
  (:NextClueHint {priority, question, action, source})  -- next_clues 항목
  (:Clue {clue_key, category, confidence})    -- clue_to_attack 매핑 단서
  (:IncidentType {name, prior})               -- 8 가설
  (:Technique {tid})                          -- ATT&CK 기법

관계:
  (ClueCategory) -[:PIVOT_TO]-> (NextClueHint)
  (NextClueHint) -[:LEADS_TO]-> (ClueCategory)
  (NextClueHint) -[:BOOSTS {weight}]-> (IncidentType)
  (Clue) -[:OF_CATEGORY]-> (ClueCategory)
  (Clue) -[:MAPS_TO {confidence}]-> (Technique)

실행
----
    python KBW/backend/scripts/neo4j_poc/import_clue_graph.py

idempotent — MERGE 사용. 여러 번 돌려도 중복 없음.
"""
from __future__ import annotations

import json
from pathlib import Path

from neo4j import GraphDatabase

# ── 환경 ──────────────────────────────────────────────────────────
NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "sherpa-poc-2026")

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "triage"
NEXT_CLUE_PATH = DATA_DIR / "next_clue_graph.json"
CLUE_TO_ATTACK_PATH = DATA_DIR / "clue_to_attack.json"
PRIORS_PATH = DATA_DIR / "priors.json"


# ── 헬퍼 ──────────────────────────────────────────────────────────
def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def reset_graph(tx) -> None:
    """PoC 한정: 기존 데이터 전부 제거."""
    tx.run("MATCH (n) DETACH DELETE n")


def create_constraints(tx) -> None:
    """노드 라벨별 unique 제약 — MERGE 최적화."""
    for label, key in [
        ("ClueCategory", "name"),
        ("NextClueHint", "hint_id"),
        ("Clue", "clue_key"),
        ("IncidentType", "name"),
        ("Technique", "tid"),
    ]:
        tx.run(
            f"CREATE CONSTRAINT {label.lower()}_{key} IF NOT EXISTS "
            f"FOR (n:{label}) REQUIRE n.{key} IS UNIQUE"
        )


# ── import 본체 ──────────────────────────────────────────────────
def import_incident_types(tx, priors: dict) -> int:
    cnt = 0
    for name, p in priors["priors"].items():
        tx.run(
            "MERGE (it:IncidentType {name: $name}) "
            "SET it.prior = $prior",
            name=name,
            prior=p,
        )
        cnt += 1
    return cnt


def import_next_clue_graph(tx, ncg: dict) -> dict:
    """6 pivot × n next_clues 를 노드·엣지로 변환.

    각 next_clue 는 NextClueHint 노드로 만들어서 priority/question/action 보존.
    """
    stats = {"categories": 0, "hints": 0, "leads_to": 0, "boosts": 0}
    for pivot in ncg["pivots"]:
        cat = pivot["clue_type"]
        obs = pivot["observation"]
        tx.run(
            "MERGE (c:ClueCategory {name: $name}) SET c.observation = $obs",
            name=cat,
            obs=obs,
        )
        stats["categories"] += 1

        for nc in pivot["next_clues"]:
            hint_id = f"{cat}#p{nc['priority']}"
            tx.run(
                "MERGE (h:NextClueHint {hint_id: $hint_id}) "
                "SET h.priority=$p, h.question=$q, h.action=$a, h.source=$s",
                hint_id=hint_id,
                p=nc["priority"],
                q=nc["question"],
                a=nc["action"],
                s=nc.get("source", ""),
            )
            stats["hints"] += 1
            tx.run(
                "MATCH (c:ClueCategory {name: $cat}), (h:NextClueHint {hint_id: $hint_id}) "
                "MERGE (c)-[:PIVOT_TO]->(h)",
                cat=cat,
                hint_id=hint_id,
            )

            # LEADS_TO 다음 카테고리 (있을 때만)
            target = nc.get("hint_clue_type")
            if target:
                tx.run(
                    "MERGE (tc:ClueCategory {name: $name})",
                    name=target,
                )
                tx.run(
                    "MATCH (h:NextClueHint {hint_id: $hint_id}), (tc:ClueCategory {name: $name}) "
                    "MERGE (h)-[:LEADS_TO]->(tc)",
                    hint_id=hint_id,
                    name=target,
                )
                stats["leads_to"] += 1

            # BOOSTS 사고유형 가중치
            for it, w in (nc.get("hypothesis_boost") or {}).items():
                tx.run(
                    "MERGE (it:IncidentType {name: $name})",
                    name=it,
                )
                tx.run(
                    "MATCH (h:NextClueHint {hint_id: $hint_id}), (it:IncidentType {name: $name}) "
                    "MERGE (h)-[r:BOOSTS]->(it) SET r.weight=$w",
                    hint_id=hint_id,
                    name=it,
                    w=w,
                )
                stats["boosts"] += 1
    return stats


def import_clue_to_attack(tx, cta: dict) -> dict:
    """143 단서 → 45 ATT&CK 기법. category 추출 = clue_key 의 ':' 앞부분."""
    stats = {"clues": 0, "techniques": 0, "maps_to": 0, "of_category": 0}
    seen_t = set()
    for clue_key, m in cta["mappings"].items():
        category = clue_key.split(":", 1)[0] if ":" in clue_key else "UNKNOWN"
        tx.run(
            "MERGE (c:Clue {clue_key: $k}) "
            "SET c.category=$cat, c.confidence=$conf",
            k=clue_key,
            cat=category,
            conf=m.get("confidence", "n/a"),
        )
        stats["clues"] += 1

        # category 노드 (next_clue_graph 와 겹치면 MERGE 가 합쳐줌)
        tx.run("MERGE (cc:ClueCategory {name: $name})", name=category)
        tx.run(
            "MATCH (c:Clue {clue_key: $k}), (cc:ClueCategory {name: $name}) "
            "MERGE (c)-[:OF_CATEGORY]->(cc)",
            k=clue_key,
            name=category,
        )
        stats["of_category"] += 1

        for tid in (m.get("techniques") or []):
            if tid not in seen_t:
                tx.run("MERGE (t:Technique {tid: $tid})", tid=tid)
                seen_t.add(tid)
                stats["techniques"] += 1
            tx.run(
                "MATCH (c:Clue {clue_key: $k}), (t:Technique {tid: $tid}) "
                "MERGE (c)-[r:MAPS_TO]->(t) SET r.confidence=$conf, r.source=$src",
                k=clue_key,
                tid=tid,
                conf=m.get("confidence", "unknown"),
                src=m.get("source", ""),
            )
            stats["maps_to"] += 1
    return stats


# ── 메인 ──────────────────────────────────────────────────────────
def main() -> None:
    ncg = load_json(NEXT_CLUE_PATH)
    cta = load_json(CLUE_TO_ATTACK_PATH)
    priors = load_json(PRIORS_PATH)

    drv = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
    try:
        with drv.session() as s:
            print("[1/4] reset graph (DETACH DELETE all)")
            s.execute_write(reset_graph)

            print("[2/4] create constraints")
            s.execute_write(create_constraints)

            print("[3/4] import IncidentType priors")
            it_cnt = s.execute_write(import_incident_types, priors)
            print(f"      IncidentType nodes: {it_cnt}")

            print("[4/4] import next_clue_graph (pivots / hints / boosts)")
            ncg_stats = s.execute_write(import_next_clue_graph, ncg)
            print(f"      stats: {ncg_stats}")

            print("[5/5] import clue_to_attack (clues / techniques)")
            cta_stats = s.execute_write(import_clue_to_attack, cta)
            print(f"      stats: {cta_stats}")

            # 최종 카운트
            print("\n=== final node counts ===")
            for label in ["ClueCategory", "NextClueHint", "Clue", "IncidentType", "Technique"]:
                row = s.run(f"MATCH (n:{label}) RETURN count(n) AS c").single()
                print(f"  {label:14s} = {row['c']}")

            print("\n=== final relationship counts ===")
            for rel in ["PIVOT_TO", "LEADS_TO", "BOOSTS", "OF_CATEGORY", "MAPS_TO"]:
                row = s.run(f"MATCH ()-[r:{rel}]->() RETURN count(r) AS c").single()
                print(f"  {rel:14s} = {row['c']}")
    finally:
        drv.close()


if __name__ == "__main__":
    main()
