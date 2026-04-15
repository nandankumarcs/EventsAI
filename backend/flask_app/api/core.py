from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Blueprint, Flask, current_app, jsonify, request

from apps.core.ttl_cache import cache
from flask_app.db import check_database
from flask_app.settings import Settings


core_api = Blueprint("core_api", __name__)


@core_api.get("/api/health/")
def api_health_check():
    settings: Settings = current_app.config["SETTINGS"]
    database = {
        "configured": bool(settings.database_url),
        "engine": "sqlalchemy",
        "reachable": False,
    }

    db = current_app.config.get("DB")
    reachable, detail = check_database(db.engine) if db else (False, "Database is not configured")
    database["reachable"] = reachable
    if detail:
        database["detail"] = detail

    status = "ok" if reachable else "degraded"

    return jsonify(
        {
            "status": status,
            "service": "eventsai-backend",
            "timestamp": datetime.now(tz=ZoneInfo("Asia/Kolkata")).isoformat(),
            "database": database,
        }
    )


@core_api.post("/api/cache/reset/")
def api_cache_reset():
    before = cache.stats()
    cache.clear()
    after = cache.stats()
    return jsonify(
        {
            "status": "ok",
            "cache": "ttl_cache",
            "before": asdict(before),
            "after": asdict(after),
        }
    )


def init_app(app: Flask) -> None:
    settings: Settings = app.config["SETTINGS"]

    if settings.cors_allowed_origins:
        try:
            from flask_cors import CORS

            CORS(
                app,
                resources={r"/api/*": {"origins": settings.cors_allowed_origins}},
                supports_credentials=False,
            )
        except Exception:
            pass

    app.register_blueprint(core_api)
