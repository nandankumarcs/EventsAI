from __future__ import annotations

from dotenv import load_dotenv

# Load .env file before creating app
load_dotenv()

from flask_app import create_app

app = create_app()
