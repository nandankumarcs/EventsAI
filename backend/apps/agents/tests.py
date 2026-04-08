from unittest.mock import patch

from django.test import TestCase

from apps.agents.langchain_tools import TurnResolution
from apps.agents.schemas import ActiveFilters
from apps.agents.services import _derive_filters_to_clear, process_chat_turn
from apps.chats.models import ChatMessage, ChatThread, ThreadFilter


class AgentServiceTests(TestCase):
    @patch("apps.agents.services.resolve_turn_filters")
    def test_process_chat_turn_persists_thread_filters_and_messages(self, resolve_turn_filters_mock):
        resolve_turn_filters_mock.return_value = TurnResolution(
            updates=ActiveFilters(
                event_types=["sports"],
                cities=["New Delhi"],
                event_dates=["2026-04-12"],
            ),
            tool_trace=["resolve_event_type", "resolve_location", "resolve_temporal"],
        )

        payload = process_chat_turn(user_message="I want sports in Delhi this Sunday")

        self.assertEqual(ChatThread.objects.count(), 1)
        self.assertEqual(ChatMessage.objects.count(), 2)
        thread_filter = ThreadFilter.objects.get()
        self.assertEqual(
            thread_filter.active_filters,
            {
                "event_types": ["sports"],
                "cities": ["New Delhi"],
                "event_dates": ["2026-04-12"],
            },
        )
        self.assertEqual(payload["search_domains"], ["sports"])
        self.assertEqual(
            thread_filter.resolver_trace,
            ["resolve_event_type", "resolve_location", "resolve_temporal"],
        )

    @patch("apps.agents.services.resolve_turn_filters")
    def test_process_chat_turn_clears_conflicting_domain_filters(self, resolve_turn_filters_mock):
        thread = ChatThread.objects.create(title="Existing thread")
        ThreadFilter.objects.create(
            thread=thread,
            active_filters={
                "event_types": ["sports"],
                "cities": ["New Delhi"],
                "sport_types": ["Cricket"],
                "teams": ["Delhi Capitals"],
                "venue_names": ["Arun Jaitley Stadium"],
            },
        )
        resolve_turn_filters_mock.return_value = TurnResolution(
            updates=ActiveFilters(event_types=["movies"]),
            tool_trace=["resolve_event_type"],
        )

        process_chat_turn(user_message="Show movies instead", thread_id=str(thread.id))

        thread_filter = ThreadFilter.objects.get(thread=thread)
        self.assertEqual(
            thread_filter.active_filters,
            {
                "event_types": ["movies"],
                "cities": ["New Delhi"],
            },
        )

    @patch("apps.agents.services.resolve_turn_filters")
    def test_process_chat_turn_updates_existing_location_preference(self, resolve_turn_filters_mock):
        thread = ChatThread.objects.create(title="Existing thread")
        ThreadFilter.objects.create(
            thread=thread,
            active_filters={
                "event_types": ["sports"],
                "cities": ["New Delhi"],
                "event_dates": ["2026-04-12"],
                "sport_types": ["Cricket"],
            },
        )
        resolve_turn_filters_mock.return_value = TurnResolution(
            updates=ActiveFilters(cities=["Mumbai"]),
            tool_trace=["resolve_location"],
        )

        payload = process_chat_turn(user_message="Actually Mumbai works better", thread_id=str(thread.id))

        self.assertEqual(payload["active_filters"]["cities"], ["Mumbai"])
        self.assertEqual(payload["active_filters"]["sport_types"], ["Cricket"])


class AgentLogicTests(TestCase):
    def test_derive_filters_to_clear_on_domain_switch_clears_domain_specific_and_shared_keys(self):
        current_filters = ActiveFilters(
            event_types=["sports"],
            cities=["New Delhi"],
            venue_names=["Arun Jaitley Stadium"],
            sport_types=["Cricket"],
            teams=["Delhi Capitals"],
        )
        updates = ActiveFilters(event_types=["movies"])

        result = _derive_filters_to_clear(current_filters=current_filters, updates=updates)

        self.assertIn("sport_types", result)
        self.assertIn("teams", result)
        self.assertIn("venue_names", result)


class AgentViewTests(TestCase):
    @patch("apps.agents.views.process_chat_turn")
    def test_chat_turn_endpoint_returns_payload(self, process_chat_turn_mock):
        process_chat_turn_mock.return_value = {"thread": {"id": "abc"}, "assistant_message": {"content": "done"}}

        response = self.client.post(
            "/api/agents/chat/",
            data='{"message":"I want sports in Delhi"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["thread"]["id"], "abc")
