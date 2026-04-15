from __future__ import annotations

from contextvars import ContextVar

from sqlalchemy.orm import Session


_session_ctx: ContextVar[Session | None] = ContextVar("sqlalchemy_session", default=None)


def set_session(session: Session) -> object:
    return _session_ctx.set(session)


def reset_session(token: object) -> None:
    _session_ctx.reset(token)


def get_session() -> Session:
    session = _session_ctx.get()
    if session is None:
        raise RuntimeError("SQLAlchemy session is not set")
    return session
