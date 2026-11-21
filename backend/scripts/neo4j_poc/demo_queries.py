"""Neo4j PoC 시연 쿼리 모음 — 5/29 보고서·시연 영상 캡처 후보.

각 쿼리는 (1) Cypher 본문 (2) 짧은 설명 (3) 콘솔 출력으로 결과 요약 을 출력한다.
시연 영상에서는 Neo4j Browser (http://localhost:7474) 에 같은 쿼리를 붙여 넣어
그래프 시각화를 같이 보여줄 것을 가정.

실행 전 import_clue_graph.py 가 한 번은 돌았어야 함.
"""
from __future__ import annotations

from neo4j import GraphDatabase

NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "sherpa-poc-2026")


DEMOS = [
    {
        "title": "Q1. 단서 카테고리 → 다음 단서 카테고리 (LEADS_TO 그래프)",
        "purpose": "Discord 김병우 비전 — '단서 후보를 단서비 기반으로 룰을 타고 다음 단서가 후로되는 방식'",
        "cypher": """
            MATCH (a:ClueCategory)-[:PIVOT_TO]->(h:NextClueHint)-[:LEADS_TO]->(b:ClueCategory)
            RETURN a.name AS from_category, h.priority AS priority, b.name AS to_category
            ORDER BY from_category, priority
        """,
    },
    {
        "title": "Q2. 각 단서가 부풀리는 사고유형 (BOOSTS Top 10)",
        "purpose": "단서 1개 → 사고유형 가중치 큰 순. Bayesian posterior 갱신의 직관적 시각화.",
        "cypher": """
            MATCH (cc:ClueCategory)-[:PIVOT_TO]->(h:NextClueHint)-[r:BOOSTS]->(it:IncidentType)
            RETURN cc.name AS category, h.priority AS priority,
                   it.name AS hypothesis, r.weight AS weight
            ORDER BY weight DESC, category, priority
            LIMIT 10
        """,
    },
    {
        "title": "Q3. 8 사고유형별 가중치 합계 (어떤 가설이 단서 풀에서 가장 많이 boost 되나)",
        "purpose": "가설별 단서 신호 강도. 사고유형 prior 가 uniform 1/8 이지만 단서 풀이 어느 가설로 기울지 본다.",
        "cypher": """
            MATCH (h:NextClueHint)-[r:BOOSTS]->(it:IncidentType)
            RETURN it.name AS hypothesis,
                   count(r) AS boost_count,
                   sum(r.weight) AS total_weight
            ORDER BY total_weight DESC
        """,
    },
    {
        "title": "Q4. ATT&CK 기법 Top 5 — 가장 많은 단서가 매핑된 기법",
        "purpose": "어떤 MITRE 기법이 단서 풀에서 가장 자주 가리키는지. 시연 영상 학술 정합성 강조.",
        "cypher": """
            MATCH (c:Clue)-[:MAPS_TO]->(t:Technique)
            RETURN t.tid AS technique, count(c) AS clue_count
            ORDER BY clue_count DESC
            LIMIT 5
        """,
    },
    {
        "title": "Q5. 특정 단서 (Q2A:object_storage_burst) 의 ATT&CK 다중 경로",
        "purpose": "데이터 유출형 단서 1건이 매핑되는 모든 기법 — Noisy-OR 의 자연 표현.",
        "cypher": """
            MATCH (c:Clue {clue_key: 'Q2A:object_storage_burst'})-[r:MAPS_TO]->(t:Technique)
            RETURN c.clue_key AS clue, collect(t.tid) AS techniques, r.confidence AS confidence
        """,
    },
    {
        "title": "Q6. 2-홉 단서 전이 (LEADS_TO 체인) — Detective Profile Guidance 직관",
        "purpose": "IP_ADDRESS → ACCOUNT → ... 같은 카테고리 단서 체인. AWS Detective 사용자 워크플로 시각화.",
        "cypher": """
            MATCH path = (a:ClueCategory)-[:PIVOT_TO]->()-[:LEADS_TO]->(b:ClueCategory)
                                        -[:PIVOT_TO]->()-[:LEADS_TO]->(c:ClueCategory)
            WHERE a <> b AND b <> c
            RETURN a.name AS step1, b.name AS step2, c.name AS step3
            LIMIT 8
        """,
    },
    {
        "title": "Q7. 단서·기법·가설 종합 — 한 단서가 어떤 기법 + 어떤 가설로 이어지나",
        "purpose": "Evidence Tree 종합 시각화. 단일 단서에서 가설·기법으로 양방향 그래프 만들기.",
        "cypher": """
            MATCH (c:Clue)-[:OF_CATEGORY]->(cc:ClueCategory)-[:PIVOT_TO]->(h)-[r:BOOSTS]->(it)
            MATCH (c)-[:MAPS_TO]->(t:Technique)
            WHERE cc.name = 'ACCOUNT'
            RETURN c.clue_key AS clue,
                   collect(DISTINCT it.name) AS boosted_hypotheses,
                   collect(DISTINCT t.tid)  AS mapped_techniques
            LIMIT 5
        """,
    },
]


def fmt_row(row: dict, widths: dict) -> str:
    return "  " + "  ".join(f"{str(row.get(k, '')):{w}s}" for k, w in widths.items())


def run_demo(session, idx: int, demo: dict) -> None:
    print(f"\n{'═'*78}")
    print(f"[{idx}] {demo['title']}")
    print(f"    ▷ {demo['purpose']}")
    print(f"{'─'*78}")
    result = list(session.run(demo["cypher"]))
    if not result:
        print("    (no rows)")
        return
    keys = result[0].keys()
    widths = {k: max(len(k), max(len(str(r[k])) for r in result)) for k in keys}
    # header
    print(fmt_row({k: k for k in keys}, widths))
    print("  " + "  ".join("─" * w for w in widths.values()))
    for r in result:
        print(fmt_row(dict(r), widths))
    print(f"    ({len(result)} rows)")


def main() -> None:
    drv = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
    try:
        with drv.session() as s:
            for i, demo in enumerate(DEMOS, 1):
                run_demo(s, i, demo)
    finally:
        drv.close()
    print(f"\n{'═'*78}")
    print("DONE — Neo4j Browser http://localhost:7474 (neo4j / sherpa-poc-2026)")
    print("       위 Cypher 들 그대로 복사해서 그래프 시각화 확인 가능.")


if __name__ == "__main__":
    main()
