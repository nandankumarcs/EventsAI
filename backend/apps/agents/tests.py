from unittest.mock import patch

from django.test import TestCase

from apps.agents.langchain_tools import (
    ResolutionIssue,
    TurnResolution,
    invoke_temporal_resolver,
    resolve_turn_filters,
)
from apps.agents.schemas import FilterResolution
from apps.agents.schemas import ActiveFilters
from apps.agents.services import ChatTurnError, _derive_filters_to_clear, process_chat_turn
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

    @patch("apps.agents.services.resolve_turn_filters")
    def test_process_chat_turn_returns_no_match_reply_without_broad_fallback(self, resolve_turn_filters_mock):
        resolve_turn_filters_mock.return_value = TurnResolution(
            updates=ActiveFilters(event_types=["sports"], cities=["Mumbai"]),
            tool_trace=["resolve_event_type", "resolve_location", "resolve_sport_filters"],
            issues=[
                ResolutionIssue(
                    status="no_match",
                    trace_name="resolve_sport_filters",
                    filter_label="sports filters",
                    message="No matching sport filters were found in the available catalog.",
                    candidates=[],
                )
            ],
        )

        payload = process_chat_turn(user_message="Show me handball in Mumbai")

        self.assertEqual(payload["results_by_domain"], {})
        self.assertEqual(payload["search_domains"], [])
        self.assertTrue(payload["needs_clarification"])
        self.assertEqual(payload["active_filters"]["cities"], ["Mumbai"])
        self.assertEqual(payload["active_filters"]["event_types"], ["sports"])
        self.assertIn("No matching sport filters", payload["assistant_message"]["content"])

    @patch("apps.agents.services.resolve_turn_filters")
    def test_process_chat_turn_returns_ambiguity_reply_with_candidates(self, resolve_turn_filters_mock):
        resolve_turn_filters_mock.return_value = TurnResolution(
            updates=ActiveFilters(event_types=["sports"]),
            tool_trace=["resolve_event_type", "resolve_location"],
            issues=[
                ResolutionIssue(
                    status="ambiguous",
                    trace_name="resolve_location",
                    filter_label="location",
                    message="Multiple possible locations matched.",
                    candidates=["New Delhi", "Delhi NCR"],
                )
            ],
        )

        payload = process_chat_turn(user_message="Show me sports in Delhi")

        self.assertEqual(payload["results_by_domain"], {})
        self.assertTrue(payload["needs_clarification"])
        self.assertEqual(payload["clarification_question"], "Did you mean New Delhi, Delhi NCR?")
        self.assertIn("multiple possible matches", payload["assistant_message"]["content"].lower())

    @patch("apps.agents.services.resolve_turn_filters")
    def test_process_chat_turn_rejects_booked_threads(self, resolve_turn_filters_mock):
        thread = ChatThread.objects.create(
            title="Booked thread",
            status=ChatThread.Status.BOOKED,
        )

        with self.assertRaisesMessage(
            ChatTurnError,
            "This thread already has a confirmed booking. Start a new thread to plan another event.",
        ):
            process_chat_turn(user_message="Actually show me Mumbai", thread_id=str(thread.id))

        resolve_turn_filters_mock.assert_not_called()


class AgentLogicTests(TestCase):
    @patch("apps.agents.langchain_tools._invoke_filter_resolution_agent")
    @patch("apps.agents.langchain_tools._build_temporal_agent")
    def test_invoke_temporal_resolver_routes_through_temporal_agent_tools(
        self,
        build_temporal_agent_mock,
        invoke_filter_resolution_agent_mock,
    ):
        build_temporal_agent_mock.return_value = object()
        invoke_filter_resolution_agent_mock.return_value = FilterResolution(status="no_input")

        invoke_temporal_resolver("show me events next week", "2026-04-09")

        invoke_filter_resolution_agent_mock.assert_called_once()
        call_kwargs = invoke_filter_resolution_agent_mock.call_args.kwargs
        self.assertEqual(call_kwargs["trace_name"], "resolve_temporal")
        self.assertEqual(
            call_kwargs["allowed_fields"],
            {"event_dates", "date_from", "date_to", "start_time_from", "start_time_to"},
        )

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

    @patch("apps.agents.langchain_tools.invoke_sport_filter_resolver")
    @patch("apps.agents.langchain_tools.invoke_temporal_resolver")
    @patch("apps.agents.langchain_tools.invoke_location_resolver")
    @patch("apps.agents.langchain_tools.invoke_event_type_resolver")
    def test_resolve_turn_filters_prefers_same_domain_sport_correction_over_event_type_issue(
        self,
        event_type_resolver_mock,
        location_resolver_mock,
        temporal_resolver_mock,
        sport_filter_resolver_mock,
    ):
        event_type_resolver_mock.return_value = FilterResolution(
            status="no_match",
            message="Cricket is not available as an event type.",
        )
        location_resolver_mock.return_value = FilterResolution(status="no_input")
        temporal_resolver_mock.return_value = FilterResolution(status="no_input")
        sport_filter_resolver_mock.return_value = FilterResolution(
            status="resolved",
            message="Resolved sport type.",
            active_filters_partial=ActiveFilters(sport_types=["Cricket"]),
        )

        result = resolve_turn_filters(
            user_message="show cricket instead",
            current_filters=ActiveFilters(event_types=["sports"], sport_types=["Handball"]),
            reference_date="2026-04-09",
        )

        self.assertEqual(result.updates.sport_types, ["Cricket"])
        self.assertEqual(result.updates.event_types, [])
        self.assertEqual(result.issues, [])

    @patch("apps.agents.langchain_tools.invoke_movie_filter_resolver")
    @patch("apps.agents.langchain_tools.invoke_temporal_resolver")
    @patch("apps.agents.langchain_tools.invoke_location_resolver")
    @patch("apps.agents.langchain_tools.invoke_event_type_resolver")
    def test_resolve_turn_filters_allows_explicit_domain_switch_from_existing_thread(
        self,
        event_type_resolver_mock,
        location_resolver_mock,
        temporal_resolver_mock,
        movie_filter_resolver_mock,
    ):
        event_type_resolver_mock.return_value = FilterResolution(
            status="resolved",
            message="Resolved event type.",
            active_filters_partial=ActiveFilters(event_types=["movies"]),
        )
        location_resolver_mock.return_value = FilterResolution(status="no_input")
        temporal_resolver_mock.return_value = FilterResolution(status="no_input")
        movie_filter_resolver_mock.return_value = FilterResolution(
            status="resolved",
            message="Resolved movie filters.",
            active_filters_partial=ActiveFilters(formats=["IMAX 70mm"]),
        )

        result = resolve_turn_filters(
            user_message="show movies instead",
            current_filters=ActiveFilters(event_types=["sports"], cities=["Mumbai"]),
            reference_date="2026-04-09",
        )

        self.assertEqual(result.updates.event_types, ["movies"])
        self.assertEqual(result.updates.formats, ["IMAX 70mm"])


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

    @patch("apps.agents.views.process_chat_turn")
    def test_chat_turn_endpoint_returns_conflict_for_closed_thread(self, process_chat_turn_mock):
        process_chat_turn_mock.side_effect = ChatTurnError(
            "This thread already has a confirmed booking. Start a new thread to plan another event.",
            status_code=409,
        )

        response = self.client.post(
            "/api/agents/chat/",
            data='{"message":"Show me something else","thread_id":"abc"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("confirmed booking", response.json()["error"])
