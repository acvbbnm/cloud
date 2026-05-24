"""경진대회 docx 3차 보강 — Part E·F 추가.

Part E — § 4.1~4.5 가상 시나리오 보강 (실제 합성 매칭률 추가)
Part F — § 6.1 핵심 클래스 일람 + § 6.2 8개 화면 일람 갱신
"""
from __future__ import annotations

import sys
from pathlib import Path
from docx import Document

sys.stdout.reconfigure(encoding="utf-8")

CONTEST_DOCX = Path(
    r"C:\Users\User\Desktop\세종대\2026-1학기\Capstone\경진대회 최종발표\최종보고서_로그아웃_AI_Sherpa.docx"
)


def _find_heading_index(doc, text_prefix: str) -> int:
    for i, p in enumerate(doc.paragraphs):
        st = (p.style.name or "")
        if st.startswith("Heading") and p.text.strip().startswith(text_prefix):
            return i
    return -1


def _insert_after(doc, anchor_para, style_name: str, text: str):
    new_p = anchor_para.insert_paragraph_before("")
    anchor_para._p.addnext(new_p._p)
    if text:
        new_p.add_run(text)
    try:
        new_p.style = doc.styles[style_name]
    except KeyError:
        pass
    return new_p


def insert_after_section(doc, section_prefix: str, blocks: list[tuple[str, str]]) -> bool:
    start = _find_heading_index(doc, section_prefix)
    if start < 0:
        return False
    start_style = doc.paragraphs[start].style.name or ""
    try:
        start_level = int(start_style.replace("Heading ", ""))
    except ValueError:
        return False
    end = len(doc.paragraphs) - 1
    for i in range(start + 1, len(doc.paragraphs)):
        st = doc.paragraphs[i].style.name or ""
        if st.startswith("Heading"):
            try:
                lvl = int(st.replace("Heading ", ""))
                if lvl <= start_level:
                    end = i - 1
                    break
            except ValueError:
                continue
    anchor = doc.paragraphs[end]
    current = anchor
    for style, text in blocks:
        current = _insert_after(doc, current, style, text)
    return True


