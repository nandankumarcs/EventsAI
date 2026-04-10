import os
from unittest.mock import patch

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.agents.langchain_tools import TurnResolution
from apps.agents.schemas import ActiveFilters
from apps.agents.services import process_chat_turn
from apps.chats.models import ChatThread, ThreadFilter


def main() -> None:
    thread = ChatThread.objects.create(title="DebugMCP demo thread")
    ThreadFilter.objects.create(
        thread=thread,
        active_filters={
            "event_types": ["sports"],
            "cities": ["New Delhi"],
            "event_dates": ["2026-04-12"],
            "sport_types": ["Cricket"],
        },
    )

    with patch("apps.agents.services.resolve_turn_filters") as resolve_turn_filters_mock:
        resolve_turn_filters_mock.return_value = TurnResolution(
            updates=ActiveFilters(cities=["Mumbai"]),
            tool_trace=["resolve_location"],
        )

        payload = process_chat_turn(
            user_message="Actually Mumbai works better",
            thread_id=str(thread.id),
        )

    print(payload["active_filters"])


if __name__ == "__main__":
    main()
