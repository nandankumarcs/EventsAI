from __future__ import annotations

from flask import Flask

from flask_app.settings import Settings
from flask_app import db as flask_db
from flask_app.web import register_web_routes
from flask_app.api import core
from flask_app.api.chats import chats_api
from flask_app.api.agents import agents_api
from flask_app.api.bookings import bookings_api
from flask_app.api.events import events_api
from flask_app.api.flights import flights_api


def create_app() -> Flask:
    settings = Settings.from_env()

    app = Flask(
        __name__,
        static_folder=str(settings.frontend_assets_dir),
        static_url_path="/assets",
    )
    app.config["SETTINGS"] = settings

    flask_db.init_app(app)

    core.init_app(app)
    app.register_blueprint(chats_api)
    app.register_blueprint(events_api)
    app.register_blueprint(flights_api)
    app.register_blueprint(agents_api)
    app.register_blueprint(bookings_api)
    register_web_routes(app)

    return app