def main() -> None:
    doc = Document(str(CONTEST_DOCX))
    print(f"열기: 단락 {len(doc.paragraphs)}")
    added = 0

    # Part E — 5 시나리오 매칭률 + 합성 사례 출처
    SCENARIO_RESULTS = {
        "4.1": (
            "S1: 자격증명 탈취 + MFA 적용 케이스",
            "본 시나리오의 합성 검증 데이터는 NCP Sysdig 2024 8 분 침투 사례 (13 events) "
            "와 NHN 사실 기반 시나리오 (8 events) 로 구성된다. NCP 시나리오에서 매처 매칭률 "
            "13/13 (100%), 정규화 13/13 (100%), ATT&CK 매핑 10/13 (77%) — T1078.004 / T1098 "
            "/ T1098.001 / T1136.003 / T1537 × 3 / T1531 등 7 종 기법으로 분포한다. NHN "
            "시나리오는 매처 매칭률 6/8 (75%) 이며 MFA 비활성화·비밀번호 변경·s3credential 발급 "
            "등 피싱 후 영속성 확보 패턴을 재현한다."
        ),
        "4.2": (
            "S2: 랜섬웨어 케이스",
            "본 시나리오의 합성 검증 데이터는 NCP / NHN 각 6 events 로, 외부 IP 로그인 → "
            "Object Storage 대량 다운로드 (이중 협박용 사전 유출) → 암호화 후 덮어쓰기 → "
            "백업 삭제 → 인스턴스 중지 / VPC 삭제 → 감사 로그 비활성화 순으로 진행된다. "
            "매처 매칭률 양 CSP 모두 6/6 (100%) 이며 MITRE T1486 Data Encrypted for Impact, "
            "T1485 Data Destruction, T1490 Inhibit System Recovery, T1531 Account Access "
            "Removal 등의 영향 단계 기법을 모두 커버한다."
        ),
        "4.3": (
            "S3: 설정 오류 노출 케이스",
            "본 시나리오의 합성 검증 데이터는 NCP 6 events / NHN 5 events 로, 정상 운영자가 "
            "Object Storage 버킷 ACL 또는 컨테이너 메타데이터를 공개로 설정하고 Security "
            "Group / NACL 규칙을 0.0.0.0/0 으로 무차별 허용한 후 익명 외부 접근이 실제 "
            "발생하는 흐름을 재현한다. 매처 매칭률 NCP 5/6 (83%) / NHN 4/5 (80%) 이며 MITRE "
            "T1580 Cloud Infrastructure Discovery, T1190 Exploit Public-Facing Application 으로 "
            "매핑된다."
        ),
        "4.4": (
            "S4: 피싱 → 자격증명 탈취 (복합)",
            "본 시나리오의 합성 검증 데이터는 NCP / NHN 각 5 events 로, 피싱 직후 1차 OTP "
            "실패 → 비국내 IP 로그인 성공 → 비밀번호 변경으로 정상 사용자 잠금 → AccessKey 또는 "
            "s3credential 발급 → 백도어 계정 생성 (system-bg-svc) 순으로 진행된다. 매처 매칭률 "
            "양 CSP 모두 5/5 (100%) 이며 PHISH_INITIAL_ACCESS → CREDENTIAL_THEFT → "
            "PRIVILEGE_ESCALATION 의 복합 사고유형 분기를 V-8 사후검증이 자동으로 보완한다."
        ),
        "4.5": (
            "S5: 내부자 위협 + 정기 감사",
            "본 시나리오의 합성 검증 데이터는 NCP / NHN 각 5 events 로, 사내 IP 의 비업무시간 "
            "(22:30) 로그인 → 자기 자신에 S3FullAccess 부여 → 민감 데이터 대량 다운로드 → "
            "개인 컨테이너로 이전 → 감사 로그 비활성화 또는 자격증명 삭제 순으로 진행된다. "
            "매처 매칭률 양 CSP 모두 5/5 (100%) 이며 사내 IP 와 비업무시간이라는 두 신호가 "
            "결합되어 INSIDER_THREAT 가설 점수를 단독 1 위로 끌어올린다."
        ),
    }

    print("\n[Part E] § 4.1~4.5 시나리오 합성 검증 결과 추가…")
    for prefix, (label, body) in SCENARIO_RESULTS.items():
        if insert_after_section(doc, prefix, [("Normal", body)]):
            added += 1
            print(f"  ✓ § {prefix} {label}")

    # Part F — § 6.2.1 8개 화면 일람에 dev3 안정화 결과 추가
    print("\n[Part F] § 6.2.1 8개 화면 일람 보강…")
    if insert_after_section(doc, "6.2.1", [
        ("Normal", (
            "각 화면은 React 18 + TypeScript 5 + Tailwind CSS 3 으로 구현되었으며, Zustand "
            "스토어 5 종 (useCaseStore / useTriageStore / useBoardStore / useSherpaStore / "
            "useToastStore) 으로 상태를 관리한다. 모든 API 호출은 axios + React Query (TanStack) "
            "로 처리되어 캐시·재시도·로딩 상태를 자동 관리한다. 페이지네이션은 신규 Pagination "
            "공통 컴포넌트로 V-2 raw_events 와 V-6 ATT&CK 표가 페이지 번호 직접 클릭으로 이동 "
            "가능하다. V-1 Step 3 의 결정 트리는 옵션 카드 하단에 다음 질문 프리뷰가 표시되어 "
            "수사관이 선택의 의미를 즉시 인식할 수 있도록 한다."
        )),
    ]):
        added += 1
        print("  ✓ § 6.2.1: 1 단락 추가")

    # § 8.5 보안 시험 보강 — 8.5 끝에 GitHub Actions 보안 영향 추가
    print("\n[추가] § 8.5 보안 시험 — CI 자동화 영향 추가…")
    if insert_after_section(doc, "8.5", [
        ("Normal", (
            "본 시스템은 GitHub Actions CI 와 로컬 pre-commit hook 으로 회귀 차단 안전망을 "
            "이중화하여, 매처 함수의 잘못된 변경, 시드 JSON 의 필수 필드 누락, ATT&CK 룰의 "
            "rule_id 중복 등 보안적 잠재 결함을 커밋 단계에서 자동 차단한다. 또한 pytest 모든 "
            "케이스가 DB 와 외부 서비스 의존성 없이 실행되므로 CI 환경에서 단 5 분 안에 전체 "
            "회귀 검증이 완료된다."
        )),
    ]):
        added += 1
        print("  ✓ § 8.5: 1 단락 추가")

    doc.save(str(CONTEST_DOCX))
    print(f"\n✅ 저장 완료: {added} 단락 추가, 현재 {len(doc.paragraphs)} 단락")


if __name__ == "__main__":
    main()
