from __future__ import annotations

from dataclasses import dataclass
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from flask import Flask, g

from apps.core import sqlalchemy as session_ctx

from flask_app.settings import Settings


@dataclass(frozen=True)
class Database:
    engine: Engine
    session_factory: sessionmaker[Session]


def create_database(settings: Settings) -> Database:
    if settings.database_url:
        engine = create_engine(settings.database_url, pool_pre_ping=True)
    else:
        sqlite_path = settings.base_dir / "db.sqlite3"
        engine = create_engine(f"sqlite:///{sqlite_path}", future=True)

    session_factory: sessionmaker[Session] = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return Database(engine=engine, session_factory=session_factory)


def init_app(app: Flask) -> None:
    settings: Settings = app.config["SETTINGS"]
    db = create_database(settings)
    app.config["DB"] = db

    @app.before_request
    def _open_session():
        session = db.session_factory()
        g.db_session = session
        g.db_session_token = session_ctx.set_session(session)

    @app.teardown_request
    def _close_session(exc: BaseException | None):
        session: Session | None = getattr(g, "db_session", None)
        if session is None:
            return
        try:
            if exc is None:
                session.commit()
            else:
                session.rollback()
        finally:
            token = getattr(g, "db_session_token", None)
            if token is not None:
                session_ctx.reset_session(token)
            session.close()


def get_session() -> Session:
    session: Session | None = getattr(g, "db_session", None)
    if session is None:
        raise RuntimeError("Database session is not initialized")
    return session


def session_scope() -> Generator[Session, None, None]:
    session = get_session()
    yield session


def check_database(engine: Engine) -> tuple[bool, str | None]:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:
        return False, str(exc)
