from __future__ import annotations

import json

from flask import Blueprint, jsonify, request

from apps.agents.services import ChatTurnError, process_chat_turn

agents_api = Blueprint("agents_api", __name__, url_prefix="/api/agents")


@agents_api.route("/chat/", methods=["POST"])
def chat_turn_view():
    try:
        payload = json.loads((request.data or b"").decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return jsonify({"error": f"Invalid chat payload: {exc}"}), 400

    message = (payload.get("message") or "").strip()
    thread_id = payload.get("thread_id")

    if not message:
        return jsonify({"error": "message is required"}), 400

    try:
        result = process_chat_turn(user_message=message, thread_id=thread_id)
    except ChatTurnError as exc:
        return jsonify({"error": str(exc)}), exc.status_code

    return jsonify(result)
