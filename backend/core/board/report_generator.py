"""Layer 4 — ReportGenerator.

설계서 5.4.6절 + UC-08. case 데이터를 모아 KISA 양식 보고서 초안을 생성하고
파일시스템에 영속화한다.

영속화 위치: config.REPORTS_DIR/{case_id}.json (gitignore 됨)
DOCX 산출물: config.EXPORTS_DIR/{case_id}.docx (gitignore 됨)
PDF 산출물:  config.EXPORTS_DIR/{case_id}.pdf  (gitignore 됨, Phase 2.1)

응답 형식: frontend types/index.ts `ReportResponse` 와 일치.
  { caseId, sections: ReportSections, status, created_at }
"""
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from docx import Document
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from sqlalchemy import select
from sqlalchemy.orm import Session

from config import settings
from db.models import (
    AttackEventModel,
    ChainEdgeModel,
    ChainNodeModel,
    CollectionTargetModel,
    GapResultModel,
    IncidentCaseModel,
    OCSFEventModel,
    RawEventModel,
)

logger = logging.getLogger(__name__)

# 한글 폰트 후보 — Windows·macOS·Linux 순회. 폐쇄망 가정 (SNF-01).
_KOREAN_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\malgun.ttf",       # Windows 기본 (맑은 고딕)
    r"C:\Windows\Fonts\NanumGothic.ttf",  # Windows 추가 설치 시
    "/System/Library/Fonts/Supplemental/AppleSDGothicNeo.ttc",  # macOS
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",          # Linux
]
_PDF_FONT_NAME = "AISherpaKR"
_pdf_font_registered = False


def _ensure_pdf_korean_font() -> Optional[str]:
    """PDF 한글 폰트 1회 등록. 첫 호출에서만 시스템 폰트 탐색."""
    global _pdf_font_registered
    if _pdf_font_registered:
        return _PDF_FONT_NAME
    for path in _KOREAN_FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(_PDF_FONT_NAME, path))
                _pdf_font_registered = True
                logger.info("PDF 한글 폰트 등록: %s", path)
                return _PDF_FONT_NAME
            except Exception as exc:  # pragma: no cover
                logger.warning("폰트 등록 실패 (%s): %s", path, exc)
                continue
    logger.warning("한글 폰트 없음 — PDF 한글 깨질 수 있음")
    return None


# 8 섹션 키 (frontend ReportSections 와 1:1 일치)
SECTION_KEYS = [
    "overview",
    "timeline",
    "impact",
    "attack_analysis",
    "response",
    "recommendation",
    "evidence",
    "comments",
]

SECTION_TITLES_KO = {
    "overview": "1. 사고 개요",
    "timeline": "2. 타임라인",
    "impact": "3. 영향 분석",
    "attack_analysis": "4. ATT&CK 분석 결과",
    "response": "5. 대응 조치",
    "recommendation": "6. 권고 사항",
    "evidence": "7. 증거 목록",
    "comments": "8. 수사관 코멘트",
}


