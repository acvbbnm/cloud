"""Layer 3 — ChatSession.

세션별 대화 히스토리 관리. 우선 인메모리 dict 로 저장 (서버 재시작 시 초기화).
DB 영속화는 별도 테이블 추가 필요 (현재 설계서 5.2 절에 chat_sessions 테이블 없음).
"""
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Message:
    role: str  # 'user' / 'assistant'
    content: str


@dataclass
class Session:
    session_id: str
    case_id: Optional[str]
    messages: list[Message] = field(default_factory=list)


_SESSIONS: dict[str, Session] = {}


class ChatSession:
    """인메모리 채팅 세션 저장소."""

    @classmethod
    def get_or_create(cls, session_id: Optional[str], case_id: Optional[str]) -> Session:
        """sessionId 가 있으면 조회, 없으면 신규 생성."""
        if session_id and session_id in _SESSIONS:
            return _SESSIONS[session_id]
        sid = session_id or f"sess-{uuid.uuid4().hex[:12]}"
        sess = Session(session_id=sid, case_id=case_id)
        _SESSIONS[sid] = sess
        return sess

    @classmethod
    def append(cls, session_id: str, role: str, content: str) -> None:
        sess = _SESSIONS.get(session_id)
        if sess is None:
            return
        sess.messages.append(Message(role=role, content=content))

    @classmethod
    def history(cls, session_id: str) -> list[Message]:
        sess = _SESSIONS.get(session_id)
        return list(sess.messages) if sess else []
