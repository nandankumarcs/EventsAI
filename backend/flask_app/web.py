from __future__ import annotations

from pathlib import Path

from flask import Flask, Response, current_app, send_from_directory

from flask_app.settings import Settings


def register_web_routes(app: Flask) -> None:
    @app.get("/health/")
    def health_check() -> Response:
        return Response("OK", content_type="text/plain")

    @app.get("/")
    @app.get("/<path:requested_path>")
    def serve_react(requested_path: str | None = None):
        settings: Settings = current_app.config["SETTINGS"]
        path = requested_path or ""

        if "." in path:
            candidate = Path(settings.frontend_dir) / path
            if candidate.exists() and candidate.is_file():
                return send_from_directory(settings.frontend_dir, path)
            return Response(status=404)

        return send_from_directory(settings.frontend_dir, "index.html")