class ReportGenerator:
    """KISA 양식 보고서 초안 생성·영속화·DOCX 내보내기."""

    # ── 파일 경로 헬퍼 ───────────────────────────────────
    @staticmethod
    def _json_path(case_id: str) -> Path:
        return settings.REPORTS_DIR / f"{case_id}.json"

    @staticmethod
    def _docx_path(case_id: str) -> Path:
        return settings.EXPORTS_DIR / f"{case_id}.docx"

    # ── 영속화 ─────────────────────────────────────────
    @classmethod
    def load(cls, case_id: str) -> Optional[dict]:
        path = cls._json_path(case_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    @classmethod
    def save(cls, case_id: str, report: dict) -> None:
        path = cls._json_path(case_id)
        path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ── 초안 생성 ───────────────────────────────────────
    @classmethod
    def generate_draft(cls, db: Session, case_id: str) -> Optional[dict]:
        """case 데이터를 모아 8 섹션 초안 자동 생성. case 미존재 시 None."""
        case = db.get(IncidentCaseModel, case_id)
        if case is None:
            return None

        # ── 보조 집계 데이터 수집 ──
        raw_count = db.execute(
            select(RawEventModel).where(RawEventModel.case_id == case_id)
        ).all()
        raw_n = len(raw_count)

        ocsf_rows = list(
            db.execute(
                select(OCSFEventModel)
                .join(RawEventModel, OCSFEventModel.event_id == RawEventModel.event_id)
                .where(RawEventModel.case_id == case_id)
                .order_by(OCSFEventModel.time)
            ).scalars()
        )

        attack_rows = list(
            db.execute(
                select(AttackEventModel, OCSFEventModel)
                .join(OCSFEventModel, AttackEventModel.ocsf_id == OCSFEventModel.ocsf_id)
                .join(RawEventModel, OCSFEventModel.event_id == RawEventModel.event_id)
                .where(RawEventModel.case_id == case_id)
                .order_by(AttackEventModel.mapped_at.desc())
            ).all()
        )

        targets = list(
            db.execute(
                select(CollectionTargetModel)
                .where(CollectionTargetModel.incident_type == case.incident_type)
                .where(CollectionTargetModel.csp.in_([case.csp, "all"]))
            ).scalars()
        )

        collected_target_ids = {
            ev.matched_target_id
            for ev in db.execute(
                select(RawEventModel).where(RawEventModel.case_id == case_id)
            ).scalars()
            if ev.matched_target_id
        }

        latest_gap = db.execute(
            select(GapResultModel)
            .where(GapResultModel.case_id == case_id)
            .order_by(GapResultModel.detected_at.desc())
            .limit(1)
        ).scalar_one_or_none()

        chain_nodes = list(
            db.execute(
                select(ChainNodeModel)
                .where(ChainNodeModel.case_id == case_id)
                .order_by(ChainNodeModel.created_at)
            ).scalars()
        )
        chain_edges = list(
            db.execute(
                select(ChainEdgeModel)
                .where(ChainEdgeModel.case_id == case_id)
                .order_by(ChainEdgeModel.created_at)
            ).scalars()
        )

        # ── 섹션 1: 개요 ──
        occurred = case.occurred_at.strftime("%Y-%m-%d %H:%M:%S") if case.occurred_at else "(미상)"
        overview = (
            f"사고 케이스 ID: {case.case_id}\n"
            f"사고 유형: {case.incident_type}\n"
            f"CSP: {case.csp}\n"
            f"심각도: {case.severity}\n"
            f"발생 시각: {occurred} (UTC)\n"
            f"수집 raw 이벤트: {raw_n}건\n"
        )
        if case.system_config:
            overview += f"시스템 구성: {json.dumps(case.system_config, ensure_ascii=False)}\n"

        # ── 섹션 2: 타임라인 (상위 20건) ──
        tl_lines = []
        for ev in ocsf_rows[:20]:
            ts = ev.time.strftime("%Y-%m-%d %H:%M:%S") if ev.time else "?"
            actor = ev.actor_user_name or "—"
            ip = ev.src_endpoint_ip or "—"
            tl_lines.append(f"  {ts} · {actor}@{ip} · {ev.activity_name}")
        timeline = (
            f"OCSF 정규화 이벤트 {len(ocsf_rows)}건 중 상위 20건 시간순:\n"
            + ("\n".join(tl_lines) if tl_lines else "  (정규화된 이벤트 없음)")
        )

        # ── 섹션 3: 영향 ──
        mapped_n = len(attack_rows)
        mapping_rate = round(mapped_n / len(ocsf_rows) * 100, 2) if ocsf_rows else 0
        impact = (
            f"수집된 원본 이벤트 {raw_n}건이 OCSF로 정규화되어 {len(ocsf_rows)}건 적재.\n"
            f"이 중 {mapped_n}건이 ATT&CK 매핑됨 (매핑률 {mapping_rate}%).\n"
            f"공격 체인 노드 {len(chain_nodes)}개 / 엣지 {len(chain_edges)}개 식별."
        )

        # ── 섹션 4: ATT&CK 분석 (risk_score 제거 — 산출 근거 부재) ──
        tech_counter: dict[str, dict] = {}
        for att, _ocsf in attack_rows:
            key = att.technique_id
            entry = tech_counter.setdefault(
                key,
                {"tactic": att.tactic, "count": 0},
            )
            entry["count"] += 1
        tech_lines = [
            f"  {tid} ({info['tactic']}) — 탐지 {info['count']}건"
            for tid, info in sorted(
                tech_counter.items(), key=lambda kv: kv[1]["count"], reverse=True
            )
        ]
        attack_analysis = (
            f"식별된 ATT&CK 기법 {len(tech_counter)}종:\n"
            + ("\n".join(tech_lines) if tech_lines else "  (매핑 결과 없음)")
        )

        # ── 섹션 5: 대응 조치 ──
        if latest_gap:
            response = (
                f"갭 판정: {latest_gap.gap_type}\n"
                f"요약: {latest_gap.note or '-'}\n"
                "수행한 조치:\n"
                "  · 로그 수집 카탈로그 매칭\n"
                "  · OCSF 정규화 및 ATT&CK 매핑\n"
                "  · 갭 분석 및 보드 노드 검토"
            )
        else:
            response = "갭 감지 미실행. 수행한 조치: 로그 수집 및 정규화."

        # ── 섹션 6: 권고 사항 ──
        if latest_gap and latest_gap.gap_type == "COLLECTION":
            missing = latest_gap.missing_required or []
            missing_repr = ", ".join(
                m.get("target_id", "?") for m in missing if isinstance(m, dict)
            ) or "(상세 미상)"
            recommendation = (
                f"필수 증거 미수집 항목 보강 필요: {missing_repr}\n"
                "Layer 0 사고 접수 화면으로 복귀하여 추가 로그 수집을 수행하십시오."
            )
        elif latest_gap and latest_gap.gap_type == "INTERPRETATION":
            recommendation = (
                "매핑되지 않은 이벤트 다수 — AI 셰르파 브리핑 또는 수사관 직접 판단 권고."
            )
        elif latest_gap and latest_gap.gap_type == "NONE":
            recommendation = "갭 없음 — 보고서 최종화 및 차기 모니터링 정책 수립 권고."
        else:
            recommendation = "갭 감지 후 결과에 따라 권고 사항 보강 필요."

        # ── 섹션 7: 증거 목록 ──
        # 2026-05-24 walkthrough: UNCLASSIFIED 케이스는 카탈로그가 비어 "(대상 카탈로그
        # 비어 있음)" placeholder 가 DOCX 보고서로 그대로 노출되는 문제 발견.
        # 보고서 외부 공유 시 부적절하므로 명시적 경고 문구로 교체.
        if not targets:
            if case.incident_type == "UNCLASSIFIED":
                evidence = (
                    "※ 사고 유형이 UNCLASSIFIED 상태로 수집 대상 카탈로그가 정의되지 않았습니다.\n"
                    "V-1 Discovery Loop(결정 트리)에서 사고 유형을 확정한 뒤 보고서를 재생성해 주세요."
                )
            else:
                evidence = (
                    f"※ 사고 유형 {case.incident_type} × CSP {case.csp} 의 수집 대상 카탈로그가 "
                    "본 시스템에 등록되어 있지 않습니다. 운영자에게 collection_targets 시드 보강을 요청해 주세요."
                )
        else:
            evid_lines = []
            for t in sorted(targets, key=lambda x: -x.priority):
                collected = "✓" if t.target_id in collected_target_ids else "✗"
                evid_lines.append(
                    f"  [{collected}] {t.target_id} · {t.log_type} ({t.evidence_role}, priority {t.priority})"
                )
            evidence = (
                f"사고 유형 {case.incident_type} × CSP {case.csp} 의 수집 대상 카탈로그:\n"
                + "\n".join(evid_lines)
            )

        # ── 섹션 8: 수사관 코멘트 (빈칸) ──
        comments = "(수사관이 직접 작성)"

        report = {
            "caseId": case_id,
            "sections": {
                "overview": overview,
                "timeline": timeline,
                "impact": impact,
                "attack_analysis": attack_analysis,
                "response": response,
                "recommendation": recommendation,
                "evidence": evidence,
                "comments": comments,
            },
            "status": "draft",
            "created_at": datetime.utcnow().isoformat(),
        }
        return report

    # ── 조회/갱신 통합 ──────────────────────────────────
    @classmethod
    def get_or_create(cls, db: Session, case_id: str) -> Optional[dict]:
        """저장된 보고서가 있으면 로드, 없으면 초안 생성 후 저장."""
        existing = cls.load(case_id)
        if existing is not None:
            return existing
        draft = cls.generate_draft(db, case_id)
        if draft is None:
            return None
        cls.save(case_id, draft)
        return draft

    @classmethod
    def update_sections(
        cls,
        case_id: str,
        section_updates: dict,
        status: Optional[str] = None,
    ) -> Optional[dict]:
        """일부 섹션 부분 갱신. case 미존재 또는 미생성 시 None."""
        existing = cls.load(case_id)
        if existing is None:
            return None
        for key, value in section_updates.items():
            if key in SECTION_KEYS and isinstance(value, str):
                existing["sections"][key] = value
        if status is not None:
            existing["status"] = status
        cls.save(case_id, existing)
        return existing

    # ── DOCX 내보내기 ──────────────────────────────────
    @classmethod
    def render_docx(cls, report: dict) -> Path:
        """보고서 dict → DOCX 파일 생성. 산출물 경로 반환."""
        doc = Document()
        case_id = report.get("caseId", "unknown")
        doc.add_heading(f"침해사고 분석 보고서", level=0)
        doc.add_paragraph(f"Case ID: {case_id}")
        doc.add_paragraph(f"생성 시각: {report.get('created_at', '')}")
        doc.add_paragraph(f"상태: {report.get('status', 'draft')}")
        doc.add_paragraph()

        sections = report.get("sections", {})
        for key in SECTION_KEYS:
            title = SECTION_TITLES_KO[key]
            doc.add_heading(title, level=1)
            text = sections.get(key, "")
            for line in text.split("\n"):
                doc.add_paragraph(line)

        out_path = cls._docx_path(case_id)
        doc.save(out_path)
        return out_path

    # ── PDF 내보내기 (Phase 2.1) ────────────────────────
    @classmethod
    def _pdf_path(cls, case_id: str) -> Path:
        return settings.EXPORTS_DIR / f"{case_id}.pdf"

    @classmethod
    def render_pdf(cls, report: dict) -> Path:
        """보고서 dict → PDF 파일 생성. reportlab + 한글 시스템 폰트 사용.

        오프라인 동작 (SNF-01): 시스템에 이미 설치된 폰트만 사용. 외부 다운로드 없음.
        DOCX 와 동일한 8 섹션 구조 + 헤더 메타.
        """
        case_id = report.get("caseId", "unknown")
        out_path = cls._pdf_path(case_id)

        font_name = _ensure_pdf_korean_font()
        # 한글 폰트 없으면 reportlab 기본(Helvetica) 사용 — 한글은 □ 로 표시되나
        # 영문/숫자는 정상. 폐쇄망 평가자 환경에 한글 폰트 없을 가능성 대비.

        # 스타일 정의
        base = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "TitleKR",
            parent=base["Title"],
            fontName=font_name or base["Title"].fontName,
            fontSize=18,
            leading=24,
            spaceAfter=12,
        )
        meta_style = ParagraphStyle(
            "MetaKR",
            parent=base["Normal"],
            fontName=font_name or base["Normal"].fontName,
            fontSize=9,
            textColor=(0.35, 0.35, 0.35),
            leading=14,
        )
        heading_style = ParagraphStyle(
            "HeadingKR",
            parent=base["Heading2"],
            fontName=font_name or base["Heading2"].fontName,
            fontSize=13,
            leading=18,
            spaceBefore=12,
            spaceAfter=6,
            textColor=(0.10, 0.30, 0.55),
        )
        body_style = ParagraphStyle(
            "BodyKR",
            parent=base["Normal"],
            fontName=font_name or base["Normal"].fontName,
            fontSize=10.5,
            leading=16,
        )

        doc = SimpleDocTemplate(
            str(out_path),
            pagesize=A4,
            leftMargin=20 * mm,
            rightMargin=20 * mm,
            topMargin=20 * mm,
            bottomMargin=20 * mm,
            title=f"침해사고 분석 보고서 {case_id}",
        )

        # XML 이스케이프 — reportlab Paragraph 는 mini-HTML 파서 사용
        def esc(s: str) -> str:
            return (
                str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            )

        story = []
        story.append(Paragraph("침해사고 분석 보고서", title_style))
        story.append(Paragraph(f"Case ID: {esc(case_id)}", meta_style))
        story.append(Paragraph(f"생성 시각: {esc(report.get('created_at', ''))}", meta_style))
        story.append(Paragraph(f"상태: {esc(report.get('status', 'draft'))}", meta_style))
        story.append(Spacer(1, 10 * mm))

        sections = report.get("sections", {})
        for key in SECTION_KEYS:
            story.append(Paragraph(esc(SECTION_TITLES_KO[key]), heading_style))
            text = sections.get(key, "") or ""
            # 줄 단위로 끊어 Paragraph 화 (긴 텍스트 자동 줄바꿈)
            for line in text.split("\n"):
                if line.strip():
                    story.append(Paragraph(esc(line), body_style))
                else:
                    story.append(Spacer(1, 4))

        doc.build(story)
        return out_path
