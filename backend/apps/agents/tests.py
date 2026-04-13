from unittest.mock import patch
from datetime import datetime

from django.test import TestCase
from django.utils import timezone

from apps.agents.langchain_tools import (
    ResolutionIssue,
    TurnResolution,
    invoke_booking_agent,
    invoke_goal_state,
    invoke_temporal_resolver,
    resolve_turn_filters,
)
from apps.agents.schemas import ActiveFilters, BookingTurnResolution, CatalogInquiry, FilterResolution, GoalState, TurnPolicy
from apps.agents.services import ChatTurnError, _derive_filters_to_clear, _update_dynamic_thread_title, process_chat_turn
from apps.bookings.models import Booking
from apps.bookings.services import (
    attempt_thread_pending_booking_confirmation,
    mark_thread_pending_booking,
    save_thread_booking_user_info,
    select_thread_pending_booking,
)
from apps.chats.models import ChatMessage, ChatThread, ThreadFilter
from apps.events.models import SportEvent
from apps.events.services import SearchResult


class AgentServiceTests(TestCase):
    def setUp(self):
        super().setUp()
        self.turn_policy_patcher = patch(
            "apps.agents.services.invoke_turn_policy",
            return_value=TurnPolicy(intent="task_continue"),
        )
        self.turn_policy_mock = self.turn_policy_patcher.start()
        self.addCleanup(self.turn_policy_patcher.stop)
        self.goal_state_patcher = patch(
            "apps.agents.services.invoke_goal_state",
            return_value=GoalState(
                goal_type="search",
                goal_stage="browsing_results",
                goal_summary="Event planning",
                last_open_question="",
            ),
        )
        self.goal_state_mock = self.goal_state_patcher.start()
        self.addCleanup(self.goal_state_patcher.stop)

    @patch("apps.agents.services.invoke_booking_agent", return_value=BookingTurnResolution(action="none"))
    @patch("apps.agents.services.resolve_turn_filters")
    def test_process_chat_turn_persists_thread_filters_and_messages(
        self,
        resolve_turn_filters_mock,
        _invoke_booking_agent_mock,
    ):
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
        self.assertEqual(thread_filter.latest_result_context["search_domains"], ["sports"])
        self.assertEqual(thread_filter.latest_result_context["results"], [])
        self.assertEqual(thread_filter.pending_booking, {})
        thread = ChatThread.objects.get()
        self.assertEqual(thread.metadata["goal_state"]["goal_summary"], "Event planning")

    @patch("apps.agents.services.resolve_turn_filters")
    @patch("apps.agents.services.invoke_booking_agent")
    def test_process_chat_turn_short_circuits_for_pending_booking_selection(
        self,
        invoke_booking_agent_mock,
        resolve_turn_filters_mock,
    ):
        thread = ChatThread.objects.create(title="Existing thread")
        ThreadFilter.objects.create(
            thread=thread,
            active_filters={"event_types": ["sports"]},
            latest_result_context={
                "thread_id": str(thread.id),
                "search_domains": ["sports"],
                "results": [
                    {
                        "position": 1,
                        "domain": "sports",
                        "listing_code": "SPT-1",
                        "title": "Mumbai Match",
                        "city": "Mumbai",
                        "venue_name": "Wankhede Stadium",
                        "event_date": "2026-04-12",
                        "start_at": "2026-04-12T19:30:00+05:30",
                    }
                ],
            },
            pending_booking={
                "status": "pending_confirmation",
                "listing_code": "SPT-1",
                "event_snapshot": {"listing_code": "SPT-1", "title": "Mumbai Match"},
            },
        )
        invoke_booking_agent_mock.return_value = BookingTurnResolution(
            action="selection_pending",
            message="You want to book Mumbai Match. Should I confirm it?",
            listing_code="SPT-1",
        )

        payload = process_chat_turn(user_message="book the first one", thread_id=str(thread.id))

        resolve_turn_filters_mock.assert_not_called()
        self.assertEqual(payload["assistant_message"]["metadata"]["booking_action"], "selection_pending")
        self.assertEqual(payload["pending_booking"]["listing_code"], "SPT-1")
        self.assertEqual(payload["search_domains"], [])
        self.assertEqual(payload["results_by_domain"], {})
        self.assertEqual(payload["assistant_message"]["metadata"]["goal_state"]["goal_summary"], "Event planning")

    @patch("apps.agents.services.resolve_turn_filters")
    @patch("apps.agents.services.invoke_booking_agent")
    def test_process_chat_turn_short_circuits_for_booking_confirmation(
        self,
        invoke_booking_agent_mock,
        resolve_turn_filters_mock,
    ):
        thread = ChatThread.objects.create(title="Existing thread")
        ThreadFilter.objects.create(thread=thread, active_filters={"event_types": ["sports"]})
        invoke_booking_agent_mock.return_value = BookingTurnResolution(
            action="booking_confirmed",
            message="Booking confirmed for Mumbai Match. Your reference is ATD-BOOK1234.",
            listing_code="SPT-1",
            booking={"booking_reference": "ATD-BOOK1234"},
        )

        payload = process_chat_turn(user_message="yes", thread_id=str(thread.id))

        resolve_turn_filters_mock.assert_not_called()
        self.assertEqual(payload["assistant_message"]["metadata"]["booking_action"], "booking_confirmed")
        self.assertEqual(
            payload["assistant_message"]["metadata"]["booking"]["booking_reference"],
            "ATD-BOOK1234",
        )

    @patch("apps.agents.services.resolve_turn_filters")
    @patch("apps.agents.services.invoke_booking_agent")
    def test_process_chat_turn_short_circuits_for_missing_booking_user_info(
        self,
        invoke_booking_agent_mock,
        resolve_turn_filters_mock,
    ):
        thread = ChatThread.objects.create(title="Existing thread")
        ThreadFilter.objects.create(
            thread=thread,
            active_filters={"event_types": ["sports"]},
            pending_booking={
                "status": "awaiting_user_info",
                "listing_code": "SPT-1",
                "awaiting_field": "name",
                "customer_info": {"name": "", "email": "", "contact_number": ""},
                "event_snapshot": {"listing_code": "SPT-1", "title": "Mumbai Match"},
            },
        )
        invoke_booking_agent_mock.return_value = BookingTurnResolution(
            action="awaiting_user_info",
            message="Please share your full name to complete the booking.",
            listing_code="SPT-1",
            requested_field="name",
        )

        payload = process_chat_turn(user_message="yes", thread_id=str(thread.id))

        resolve_turn_filters_mock.assert_not_called()
        self.assertEqual(payload["assistant_message"]["metadata"]["booking_action"], "awaiting_user_info")
        self.assertEqual(payload["assistant_message"]["metadata"]["requested_field"], "name")

    @patch("apps.agents.services.resolve_turn_filters")
    @patch("apps.agents.services.invoke_booking_agent")
    def test_process_chat_turn_repairs_invalid_booking_transition_before_confirmation(
        self,
        invoke_booking_agent_mock,
        resolve_turn_filters_mock,
    ):
        thread = ChatThread.objects.create(title="Existing thread")
        thread_filter = ThreadFilter.objects.create(
            thread=thread,
            active_filters={"event_types": ["sports"]},
            latest_result_context={
                "thread_id": str(thread.id),
                "search_domains": ["sports"],
                "results": [
                    {
                        "position": 1,
                        "domain": "sports",
                        "listing_code": "SPT-1",
                        "title": "Mumbai Match",
                        "city": "Mumbai",
                        "venue_name": "Wankhede Stadium",
                        "event_date": "2026-04-12",
                        "start_at": "2026-04-12T19:30:00+05:30",
                    }
                ],
            },
        )
        def mutate_pending_booking(**_kwargs):
            thread_filter.pending_booking = {
                "status": "awaiting_user_info",
                "listing_code": "SPT-1",
                "awaiting_field": "name",
                "customer_info": {"name": "", "email": "", "contact_number": ""},
                "event_snapshot": {"listing_code": "SPT-1", "title": "Mumbai Match"},
            }
            thread_filter.save(update_fields=["pending_booking", "updated_at"])
            return BookingTurnResolution(
                action="awaiting_user_info",
                message="Please share your full name to complete the booking.",
                listing_code="SPT-1",
                requested_field="name",
                selected_event={"listing_code": "SPT-1", "title": "Mumbai Match"},
            )

        invoke_booking_agent_mock.side_effect = mutate_pending_booking

        payload = process_chat_turn(user_message="book the first one", thread_id=str(thread.id))

        resolve_turn_filters_mock.assert_not_called()
        self.assertEqual(payload["assistant_message"]["metadata"]["booking_action"], "awaiting_user_info")
        thread_filter.refresh_from_db()
        self.assertEqual(thread_filter.pending_booking["status"], "awaiting_user_info")
        self.assertEqual(thread_filter.pending_booking["awaiting_field"], "name")

    @patch("apps.agents.langchain_tools._build_booking_selection_chain")
    def test_invoke_booking_agent_persists_selection_from_structured_output(self, build_booking_selection_chain_mock):
        thread = ChatThread.objects.create(title="Booking thread")
        thread_filter = ThreadFilter.objects.create(
            thread=thread,
            latest_result_context={
                "thread_id": str(thread.id),
                "search_domains": ["sports"],
                "results": [
                    {
                        "position": 1,
                        "domain": "sports",
                        "listing_code": "SPT-1",
                        "title": "Mumbai Match",
                        "city": "Mumbai",
                        "venue_name": "Wankhede Stadium",
                        "event_date": "2026-04-12",
                        "start_at": "2026-04-12T19:30:00+05:30",
                    }
                ],
            },
        )
        build_booking_selection_chain_mock.return_value.invoke.return_value = BookingTurnResolution(
            action="selection_pending",
            message="I selected Mumbai Match. Reply yes to confirm it or no to clear it.",
            listing_code="SPT-1",
        )

        resolution = invoke_booking_agent(thread_id=str(thread.id), user_message="book this one")

        thread_filter.refresh_from_db()
        self.assertEqual(resolution.action, "selection_pending")
        self.assertEqual(resolution.listing_code, "SPT-1")
        self.assertEqual(resolution.selected_event.listing_code, "SPT-1")
        self.assertEqual(thread_filter.pending_booking["listing_code"], "SPT-1")
        self.assertEqual(thread_filter.pending_booking["status"], "pending_confirmation")

    @patch("apps.agents.langchain_tools._build_booking_selection_chain")
    def test_invoke_booking_agent_keeps_state_unchanged_for_ambiguous_selection(self, build_booking_selection_chain_mock):
        thread = ChatThread.objects.create(title="Booking thread")
        thread_filter = ThreadFilter.objects.create(
            thread=thread,
            latest_result_context={
                "thread_id": str(thread.id),
                "search_domains": ["sports"],
                "results": [
                    {"position": 1, "domain": "sports", "listing_code": "SPT-1", "title": "Mumbai Match"},
                    {"position": 2, "domain": "sports", "listing_code": "SPT-2", "title": "Delhi Match"},
                ],
            },
        )
        build_booking_selection_chain_mock.return_value.invoke.return_value = BookingTurnResolution(
            action="ambiguous",
            message="Please tell me which visible event you want to book.",
            candidates=["SPT-1", "SPT-2"],
        )

        resolution = invoke_booking_agent(thread_id=str(thread.id), user_message="book that one")

        thread_filter.refresh_from_db()
        self.assertEqual(resolution.action, "ambiguous")
        self.assertEqual(thread_filter.pending_booking, {})

    @patch("apps.agents.langchain_tools._build_booking_selection_chain")
    def test_invoke_booking_agent_rejects_selection_without_listing_code(self, build_booking_selection_chain_mock):
        thread = ChatThread.objects.create(title="Booking thread")
        thread_filter = ThreadFilter.objects.create(
            thread=thread,
            latest_result_context={
                "thread_id": str(thread.id),
                "search_domains": ["sports"],
                "results": [
                    {"position": 1, "domain": "sports", "listing_code": "SPT-1", "title": "Mumbai Match"},
                ],
            },
        )
        build_booking_selection_chain_mock.return_value.invoke.return_value = BookingTurnResolution(
            action="selection_pending",
            message="I found the event you want.",
            listing_code="",
        )

        resolution = invoke_booking_agent(thread_id=str(thread.id), user_message="book this one")

        thread_filter.refresh_from_db()
        self.assertEqual(resolution.action, "no_match")
        self.assertEqual(thread_filter.pending_booking, {})

    @patch("apps.agents.langchain_tools.attempt_thread_pending_booking_confirmation")
    @patch("apps.agents.langchain_tools._build_booking_confirmation_chain")
    def test_invoke_booking_agent_confirmation_routes_to_missing_user_info(
        self,
        build_booking_confirmation_chain_mock,
        attempt_confirmation_mock,
    ):
        thread = ChatThread.objects.create(title="Booking thread")
        ThreadFilter.objects.create(
            thread=thread,
            pending_booking={
                "status": "pending_confirmation",
                "listing_code": "SPT-1",
                "customer_info": {"name": "", "email": "", "contact_number": ""},
                "event_snapshot": {"listing_code": "SPT-1", "title": "Mumbai Match", "domain": "sports"},
            },
            latest_result_context={"results": []},
        )
        build_booking_confirmation_chain_mock.return_value.invoke.return_value = BookingTurnResolution(
            action="booking_confirmed",
            message="Yes, proceed with the booking.",
        )
        attempt_confirmation_mock.return_value = {
            "status": "missing_user_info",
            "next_required_field": "name",
            "message": "Please share your full name to complete the booking.",
            "pending_booking": {
                "status": "awaiting_user_info",
                "listing_code": "SPT-1",
                "awaiting_field": "name",
                "customer_info": {"name": "", "email": "", "contact_number": ""},
                "event_snapshot": {"listing_code": "SPT-1", "title": "Mumbai Match", "domain": "sports"},
            },
        }

        resolution = invoke_booking_agent(thread_id=str(thread.id), user_message="yes")

        self.assertEqual(resolution.action, "awaiting_user_info")
        self.assertEqual(resolution.requested_field, "name")
        self.assertEqual(resolution.listing_code, "SPT-1")

    @patch("apps.agents.langchain_tools.cancel_thread_pending_booking")
    @patch("apps.agents.langchain_tools._build_booking_confirmation_chain")
    def test_invoke_booking_agent_confirmation_can_clear_booking(
        self,
        build_booking_confirmation_chain_mock,
        cancel_pending_booking_mock,
    ):
        thread = ChatThread.objects.create(title="Booking thread")
        ThreadFilter.objects.create(
            thread=thread,
            pending_booking={
                "status": "pending_confirmation",
                "listing_code": "SPT-1",
                "customer_info": {"name": "", "email": "", "contact_number": ""},
                "event_snapshot": {"listing_code": "SPT-1", "title": "Mumbai Match", "domain": "sports"},
            },
            latest_result_context={"results": []},
        )
        build_booking_confirmation_chain_mock.return_value.invoke.return_value = BookingTurnResolution(
            action="booking_cleared",
            message="Okay, I cleared that booking selection.",
        )

        resolution = invoke_booking_agent(thread_id=str(thread.id), user_message="cancel this booking")

        self.assertEqual(resolution.action, "booking_cleared")
        cancel_pending_booking_mock.assert_called_once()

    @patch("apps.agents.langchain_tools.cancel_thread_pending_booking")
    @patch("apps.agents.langchain_tools._build_booking_confirmation_chain")
    def test_invoke_booking_agent_confirmation_can_clear_selection_for_different_event_request(
        self,
        build_booking_confirmation_chain_mock,
        cancel_pending_booking_mock,
    ):
        thread = ChatThread.objects.create(title="Booking thread")
        ThreadFilter.objects.create(
            thread=thread,
            pending_booking={
                "status": "pending_confirmation",
                "listing_code": "MOV-1",
                "customer_info": {"name": "", "email": "", "contact_number": ""},
                "event_snapshot": {"listing_code": "MOV-1", "title": "Love and War", "domain": "movies"},
            },
            latest_result_context={
                "results": [
                    {"position": 1, "domain": "movies", "listing_code": "MOV-1", "title": "Love and War"},
                    {"position": 2, "domain": "movies", "listing_code": "MOV-2", "title": "Kuberaa"},
                ]
            },
        )
        build_booking_confirmation_chain_mock.return_value.invoke.return_value = BookingTurnResolution(
            action="booking_cleared",
            message="Sure, I cleared that selection so you can pick a different movie.",
        )

        resolution = invoke_booking_agent(thread_id=str(thread.id), user_message="I want a different movie")

        self.assertEqual(resolution.action, "booking_cleared")
        self.assertIn("different movie", resolution.message.lower())
        cancel_pending_booking_mock.assert_called_once()

    @patch("apps.agents.langchain_tools.attempt_thread_pending_booking_confirmation")
    @patch("apps.agents.langchain_tools.capture_thread_booking_user_info")
    @patch("apps.agents.langchain_tools._build_booking_user_info_chain")
    def test_invoke_booking_agent_user_info_saves_value_and_requests_next_field(
        self,
        build_booking_user_info_chain_mock,
        capture_user_info_mock,
        attempt_confirmation_mock,
    ):
        thread = ChatThread.objects.create(title="Booking thread")
        ThreadFilter.objects.create(
            thread=thread,
            pending_booking={
                "status": "awaiting_user_info",
                "listing_code": "SPT-1",
                "awaiting_field": "name",
                "customer_info": {"name": "", "email": "", "contact_number": ""},
                "event_snapshot": {"listing_code": "SPT-1", "title": "Mumbai Match", "domain": "sports"},
            },
            latest_result_context={"results": []},
        )
        build_booking_user_info_chain_mock.return_value.invoke.return_value = BookingTurnResolution(
            action="booking_confirmed",
            message="I have recorded the name as Nandan Kumar.",
        )
        capture_user_info_mock.return_value = {
            "status": "saved",
            "pending_booking": {
                "status": "awaiting_user_info",
                "listing_code": "SPT-1",
                "awaiting_field": None,
                "customer_info": {"name": "Nandan Kumar", "email": "", "contact_number": ""},
                "event_snapshot": {"listing_code": "SPT-1", "title": "Mumbai Match", "domain": "sports"},
            },
        }
        attempt_confirmation_mock.return_value = {
            "status": "missing_user_info",
            "next_required_field": "email",
            "message": "Please share your email address to complete the booking.",
            "pending_booking": {
                "status": "awaiting_user_info",
                "listing_code": "SPT-1",
                "awaiting_field": "email",
                "customer_info": {"name": "Nandan Kumar", "email": "", "contact_number": ""},
                "event_snapshot": {"listing_code": "SPT-1", "title": "Mumbai Match", "domain": "sports"},
            },
        }

        resolution = invoke_booking_agent(thread_id=str(thread.id), user_message="Nandan Kumar")

        self.assertEqual(resolution.action, "awaiting_user_info")
        self.assertEqual(resolution.requested_field, "email")
        capture_user_info_mock.assert_called_once_with(
            thread_filter=thread.filter_state,
            field_name="name",
            value="Nandan Kumar",
        )
        attempt_confirmation_mock.assert_called_once()

    @patch("apps.agents.langchain_tools.capture_thread_booking_user_info")
    @patch("apps.agents.langchain_tools._build_booking_user_info_chain")
    def test_invoke_booking_agent_user_info_handles_validation_failure(
        self,
        build_booking_user_info_chain_mock,
        capture_user_info_mock,
    ):
        thread = ChatThread.objects.create(title="Booking thread")
        ThreadFilter.objects.create(
            thread=thread,
            pending_booking={
                "status": "awaiting_user_info",
                "listing_code": "SPT-1",
                "awaiting_field": "email",
                "customer_info": {"name": "Nandan Kumar", "email": "", "contact_number": ""},
                "event_snapshot": {"listing_code": "SPT-1", "title": "Mumbai Match", "domain": "sports"},
            },
            latest_result_context={"results": []},
        )
        build_booking_user_info_chain_mock.return_value.invoke.return_value = BookingTurnResolution(
            action="booking_confirmed",
            message="not-an-email",
        )
        capture_user_info_mock.return_value = {
            "status": "invalid_user_info",
            "message": "Please provide a valid email address.",
            "pending_booking": {
                "status": "awaiting_user_info",
                "listing_code": "SPT-1",
                "awaiting_field": "email",
                "customer_info": {"name": "Nandan Kumar", "email": "", "contact_number": ""},
                "event_snapshot": {"listing_code": "SPT-1", "title": "Mumbai Match", "domain": "sports"},
            },
            "field_name": "email",
        }

        resolution = invoke_booking_agent(thread_id=str(thread.id), user_message="not-an-email")

        self.assertEqual(resolution.action, "awaiting_user_info")
        self.assertEqual(resolution.requested_field, "email")
        self.assertIn("valid email", resolution.message.lower())

    @patch("apps.agents.langchain_tools.attempt_thread_pending_booking_confirmation")
    @patch("apps.agents.langchain_tools.capture_thread_booking_user_info")
    @patch("apps.agents.langchain_tools._build_booking_user_info_chain")
    def test_invoke_booking_agent_user_info_returns_full_confirmation_message(
        self,
        build_booking_user_info_chain_mock,
        capture_user_info_mock,
        attempt_confirmation_mock,
    ):
        thread = ChatThread.objects.create(title="Booking thread")
        ThreadFilter.objects.create(
            thread=thread,
            pending_booking={
                "status": "awaiting_user_info",
                "listing_code": "SPT-1",
                "awaiting_field": "contact_number",
                "customer_info": {"name": "Nandan Kumar", "email": "nandan@example.com", "contact_number": ""},
                "event_snapshot": {"listing_code": "SPT-1", "title": "Mumbai Match", "domain": "sports"},
            },
            latest_result_context={"results": []},
        )
        build_booking_user_info_chain_mock.return_value.invoke.return_value = BookingTurnResolution(
            action="booking_confirmed",
            message="+91 9876543210",
        )
        capture_user_info_mock.return_value = {
            "status": "saved",
            "pending_booking": {
                "status": "awaiting_user_info",
                "listing_code": "SPT-1",
                "awaiting_field": None,
                "customer_info": {"name": "Nandan Kumar", "email": "nandan@example.com", "contact_number": "+91 9876543210"},
                "event_snapshot": {
                    "listing_code": "SPT-1",
                    "title": "Mumbai Match",
                    "city": "Mumbai",
                    "venue_name": "Wankhede Stadium",
                    "start_at": "2026-04-12T19:30:00+05:30",
                    "domain": "sports",
                },
            },
        }
        attempt_confirmation_mock.return_value = {
            "status": "confirmed",
            "booking": {
                "booking_reference": "ATD-BOOK1234",
                "event_title": "Mumbai Match",
                "city": "Mumbai",
                "venue_name": "Wankhede Stadium",
                "customer_name": "Nandan Kumar",
                "customer_email": "nandan@example.com",
                "customer_contact_number": "+91 9876543210",
            },
        }

        resolution = invoke_booking_agent(thread_id=str(thread.id), user_message="+91 9876543210")

        self.assertEqual(resolution.action, "booking_confirmed")
        self.assertIn("Booking confirmed for Mumbai Match", resolution.message)
        self.assertIn("ATD-BOOK1234", resolution.message)

    @patch("apps.agents.services.resolve_turn_filters")
    @patch("apps.agents.services.invoke_booking_agent")
    def test_process_chat_turn_returns_agent_requested_next_user_info_prompt(
        self,
        invoke_booking_agent_mock,
        resolve_turn_filters_mock,
    ):
        thread = ChatThread.objects.create(title="Existing thread")
        thread_filter = ThreadFilter.objects.create(
            thread=thread,
            active_filters={"event_types": ["sports"]},
            pending_booking={
                "status": "awaiting_user_info",
                "listing_code": "SPT-1",
                "awaiting_field": "email",
                "customer_info": {"name": "Nandan Kumar", "email": "", "contact_number": ""},
                "event_snapshot": {
                    "listing_code": "SPT-1",
                    "title": "Mumbai Match",
                    "city": "Mumbai",
                    "venue_name": "Wankhede Stadium",
                    "event_date": "2026-04-12",
                    "start_at": "2026-04-12T19:30:00+05:30",
                    "min_price": 499,
                    "max_price": 2400,
                    "domain": "sports",
                },
            },
        )

        def leave_pending_half_updated(**_kwargs):
            thread_filter.pending_booking = {
                **thread_filter.pending_booking,
                "customer_info": {
                    "name": "Nandan Kumar",
                    "email": "nandan@example.com",
                    "contact_number": "",
                },
                "awaiting_field": "contact_number",
            }
            thread_filter.save(update_fields=["pending_booking", "updated_at"])
            return BookingTurnResolution(
                action="awaiting_user_info",
                message="Thanks, Nandan Kumar. Please provide your contact number to proceed with the booking.",
                listing_code="SPT-1",
                requested_field="contact_number",
                selected_event={"listing_code": "SPT-1", "title": "Mumbai Match"},
            )

        invoke_booking_agent_mock.side_effect = leave_pending_half_updated

        payload = process_chat_turn(user_message="nandan@example.com", thread_id=str(thread.id))

        resolve_turn_filters_mock.assert_not_called()
        self.assertEqual(payload["assistant_message"]["metadata"]["booking_action"], "awaiting_user_info")
        self.assertEqual(payload["assistant_message"]["metadata"]["requested_field"], "contact_number")
        thread_filter.refresh_from_db()
        self.assertEqual(thread_filter.pending_booking["awaiting_field"], "contact_number")

    @patch("apps.agents.services.resolve_turn_filters")
    @patch("apps.agents.services.invoke_booking_agent")
    def test_process_chat_turn_trusts_agent_when_same_user_info_prompt_repeats(
        self,
        invoke_booking_agent_mock,
        resolve_turn_filters_mock,
    ):
        thread = ChatThread.objects.create(title="Existing thread")
        thread_filter = ThreadFilter.objects.create(
            thread=thread,
            active_filters={"event_types": ["sports"]},
            pending_booking={
                "status": "awaiting_user_info",
                "listing_code": "SPT-1",
                "awaiting_field": "email",
                "customer_info": {"name": "Nandan Kumar", "email": "", "contact_number": ""},
                "event_snapshot": {
                    "listing_code": "SPT-1",
                    "title": "Mumbai Match",
                    "city": "Mumbai",
                    "venue_name": "Wankhede Stadium",
                    "event_date": "2026-04-12",
                    "start_at": "2026-04-12T19:30:00+05:30",
                    "min_price": 499,
                    "max_price": 2400,
                    "domain": "sports",
                },
            },
        )
        invoke_booking_agent_mock.return_value = BookingTurnResolution(
            action="awaiting_user_info",
            message="Please share your email address to complete the booking.",
            listing_code="SPT-1",
            requested_field="email",
            selected_event={"listing_code": "SPT-1", "title": "Mumbai Match"},
        )

        payload = process_chat_turn(user_message="nandan@example.com", thread_id=str(thread.id))

        resolve_turn_filters_mock.assert_not_called()
        self.assertEqual(payload["assistant_message"]["metadata"]["booking_action"], "awaiting_user_info")
        self.assertEqual(payload["assistant_message"]["metadata"]["requested_field"], "email")
        thread_filter.refresh_from_db()
        self.assertEqual(thread_filter.pending_booking["customer_info"]["email"], "")
        self.assertEqual(thread_filter.pending_booking["awaiting_field"], "email")

    @patch("apps.agents.services.resolve_turn_filters")
    @patch("apps.agents.services.invoke_booking_agent")
    def test_process_chat_turn_returns_current_results_when_booking_is_cleared(
        self,
        invoke_booking_agent_mock,
        resolve_turn_filters_mock,
    ):
        thread = ChatThread.objects.create(title="Existing thread")
        ThreadFilter.objects.create(
            thread=thread,
            active_filters={"event_types": ["sports"], "sport_types": ["Cricket"]},
            latest_result_context={
                "thread_id": str(thread.id),
                "search_domains": ["sports"],
                "results": [
                    {
                        "position": 1,
                        "domain": "sports",
                        "listing_code": "SPT-1",
                        "title": "Mumbai Match",
                        "city": "Mumbai",
                        "venue_name": "Wankhede Stadium",
                        "event_date": "2026-04-12",
                        "start_at": "2026-04-12T19:30:00+05:30",
                        "min_price": 499,
                        "max_price": 2400,
                        "sport_type": "Cricket",
                    }
                ],
            },
            pending_booking={
                "status": "pending_confirmation",
                "listing_code": "SPT-1",
                "event_snapshot": {"listing_code": "SPT-1", "title": "Mumbai Match"},
            },
        )
        invoke_booking_agent_mock.return_value = BookingTurnResolution(
            action="booking_cleared",
            message="Okay, I have canceled the selection.",
        )

        payload = process_chat_turn(user_message="no", thread_id=str(thread.id))

        resolve_turn_filters_mock.assert_not_called()
        self.assertEqual(payload["assistant_message"]["metadata"]["booking_action"], "booking_cleared")
        self.assertIn("sports", payload["assistant_message"]["metadata"]["results_by_domain"])
        self.assertEqual(
            payload["assistant_message"]["metadata"]["results_by_domain"]["sports"]["results"][0]["listing_code"],
            "SPT-1",
        )
        self.assertEqual(payload["search_domains"], ["sports"])

    @patch("apps.agents.services.resolve_turn_filters")
    @patch("apps.agents.services.invoke_booking_agent")
    def test_process_chat_turn_falls_through_to_search_for_non_booking_follow_up_and_clears_pending(
        self,
        invoke_booking_agent_mock,
        resolve_turn_filters_mock,
    ):
        thread = ChatThread.objects.create(title="Existing thread")
        thread_filter = ThreadFilter.objects.create(
            thread=thread,
            active_filters={
                "event_types": ["sports"],
                "cities": ["Mumbai"],
                "event_dates": ["2026-04-12"],
                "sport_types": ["Cricket"],
            },
            latest_result_context={
                "thread_id": str(thread.id),
                "search_domains": ["sports"],
                "results": [
                    {
                        "position": 1,
                        "listing_code": "SPT-1",
                        "title": "Mumbai Match",
                        "city": "Mumbai",
                        "venue_name": "Wankhede Stadium",
                        "event_date": "2026-04-12",
                        "start_at": "2026-04-12T19:30:00+05:30",
                        "sport_type": "Cricket",
                    }
                ],
            },
            pending_booking={
                "status": "pending_confirmation",
                "listing_code": "SPT-1",
                "event_snapshot": {"listing_code": "SPT-1", "title": "Mumbai Match"},
            },
        )
        invoke_booking_agent_mock.return_value = BookingTurnResolution(
            action="none",
        )
        resolve_turn_filters_mock.return_value = TurnResolution(
            updates=ActiveFilters(sport_types=["Football"]),
            tool_trace=["resolve_sport_filters"],
        )

        payload = process_chat_turn(user_message="show football instead", thread_id=str(thread.id))

        self.assertEqual(resolve_turn_filters_mock.call_count, 1)
        thread_filter.refresh_from_db()
        self.assertEqual(thread_filter.pending_booking, {})
        self.assertEqual(payload["active_filters"]["sport_types"], ["Football"])

    @patch("apps.agents.services.resolve_turn_filters")
    @patch("apps.agents.services.invoke_booking_agent")
    def test_process_chat_turn_returns_ambiguous_when_selection_matches_multiple_results(
        self,
        invoke_booking_agent_mock,
        resolve_turn_filters_mock,
    ):
        thread = ChatThread.objects.create(title="Existing thread")
        ThreadFilter.objects.create(
            thread=thread,
            active_filters={"event_types": ["movies"], "cities": ["Mumbai"]},
            latest_result_context={
                "thread_id": str(thread.id),
                "search_domains": ["movies"],
                "results": [
                    {
                        "position": 3,
                        "listing_code": "MOV-011-02",
                        "title": "Love and War",
                        "city": "Mumbai",
                        "venue_name": "PVR Phoenix",
                        "event_date": "2026-04-18",
                        "start_at": "2026-04-18T08:00:00+00:00",
                    },
                    {
                        "position": 4,
                        "listing_code": "MOV-020-02",
                        "title": "Kuberaa",
                        "city": "Mumbai",
                        "venue_name": "PVR Phoenix",
                        "event_date": "2026-04-20",
                        "start_at": "2026-04-20T04:45:00+00:00",
                    },
                ],
            },
        )
        invoke_booking_agent_mock.return_value = BookingTurnResolution(
            action="ambiguous",
            message="Multiple matching events are available at PVR Phoenix. Please tell me which one you want to book.",
            candidates=["Love and War", "Kuberaa"],
        )

        payload = process_chat_turn(user_message="book the PVR Phoenix one", thread_id=str(thread.id))

        resolve_turn_filters_mock.assert_not_called()
        self.assertEqual(payload["assistant_message"]["metadata"]["booking_action"], "ambiguous")
        self.assertEqual(payload["pending_booking"], {})
        self.assertIn("multiple matching events", payload["assistant_message"]["content"].lower())

    @patch("apps.agents.services.resolve_turn_filters")
    @patch("apps.agents.services.invoke_booking_agent")
    def test_process_chat_turn_reconciles_single_result_booking_ambiguity_to_selection(
        self,
        invoke_booking_agent_mock,
        resolve_turn_filters_mock,
    ):
        thread = ChatThread.objects.create(title="Existing thread")
        thread_filter = ThreadFilter.objects.create(
            thread=thread,
            active_filters={
                "event_types": ["sports"],
                "cities": ["Kolkata"],
                "event_dates": ["2026-04-19"],
                "sport_types": ["Cricket"],
            },
            latest_result_context={
                "thread_id": str(thread.id),
                "search_domains": ["sports"],
                "results": [
                    {
                        "position": 1,
                        "domain": "sports",
                        "listing_code": "SPT-IPL-028",
                        "title": "Rajasthan Royals vs Kolkata Knight Riders",
                        "city": "Kolkata",
                        "venue_name": "Eden Gardens",
                        "event_date": "2026-04-19",
                        "start_at": "2026-04-19T10:00:00+00:00",
                        "sport_type": "Cricket",
                    }
                ],
            },
        )
        invoke_booking_agent_mock.return_value = BookingTurnResolution(
            action="ambiguous",
            message="Please specify which cricket event in Kolkata on 2026-04-19 you want to book, as there are multiple matches available.",
        )

        payload = process_chat_turn(user_message="book this one", thread_id=str(thread.id))

        resolve_turn_filters_mock.assert_not_called()
        thread_filter.refresh_from_db()
        self.assertEqual(payload["assistant_message"]["metadata"]["booking_action"], "selection_pending")
        self.assertEqual(payload["pending_booking"]["listing_code"], "SPT-IPL-028")
        self.assertEqual(thread_filter.pending_booking["listing_code"], "SPT-IPL-028")
        self.assertIn("only matching event", payload["assistant_message"]["content"].lower())

    @patch("apps.agents.services.resolve_turn_filters")
    @patch("apps.agents.services.invoke_booking_agent")
    def test_process_chat_turn_does_not_force_booking_selection_when_agent_returns_none(
        self,
        invoke_booking_agent_mock,
        resolve_turn_filters_mock,
    ):
        thread = ChatThread.objects.create(title="Existing thread")
        ThreadFilter.objects.create(
            thread=thread,
            active_filters={"event_types": ["movies"], "cities": ["Mumbai"]},
            latest_result_context={
                "thread_id": str(thread.id),
                "search_domains": ["movies"],
                "results": [
                    {
                        "position": 3,
                        "listing_code": "MOV-011-02",
                        "title": "Love and War",
                        "city": "Mumbai",
                        "venue_name": "PVR Phoenix",
                        "event_date": "2026-04-18",
                        "start_at": "2026-04-18T08:00:00+00:00",
                    }
                ],
            },
        )
        invoke_booking_agent_mock.return_value = BookingTurnResolution(action="none")
        resolve_turn_filters_mock.return_value = TurnResolution(
            updates=ActiveFilters(),
            tool_trace=[],
        )

        payload = process_chat_turn(user_message="book Love and War", thread_id=str(thread.id))

        self.assertNotIn("booking_action", payload["assistant_message"]["metadata"])
        self.assertEqual(payload["pending_booking"], {})
        self.assertEqual(payload["search_domains"], ["movies"])

    @patch("apps.agents.services.resolve_turn_filters")
    @patch("apps.agents.services.invoke_booking_agent")
    def test_process_chat_turn_relies_on_agent_for_user_info_booking_progression(
        self,
        invoke_booking_agent_mock,
        resolve_turn_filters_mock,
    ):
        thread = ChatThread.objects.create(title="Existing thread")
        thread_filter = ThreadFilter.objects.create(
            thread=thread,
            active_filters={"event_types": ["sports"]},
            pending_booking={
                "status": "awaiting_user_info",
                "listing_code": "SPT-BOOK-1",
                "awaiting_field": "contact_number",
                "customer_info": {
                    "name": "Nandan Kumar",
                    "email": "nandan@example.com",
                    "contact_number": "",
                },
                "event_snapshot": {"listing_code": "SPT-BOOK-1", "title": "Mumbai Match"},
            },
        )
        invoke_booking_agent_mock.return_value = BookingTurnResolution(
            action="booking_confirmed",
            message="Booking confirmed for Mumbai Match. Your reference is ATD-BOOK1234.",
            listing_code="SPT-BOOK-1",
            booking={"booking_reference": "ATD-BOOK1234"},
        )

        payload = process_chat_turn(user_message="+91 9876543210", thread_id=str(thread.id))

        resolve_turn_filters_mock.assert_not_called()
        self.assertEqual(payload["assistant_message"]["metadata"]["booking_action"], "booking_confirmed")

    @patch("apps.agents.services.resolve_turn_filters")
    @patch("apps.agents.services.invoke_booking_agent")
    def test_process_chat_turn_hides_latest_results_during_user_info_stage(
        self,
        invoke_booking_agent_mock,
        resolve_turn_filters_mock,
    ):
        thread = ChatThread.objects.create(title="Existing thread")
        ThreadFilter.objects.create(
            thread=thread,
            active_filters={"event_types": ["sports"], "sport_types": ["Cricket"]},
            latest_result_context={
                "thread_id": str(thread.id),
                "search_domains": ["sports"],
                "results": [
                    {
                        "position": 1,
                        "domain": "sports",
                        "listing_code": "SPT-1",
                        "title": "Mumbai Match",
                        "city": "Mumbai",
                        "venue_name": "Wankhede Stadium",
                        "event_date": "2026-04-12",
                        "start_at": "2026-04-12T19:30:00+05:30",
                        "sport_type": "Cricket",
                    }
                ],
            },
            pending_booking={
                "status": "awaiting_user_info",
                "listing_code": "SPT-1",
                "awaiting_field": "email",
                "customer_info": {"name": "Nandan Kumar", "email": "", "contact_number": ""},
                "event_snapshot": {"listing_code": "SPT-1", "title": "Mumbai Match"},
            },
        )
        invoke_booking_agent_mock.return_value = BookingTurnResolution(
            action="awaiting_user_info",
            message="Please share your email address to complete the booking.",
            listing_code="SPT-1",
            requested_field="email",
        )

        payload = process_chat_turn(user_message="tell me a joke first", thread_id=str(thread.id))

        resolve_turn_filters_mock.assert_not_called()
        self.assertEqual(payload["search_domains"], [])
        self.assertEqual(payload["results_by_domain"], {})

    @patch("apps.agents.services.resolve_turn_filters")
    @patch("apps.agents.services.invoke_booking_agent")
    def test_process_chat_turn_reselection_during_user_info_restores_requested_field(
        self,
        invoke_booking_agent_mock,
        resolve_turn_filters_mock,
    ):
        thread = ChatThread.objects.create(title="Existing thread")
        thread_filter = ThreadFilter.objects.create(
            thread=thread,
            active_filters={"event_types": ["sports"], "sport_types": ["Cricket"]},
            latest_result_context={
                "thread_id": str(thread.id),
                "search_domains": ["sports"],
                "results": [
                    {
                        "position": 1,
                        "domain": "sports",
                        "listing_code": "SPT-1",
                        "title": "Mumbai Match",
                        "city": "Mumbai",
                        "venue_name": "Wankhede Stadium",
                        "event_date": "2026-04-12",
                        "start_at": "2026-04-12T19:30:00+05:30",
                        "sport_type": "Cricket",
                    },
                    {
                        "position": 2,
                        "domain": "sports",
                        "listing_code": "SPT-2",
                        "title": "Delhi Match",
                        "city": "New Delhi",
                        "venue_name": "Arun Jaitley Stadium",
                        "event_date": "2026-04-13",
                        "start_at": "2026-04-13T19:30:00+05:30",
                        "sport_type": "Cricket",
                    },
                ],
            },
            pending_booking={
                "status": "awaiting_user_info",
                "listing_code": "SPT-1",
                "awaiting_field": "contact_number",
                "customer_info": {
                    "name": "Nandan Kumar",
                    "email": "nandan@example.com",
                    "contact_number": "",
                },
                "event_snapshot": {"listing_code": "SPT-1", "title": "Mumbai Match"},
            },
        )

        def switch_pending_selection(**_kwargs):
            thread_filter.pending_booking = {
                "status": "pending_confirmation",
                "listing_code": "SPT-2",
                "awaiting_field": None,
                "customer_info": {
                    "name": "Nandan Kumar",
                    "email": "nandan@example.com",
                    "contact_number": "",
                },
                "event_snapshot": {
                    "listing_code": "SPT-2",
                    "title": "Delhi Match",
                    "city": "New Delhi",
                    "venue_name": "Arun Jaitley Stadium",
                    "event_date": "2026-04-13",
                    "start_at": "2026-04-13T19:30:00+05:30",
                    "sport_type": "Cricket",
                    "domain": "sports",
                },
            }
            thread_filter.save(update_fields=["pending_booking", "updated_at"])
            return BookingTurnResolution(
                action="selection_pending",
                message="The Delhi match has been selected.",
                listing_code="SPT-2",
                selected_event={"listing_code": "SPT-2", "title": "Delhi Match"},
            )

        invoke_booking_agent_mock.side_effect = switch_pending_selection

        payload = process_chat_turn(user_message="book the Delhi one instead", thread_id=str(thread.id))

        resolve_turn_filters_mock.assert_not_called()
        thread_filter.refresh_from_db()
        self.assertEqual(payload["assistant_message"]["metadata"]["booking_action"], "awaiting_user_info")
        self.assertEqual(payload["assistant_message"]["metadata"]["requested_field"], "contact_number")
        self.assertEqual(thread_filter.pending_booking["listing_code"], "SPT-2")
        self.assertEqual(thread_filter.pending_booking["awaiting_field"], "contact_number")

    @patch("apps.agents.services.invoke_booking_agent", return_value=BookingTurnResolution(action="none"))
    @patch("apps.agents.services.invoke_turn_policy")
    @patch("apps.agents.services.search_sport_events")
    @patch("apps.agents.services.resolve_turn_filters")
    def test_process_chat_turn_soft_redirects_off_track_and_keeps_current_results(
        self,
        resolve_turn_filters_mock,
        search_sport_events_mock,
        invoke_turn_policy_mock,
        _invoke_booking_agent_mock,
    ):
        thread = ChatThread.objects.create(title="Existing thread")
        ThreadFilter.objects.create(
            thread=thread,
            active_filters={
                "event_types": ["sports"],
                "cities": ["Mumbai"],
                "sport_types": ["Football"],
            },
        )
        invoke_turn_policy_mock.return_value = TurnPolicy(
            intent="temporary_distraction",
            message="I can help with event plans here. Coming back to your football search, these are the current matches.",
            should_keep_results=True,
        )
        search_sport_events_mock.return_value = SearchResult(
            count=1,
            limit=5,
            offset=0,
            filters={"cities": ["Mumbai"], "sport_types": ["Football"]},
            results=[
                {
                    "listing_code": "SPT-FOOT-1",
                    "title": "Mumbai City FC vs Mohun Bagan",
                    "sport_type": "Football",
                    "city": "Mumbai",
                    "venue_name": "Mumbai Football Arena",
                    "event_date": "2026-04-13",
                    "start_at": "2026-04-13T14:00:00+00:00",
                    "min_price": 499,
                    "max_price": 1499,
                }
            ],
        )

        payload = process_chat_turn(user_message="write a poem", thread_id=str(thread.id))

        resolve_turn_filters_mock.assert_not_called()
        self.assertEqual(payload["search_domains"], ["sports"])
        self.assertEqual(payload["results_by_domain"]["sports"]["count"], 1)
        self.assertIn("football search", payload["assistant_message"]["content"].lower())
        self.assertIn("Mumbai City FC vs Mohun Bagan", payload["assistant_message"]["content"])
        self.assertEqual(payload["goal_state"]["goal_summary"], "Event planning")

    @patch("apps.agents.services.invoke_booking_agent", return_value=BookingTurnResolution(action="none"))
    @patch("apps.agents.services.invoke_turn_policy")
    @patch("apps.agents.services.search_movie_events")
    @patch("apps.agents.services.resolve_turn_filters")
    def test_process_chat_turn_soft_redirect_during_booking_keeps_selection_and_hides_results(
        self,
        resolve_turn_filters_mock,
        search_movie_events_mock,
        invoke_turn_policy_mock,
        _invoke_booking_agent_mock,
    ):
        thread = ChatThread.objects.create(title="Existing thread")
        ThreadFilter.objects.create(
            thread=thread,
            active_filters={
                "event_types": ["movies"],
                "cities": ["Mumbai"],
            },
            latest_result_context={
                "thread_id": str(thread.id),
                "search_domains": ["movies"],
                "results": [
                    {
                        "position": 1,
                        "domain": "movies",
                        "listing_code": "MOV-1",
                        "title": "Love and War",
                        "city": "Mumbai",
                        "venue_name": "PVR Phoenix",
                        "event_date": "2026-04-18",
                        "start_at": "2026-04-18T08:00:00+00:00",
                    }
                ],
            },
            pending_booking={
                "status": "awaiting_user_info",
                "listing_code": "MOV-1",
                "awaiting_field": "contact_number",
                "customer_info": {"name": "Nandan Kumar", "email": "nandan@example.com", "contact_number": ""},
                "event_snapshot": {
                    "listing_code": "MOV-1",
                    "title": "Love and War",
                    "city": "Mumbai",
                    "venue_name": "PVR Phoenix",
                    "event_date": "2026-04-18",
                    "start_at": "2026-04-18T08:00:00+00:00",
                    "domain": "movies",
                },
            },
        )
        invoke_turn_policy_mock.return_value = TurnPolicy(
            intent="temporary_distraction",
            message="Let's continue with your booking for Love and War. Please share your contact number to complete the booking.",
            should_keep_results=True,
        )
        search_movie_events_mock.return_value = SearchResult(
            count=2,
            limit=5,
            offset=0,
            filters={"cities": ["Mumbai"]},
            results=[
                {
                    "listing_code": "MOV-1",
                    "title": "Love and War",
                    "city": "Mumbai",
                    "venue_name": "PVR Phoenix",
                    "event_date": "2026-04-18",
                    "start_at": "2026-04-18T08:00:00+00:00",
                    "min_price": 315,
                    "max_price": 375,
                    "genres": ["Romance", "Drama"],
                },
                {
                    "listing_code": "MOV-2",
                    "title": "Kuberaa",
                    "city": "Mumbai",
                    "venue_name": "PVR Phoenix",
                    "event_date": "2026-04-20",
                    "start_at": "2026-04-20T04:45:00+00:00",
                    "min_price": 315,
                    "max_price": 375,
                    "genres": ["Crime", "Drama"],
                },
            ],
        )

        payload = process_chat_turn(user_message="tell me a joke", thread_id=str(thread.id))

        resolve_turn_filters_mock.assert_not_called()
        self.assertEqual(payload["search_domains"], ["movies"])
        self.assertEqual(payload["results_by_domain"], {})
        self.assertEqual(payload["pending_booking"]["listing_code"], "MOV-1")
        self.assertEqual(payload["assistant_message"]["metadata"]["pending_booking"]["listing_code"], "MOV-1")
        self.assertEqual(payload["assistant_message"]["metadata"]["results_by_domain"], {})

    @patch("apps.agents.services.invoke_booking_agent", return_value=BookingTurnResolution(action="none"))
    @patch("apps.agents.services.invoke_turn_policy")
    @patch("apps.agents.services.resolve_turn_filters")
    def test_process_chat_turn_does_not_soft_redirect_search_change_intent(
        self,
        resolve_turn_filters_mock,
        invoke_turn_policy_mock,
        _invoke_booking_agent_mock,
    ):
        invoke_turn_policy_mock.return_value = TurnPolicy(
            intent="search_change",
            message="Looking for upcoming football matches. I'll find those for you.",
            should_keep_results=False,
        )
        resolve_turn_filters_mock.return_value = TurnResolution(
            updates=ActiveFilters(event_types=["sports"], sport_types=["Football"]),
            tool_trace=["resolve_event_type", "resolve_sport_filters"],
        )

        payload = process_chat_turn(user_message="Show me upcoming football matches")

        self.assertEqual(resolve_turn_filters_mock.call_count, 1)
        self.assertEqual(payload["active_filters"]["event_types"], ["sports"])
        self.assertEqual(payload["active_filters"]["sport_types"], ["Football"])

    @patch("apps.agents.services.invoke_booking_agent")
    @patch("apps.agents.services.invoke_turn_policy")
    @patch("apps.agents.services.resolve_turn_filters")
    def test_process_chat_turn_skips_booking_resolution_for_search_change_city_correction(
        self,
        resolve_turn_filters_mock,
        invoke_turn_policy_mock,
        invoke_booking_agent_mock,
    ):
        thread = ChatThread.objects.create(title="Existing thread")
        ThreadFilter.objects.create(
            thread=thread,
            active_filters={
                "event_types": ["sports"],
                "cities": ["New Delhi"],
                "sport_types": ["Cricket"],
            },
            latest_result_context={
                "thread_id": str(thread.id),
                "search_domains": ["sports"],
                "results": [
                    {
                        "position": 1,
                        "domain": "sports",
                        "listing_code": "SPT-1",
                        "title": "Delhi Match",
                        "city": "New Delhi",
                        "venue_name": "Arun Jaitley Stadium",
                        "event_date": "2026-04-18",
                        "start_at": "2026-04-18T19:30:00+05:30",
                        "sport_type": "Cricket",
                    }
                ],
            },
        )
        invoke_turn_policy_mock.return_value = TurnPolicy(
            intent="search_change",
            message="",
            should_keep_results=False,
        )
        resolve_turn_filters_mock.return_value = TurnResolution(
            updates=ActiveFilters(cities=["Pune"]),
            tool_trace=["resolve_location"],
        )

        payload = process_chat_turn(user_message="No wait Pune", thread_id=str(thread.id))

        invoke_booking_agent_mock.assert_not_called()
        self.assertEqual(resolve_turn_filters_mock.call_count, 1)
        self.assertEqual(payload["active_filters"]["cities"], ["Pune"])
        self.assertEqual(payload["active_filters"]["sport_types"], ["Cricket"])

    @patch("apps.agents.services.invoke_booking_agent")
    @patch("apps.agents.services.invoke_turn_policy")
    @patch("apps.agents.services.resolve_turn_filters")
    def test_process_chat_turn_skips_booking_resolution_for_search_change_domain_switch(
        self,
        resolve_turn_filters_mock,
        invoke_turn_policy_mock,
        invoke_booking_agent_mock,
    ):
        thread = ChatThread.objects.create(title="Existing thread")
        ThreadFilter.objects.create(
            thread=thread,
            active_filters={
                "event_types": ["movies"],
                "cities": ["Mumbai"],
                "languages": ["Hindi"],
            },
            latest_result_context={
                "thread_id": str(thread.id),
                "search_domains": ["movies"],
                "results": [
                    {
                        "position": 1,
                        "domain": "movies",
                        "listing_code": "MOV-1",
                        "title": "Movie Match",
                        "city": "Mumbai",
                        "venue_name": "PVR",
                        "event_date": "2026-04-18",
                        "start_at": "2026-04-18T19:30:00+05:30",
                    }
                ],
            },
        )
        invoke_turn_policy_mock.return_value = TurnPolicy(
            intent="search_change",
            message="",
            should_keep_results=False,
        )
        resolve_turn_filters_mock.return_value = TurnResolution(
            updates=ActiveFilters(event_types=["sports"], sport_types=["Cricket"]),
            tool_trace=["resolve_event_type", "resolve_sport_filters"],
        )

        payload = process_chat_turn(user_message="Show cricket matches", thread_id=str(thread.id))

        invoke_booking_agent_mock.assert_not_called()
        self.assertEqual(resolve_turn_filters_mock.call_count, 1)
        self.assertEqual(payload["active_filters"]["event_types"], ["sports"])
        self.assertEqual(payload["active_filters"]["sport_types"], ["Cricket"])
        self.assertNotIn("languages", payload["active_filters"])

    @patch("apps.agents.services.invoke_booking_agent", return_value=BookingTurnResolution(action="none"))
    @patch("apps.agents.services.resolve_turn_filters")
    def test_process_chat_turn_clears_conflicting_domain_filters(
        self,
        resolve_turn_filters_mock,
        _invoke_booking_agent_mock,
    ):
        thread = ChatThread.objects.create(title="Existing thread")
        ThreadFilter.objects.create(
            thread=thread,
            active_filters={
                "event_types": ["sports"],
                "cities": ["New Delhi"],
                "languages": ["Hindi"],
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

    @patch("apps.agents.services.invoke_booking_agent", return_value=BookingTurnResolution(action="none"))
    @patch("apps.agents.services.resolve_turn_filters")
    def test_process_chat_turn_updates_existing_location_preference(
        self,
        resolve_turn_filters_mock,
        _invoke_booking_agent_mock,
    ):
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

    @patch("apps.agents.services.invoke_booking_agent", return_value=BookingTurnResolution(action="none"))
    @patch("apps.agents.services.resolve_turn_filters")
    def test_process_chat_turn_clears_filters_returned_by_resolvers(
        self,
        resolve_turn_filters_mock,
        _invoke_booking_agent_mock,
    ):
        thread = ChatThread.objects.create(title="Existing thread")
        ThreadFilter.objects.create(
            thread=thread,
            active_filters={
                "event_types": ["sports"],
                "cities": ["Mumbai"],
                "event_dates": ["2026-04-12"],
                "sport_types": ["Cricket"],
            },
        )
        resolve_turn_filters_mock.return_value = TurnResolution(
            updates=ActiveFilters(date_from="2026-04-07", date_to="2026-04-12"),
            clear_fields=["cities", "event_dates"],
            tool_trace=["resolve_location", "resolve_temporal"],
        )

        payload = process_chat_turn(user_message="remove the mumbai filter and show matches this week", thread_id=str(thread.id))

        self.assertNotIn("cities", payload["active_filters"])
        self.assertNotIn("event_dates", payload["active_filters"])
        self.assertEqual(payload["active_filters"]["date_from"], "2026-04-07")
        self.assertEqual(payload["active_filters"]["date_to"], "2026-04-12")
        self.assertEqual(payload["active_filters"]["sport_types"], ["Cricket"])

    @patch("apps.agents.services.invoke_booking_agent", return_value=BookingTurnResolution(action="none"))
    @patch("apps.agents.services.resolve_turn_filters")
    def test_process_chat_turn_returns_no_match_reply_without_broad_fallback(
        self,
        resolve_turn_filters_mock,
        _invoke_booking_agent_mock,
    ):
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

    @patch("apps.agents.services.invoke_booking_agent", return_value=BookingTurnResolution(action="none"))
    @patch("apps.agents.services.search_sport_events")
    @patch("apps.agents.services.resolve_turn_filters")
    def test_process_chat_turn_returns_ambiguity_reply_with_candidates(
        self,
        resolve_turn_filters_mock,
        search_sport_events_mock,
        _invoke_booking_agent_mock,
    ):
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
        search_sport_events_mock.return_value = SearchResult(
            count=0,
            limit=5,
            offset=0,
            filters={},
            results=[],
        )

        payload = process_chat_turn(user_message="Show me sports in Delhi")

        self.assertEqual(payload["search_domains"], ["sports"])
        self.assertEqual(payload["results_by_domain"]["sports"]["count"], 0)
        self.assertTrue(payload["needs_clarification"])
        self.assertEqual(payload["clarification_question"], "Did you mean New Delhi, Delhi NCR?")
        self.assertIn("multiple possible matches", payload["assistant_message"]["content"].lower())

    @patch("apps.agents.services.invoke_booking_agent", return_value=BookingTurnResolution(action="none"))
    @patch("apps.agents.services.search_sport_events")
    @patch("apps.agents.services.resolve_turn_filters")
    def test_process_chat_turn_returns_results_even_with_ambiguity_when_filters_match(
        self,
        resolve_turn_filters_mock,
        search_sport_events_mock,
        _invoke_booking_agent_mock,
    ):
        resolve_turn_filters_mock.return_value = TurnResolution(
            updates=ActiveFilters(
                event_types=["sports"],
                sport_types=["Football"],
                date_from="2026-04-13",
            ),
            tool_trace=["resolve_event_type", "resolve_temporal", "resolve_sport_filters", "resolve_location"],
            issues=[
                ResolutionIssue(
                    status="ambiguous",
                    trace_name="resolve_location",
                    filter_label="location",
                    message="Please specify the city or cities where you want to see upcoming football matches, or confirm if you want matches from all cities.",
                    candidates=["Ahmedabad", "Bengaluru", "Bhubaneswar", "Chennai"],
                )
            ],
        )
        search_sport_events_mock.return_value = SearchResult(
            count=2,
            limit=5,
            offset=0,
            filters={"sport_types": ["Football"], "date_from": "2026-04-13"},
            results=[
                {
                    "listing_code": "SPT-FOOT-001",
                    "title": "Mumbai City FC vs Mohun Bagan",
                    "sport_type": "Football",
                    "city": "Mumbai",
                    "venue_name": "Mumbai Football Arena",
                    "event_date": "2026-04-13",
                    "start_at": "2026-04-13T14:00:00+00:00",
                    "min_price": 499,
                    "max_price": 1499,
                },
                {
                    "listing_code": "SPT-FOOT-002",
                    "title": "Bengaluru FC vs Kerala Blasters",
                    "sport_type": "Football",
                    "city": "Bengaluru",
                    "venue_name": "Sree Kanteerava Stadium",
                    "event_date": "2026-04-14",
                    "start_at": "2026-04-14T14:00:00+00:00",
                    "min_price": 399,
                    "max_price": 1299,
                },
            ],
        )

        payload = process_chat_turn(user_message="Show me upcoming football matches")

        self.assertEqual(payload["search_domains"], ["sports"])
        self.assertEqual(payload["results_by_domain"]["sports"]["count"], 2)
        self.assertTrue(payload["needs_clarification"])
        self.assertEqual(payload["clarification_question"], "Did you mean Ahmedabad, Bengaluru, Bhubaneswar, Chennai?")
        self.assertIn("I found football matches", payload["assistant_message"]["content"])
        self.assertIn("Did you mean Ahmedabad, Bengaluru, Bhubaneswar, Chennai?", payload["assistant_message"]["content"])

    @patch("apps.agents.services.invoke_booking_agent", return_value=BookingTurnResolution(action="none"))
    @patch("apps.agents.services.resolve_turn_filters")
    def test_process_chat_turn_broadens_sport_filters_for_catalog_style_question(
        self,
        resolve_turn_filters_mock,
        _invoke_booking_agent_mock,
    ):
        thread = ChatThread.objects.create(title="Existing thread")
        ThreadFilter.objects.create(
            thread=thread,
            active_filters={
                "event_types": ["sports"],
                "event_dates": ["2026-04-12"],
                "start_time_from": "18:00:00",
                "start_time_to": "20:00:00",
            },
        )
        resolve_turn_filters_mock.return_value = TurnResolution(
            updates=ActiveFilters(
                sport_types=["Badminton", "Cricket", "Football", "Kabaddi"],
            ),
            tool_trace=["resolve_temporal", "resolve_sport_catalog_inquiry"],
        )

        payload = process_chat_turn(
            user_message="what other sports do you have?",
            thread_id=str(thread.id),
        )

        self.assertEqual(payload["search_domains"], ["sports"])
        self.assertEqual(
            payload["active_filters"],
            {
                "event_types": ["sports"],
                "event_dates": ["2026-04-12"],
                "sport_types": ["Badminton", "Cricket", "Football", "Kabaddi"],
                "start_time_from": "18:00:00",
                "start_time_to": "20:00:00",
            },
        )
        self.assertIn("event options", payload["assistant_message"]["content"])

    @patch("apps.agents.services.invoke_booking_agent", return_value=BookingTurnResolution(action="none"))
    @patch("apps.agents.services.search_sport_events")
    @patch("apps.agents.services.resolve_turn_filters")
    def test_process_chat_turn_diversifies_broadened_sport_results(
        self,
        resolve_turn_filters_mock,
        search_sport_events_mock,
        _invoke_booking_agent_mock,
    ):
        resolve_turn_filters_mock.return_value = TurnResolution(
            updates=ActiveFilters(
                event_types=["sports"],
                cities=["Mumbai"],
                sport_types=["Badminton", "Cricket", "Football", "Kabaddi"],
            ),
            tool_trace=["resolve_event_type", "resolve_sport_catalog_inquiry"],
        )
        search_sport_events_mock.return_value = SearchResult(
            count=6,
            limit=20,
            offset=0,
            filters={},
            results=[
                {"listing_code": "1", "title": "Cricket A", "sport_type": "Cricket"},
                {"listing_code": "2", "title": "Cricket B", "sport_type": "Cricket"},
                {"listing_code": "3", "title": "Football A", "sport_type": "Football"},
                {"listing_code": "4", "title": "Kabaddi A", "sport_type": "Kabaddi"},
                {"listing_code": "5", "title": "Badminton A", "sport_type": "Badminton"},
                {"listing_code": "6", "title": "Cricket C", "sport_type": "Cricket"},
            ],
        )

        payload = process_chat_turn(user_message="what other sports do we have?")

        results = payload["results_by_domain"]["sports"]["results"]
        self.assertEqual(
            [item["sport_type"] for item in results[:4]],
            ["Cricket", "Football", "Kabaddi", "Badminton"],
        )

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
    @patch("apps.agents.langchain_tools._build_goal_state_chain")
    def test_invoke_goal_state_regrounds_incorrect_movie_summary_for_sports_search(self, build_goal_state_chain_mock):
        build_goal_state_chain_mock.return_value.invoke.return_value = GoalState(
            goal_type="search",
            goal_stage="awaiting_clarification",
            goal_summary="Movies in Dharamshala",
            last_open_question="What movie or genre are you interested in?",
        )

        goal_state = invoke_goal_state(
            user_message="Show me sports in Dharamshala",
            assistant_message="I found sports options in Dharamshala.",
            active_filters={"event_types": ["sports"], "cities": ["Dharamshala"]},
            latest_result_context={
                "search_domains": ["sports"],
                "results": [
                    {
                        "listing_code": "SPT-1",
                        "title": "Punjab Kings vs Delhi Capitals",
                        "domain": "sports",
                        "city": "Dharamshala",
                        "sport_type": "Cricket",
                    }
                ],
            },
            pending_booking={},
            search_domains=["sports"],
            needs_clarification=False,
            clarification_question=None,
            booking_action=None,
            turn_policy_intent="task_continue",
            existing_goal_state={},
        )

        self.assertEqual(goal_state.goal_type, "search")
        self.assertEqual(goal_state.goal_summary, "Sports in Dharamshala")

    @patch("apps.agents.langchain_tools._build_goal_state_chain")
    def test_invoke_goal_state_prefers_selected_booking_event_summary(self, build_goal_state_chain_mock):
        build_goal_state_chain_mock.return_value.invoke.return_value = GoalState(
            goal_type="booking",
            goal_stage="awaiting_user_info",
            goal_summary="Sports in New Delhi",
            last_open_question="Please share your full name.",
        )

        goal_state = invoke_goal_state(
            user_message="book this one",
            assistant_message="Please share your full name to complete the booking.",
            active_filters={"event_types": ["sports"], "cities": ["New Delhi"], "sport_types": ["Cricket"]},
            latest_result_context={
                "search_domains": ["sports"],
                "results": [],
            },
            pending_booking={
                "listing_code": "SPT-IPL-035",
                "awaiting_field": "name",
                "event_snapshot": {
                    "listing_code": "SPT-IPL-035",
                    "title": "Punjab Kings vs Delhi Capitals",
                    "domain": "sports",
                    "city": "New Delhi",
                    "venue_name": "Arun Jaitley Stadium",
                    "event_date": "2026-04-25",
                },
            },
            search_domains=["sports"],
            needs_clarification=False,
            clarification_question=None,
            booking_action="awaiting_user_info",
            turn_policy_intent="task_continue",
            existing_goal_state={},
        )

        self.assertEqual(goal_state.goal_type, "booking")
        self.assertEqual(
            goal_state.goal_summary,
            "Book Punjab Kings vs Delhi Capitals match in New Delhi at Arun Jaitley Stadium on 2026-04-25",
        )

    @patch("apps.agents.services.generate_dynamic_thread_title")
    def test_update_dynamic_thread_title_prefers_goal_summary_over_recent_messages(
        self,
        generate_dynamic_thread_title_mock,
    ):
        thread = ChatThread.objects.create(
            title="Old title",
            metadata={
                "goal_state": {
                    "goal_type": "search",
                    "goal_stage": "browsing_results",
                    "goal_summary": "Football matches in Mumbai",
                    "last_open_question": "Do you want this weekend or next week?",
                }
            },
        )

        _update_dynamic_thread_title(thread)

        thread.refresh_from_db()
        self.assertEqual(thread.title, "Football matches in Mumbai")
        generate_dynamic_thread_title_mock.assert_not_called()

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
            languages=["Hindi"],
            sport_types=["Cricket"],
            teams=["Delhi Capitals"],
        )
        updates = ActiveFilters(event_types=["movies"])

        result = _derive_filters_to_clear(current_filters=current_filters, updates=updates)

        self.assertIn("sport_types", result)
        self.assertIn("teams", result)
        self.assertIn("venue_names", result)
        self.assertIn("languages", result)

    @patch("apps.agents.langchain_tools.invoke_sport_filter_resolver")
    @patch("apps.agents.langchain_tools.invoke_movie_filter_resolver")
    @patch("apps.agents.langchain_tools.invoke_sport_catalog_inquiry")
    @patch("apps.agents.langchain_tools.invoke_temporal_resolver")
    @patch("apps.agents.langchain_tools.invoke_location_resolver")
    @patch("apps.agents.langchain_tools.invoke_event_type_resolver")
    def test_resolve_turn_filters_prefers_same_domain_sport_correction_over_event_type_issue(
        self,
        event_type_resolver_mock,
        location_resolver_mock,
        temporal_resolver_mock,
        sport_catalog_inquiry_mock,
        movie_filter_resolver_mock,
        sport_filter_resolver_mock,
    ):
        event_type_resolver_mock.return_value = FilterResolution(
            status="no_match",
            message="Cricket is not available as an event type.",
        )
        location_resolver_mock.return_value = FilterResolution(status="no_input")
        temporal_resolver_mock.return_value = FilterResolution(status="no_input")
        sport_catalog_inquiry_mock.return_value = CatalogInquiry(status="no_input")
        movie_filter_resolver_mock.return_value = FilterResolution(status="no_input")
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

    @patch("apps.agents.langchain_tools.invoke_sport_filter_resolver")
    @patch("apps.agents.langchain_tools.invoke_movie_filter_resolver")
    @patch("apps.agents.langchain_tools.invoke_temporal_resolver")
    @patch("apps.agents.langchain_tools.invoke_location_resolver")
    @patch("apps.agents.langchain_tools.invoke_event_type_resolver")
    def test_resolve_turn_filters_infers_sports_domain_from_specific_filter_when_event_type_is_missing(
        self,
        event_type_resolver_mock,
        location_resolver_mock,
        temporal_resolver_mock,
        movie_filter_resolver_mock,
        sport_filter_resolver_mock,
    ):
        event_type_resolver_mock.return_value = FilterResolution(status="no_input")
        movie_filter_resolver_mock.return_value = FilterResolution(status="no_input")
        sport_filter_resolver_mock.return_value = FilterResolution(
            status="resolved",
            message="Resolved sport type.",
            active_filters_partial=ActiveFilters(sport_types=["Cricket"]),
        )
        location_resolver_mock.return_value = FilterResolution(
            status="resolved",
            message="Resolved location.",
            active_filters_partial=ActiveFilters(cities=["Mumbai"]),
        )
        temporal_resolver_mock.return_value = FilterResolution(
            status="resolved",
            message="Resolved date.",
            active_filters_partial=ActiveFilters(event_dates=["2026-04-12"]),
        )

        result = resolve_turn_filters(
            user_message="is there a cricket event this sunday in Mumbai?",
            current_filters=ActiveFilters(),
            reference_date="2026-04-09",
        )

        self.assertEqual(result.updates.event_types, ["sports"])
        self.assertEqual(result.updates.sport_types, ["Cricket"])
        self.assertEqual(result.updates.cities, ["Mumbai"])
        self.assertEqual(result.updates.event_dates, ["2026-04-12"])
        location_resolver_mock.assert_called_once()
        self.assertEqual(
            location_resolver_mock.call_args.args,
            ("is there a cricket event this sunday in Mumbai?", ["sports"], ActiveFilters()),
        )

    @patch("apps.agents.langchain_tools.invoke_sport_filter_resolver")
    @patch("apps.agents.langchain_tools.invoke_movie_filter_resolver")
    @patch("apps.agents.langchain_tools.invoke_temporal_resolver")
    @patch("apps.agents.langchain_tools.invoke_location_resolver")
    @patch("apps.agents.langchain_tools.invoke_event_type_resolver")
    def test_resolve_turn_filters_infers_movie_domain_from_specific_filter_when_event_type_is_missing(
        self,
        event_type_resolver_mock,
        location_resolver_mock,
        temporal_resolver_mock,
        movie_filter_resolver_mock,
        sport_filter_resolver_mock,
    ):
        event_type_resolver_mock.return_value = FilterResolution(status="no_input")
        movie_filter_resolver_mock.return_value = FilterResolution(
            status="resolved",
            message="Resolved movie venue.",
            active_filters_partial=ActiveFilters(venue_names=["PVR Phoenix"]),
        )
        sport_filter_resolver_mock.return_value = FilterResolution(status="no_input")
        location_resolver_mock.return_value = FilterResolution(status="no_input")
        temporal_resolver_mock.return_value = FilterResolution(status="no_input")

        result = resolve_turn_filters(
            user_message="in PVR Phoenix",
            current_filters=ActiveFilters(),
            reference_date="2026-04-09",
        )

        self.assertEqual(result.updates.event_types, ["movies"])
        self.assertEqual(result.updates.venue_names, ["PVR Phoenix"])
        location_resolver_mock.assert_called_once()
        self.assertEqual(
            location_resolver_mock.call_args.args,
            ("in PVR Phoenix", ["movies"], ActiveFilters()),
        )

    @patch("apps.agents.langchain_tools.invoke_sport_filter_resolver")
    @patch("apps.agents.langchain_tools.invoke_sport_catalog_inquiry")
    @patch("apps.agents.langchain_tools.invoke_movie_filter_resolver")
    @patch("apps.agents.langchain_tools.invoke_temporal_resolver")
    @patch("apps.agents.langchain_tools.invoke_location_resolver")
    @patch("apps.agents.langchain_tools.invoke_event_type_resolver")
    def test_resolve_turn_filters_collects_clear_fields_from_location_and_temporal_resolvers(
        self,
        event_type_resolver_mock,
        location_resolver_mock,
        temporal_resolver_mock,
        movie_filter_resolver_mock,
        sport_catalog_inquiry_mock,
        sport_filter_resolver_mock,
    ):
        current_filters = ActiveFilters(
            event_types=["sports"],
            cities=["Mumbai"],
            event_dates=["2026-04-12"],
            sport_types=["Cricket"],
        )
        event_type_resolver_mock.return_value = FilterResolution(status="no_input")
        location_resolver_mock.return_value = FilterResolution(
            status="resolved",
            clear_fields=["cities"],
        )
        temporal_resolver_mock.return_value = FilterResolution(
            status="resolved",
            clear_fields=["event_dates"],
            active_filters_partial=ActiveFilters(date_from="2026-04-07", date_to="2026-04-12"),
        )
        movie_filter_resolver_mock.return_value = FilterResolution(status="no_input")
        sport_catalog_inquiry_mock.return_value = CatalogInquiry(status="no_input")
        sport_filter_resolver_mock.return_value = FilterResolution(status="no_input")

        result = resolve_turn_filters(
            user_message="remove the mumbai filter and show matches this week",
            current_filters=current_filters,
            reference_date="2026-04-09",
        )

        self.assertEqual(result.clear_fields, ["cities", "event_dates"])
        self.assertEqual(result.updates.date_from, "2026-04-07")
        self.assertEqual(result.updates.date_to, "2026-04-12")

    @patch("apps.agents.langchain_tools.invoke_sport_filter_resolver")
    @patch("apps.agents.langchain_tools.invoke_sport_catalog_inquiry")
    @patch("apps.agents.langchain_tools.invoke_movie_filter_resolver")
    @patch("apps.agents.langchain_tools.invoke_temporal_resolver")
    @patch("apps.agents.langchain_tools.invoke_location_resolver")
    @patch("apps.agents.langchain_tools.invoke_event_type_resolver")
    def test_resolve_turn_filters_clears_current_city_for_outside_location_follow_up(
        self,
        event_type_resolver_mock,
        location_resolver_mock,
        temporal_resolver_mock,
        movie_filter_resolver_mock,
        sport_catalog_inquiry_mock,
        sport_filter_resolver_mock,
    ):
        current_filters = ActiveFilters(
            event_types=["sports"],
            cities=["Mumbai"],
            event_dates=["2026-04-12"],
            sport_types=["Cricket"],
        )
        event_type_resolver_mock.return_value = FilterResolution(status="no_input")
        location_resolver_mock.return_value = FilterResolution(status="no_input")
        temporal_resolver_mock.return_value = FilterResolution(status="no_input")
        movie_filter_resolver_mock.return_value = FilterResolution(status="no_input")
        sport_catalog_inquiry_mock.return_value = CatalogInquiry(status="no_input")
        sport_filter_resolver_mock.return_value = FilterResolution(status="no_input")

        result = resolve_turn_filters(
            user_message="what matches are there on sunday that are outside mumbai?",
            current_filters=current_filters,
            reference_date="2026-04-09",
        )

        self.assertEqual(result.clear_fields, ["cities"])

    @patch("apps.agents.langchain_tools.invoke_sport_filter_resolver")
    @patch("apps.agents.langchain_tools.invoke_sport_catalog_inquiry")
    @patch("apps.agents.langchain_tools.invoke_movie_filter_resolver")
    @patch("apps.agents.langchain_tools.invoke_temporal_resolver")
    @patch("apps.agents.langchain_tools.invoke_location_resolver")
    @patch("apps.agents.langchain_tools.invoke_event_type_resolver")
    def test_resolve_turn_filters_clears_city_for_all_cities_follow_up_without_widening_domain(
        self,
        event_type_resolver_mock,
        location_resolver_mock,
        temporal_resolver_mock,
        movie_filter_resolver_mock,
        sport_catalog_inquiry_mock,
        sport_filter_resolver_mock,
    ):
        current_filters = ActiveFilters(
            event_types=["sports"],
            cities=["Mumbai"],
            date_from="2026-04-20",
            date_to="2026-04-26",
            sport_types=["Cricket"],
        )
        event_type_resolver_mock.return_value = FilterResolution(status="no_input")
        location_resolver_mock.return_value = FilterResolution(status="resolved", clear_fields=["cities"])
        temporal_resolver_mock.return_value = FilterResolution(status="no_input")
        movie_filter_resolver_mock.return_value = FilterResolution(status="no_input")
        sport_catalog_inquiry_mock.return_value = CatalogInquiry(status="no_input")
        sport_filter_resolver_mock.return_value = FilterResolution(status="no_input")

        result = resolve_turn_filters(
            user_message="in all cities, not just mumbai",
            current_filters=current_filters,
            reference_date="2026-04-13",
        )

        self.assertEqual(result.clear_fields, ["cities"])
        self.assertEqual(result.updates.event_types, [])
        self.assertEqual(result.updates.sport_types, [])

    @patch("apps.agents.langchain_tools.invoke_sport_filter_resolver")
    @patch("apps.agents.langchain_tools.invoke_sport_catalog_inquiry")
    @patch("apps.agents.langchain_tools.invoke_movie_filter_resolver")
    @patch("apps.agents.langchain_tools.invoke_temporal_resolver")
    @patch("apps.agents.langchain_tools.invoke_location_resolver")
    @patch("apps.agents.langchain_tools.invoke_event_type_resolver")
    def test_resolve_turn_filters_does_not_run_sport_catalog_inquiry_for_temporal_follow_up(
        self,
        event_type_resolver_mock,
        location_resolver_mock,
        temporal_resolver_mock,
        movie_filter_resolver_mock,
        sport_catalog_inquiry_mock,
        sport_filter_resolver_mock,
    ):
        current_filters = ActiveFilters(
            event_types=["sports"],
            event_dates=["2026-04-12"],
            sport_types=["Cricket"],
        )
        event_type_resolver_mock.return_value = FilterResolution(status="no_input")
        location_resolver_mock.return_value = FilterResolution(status="no_input")
        temporal_resolver_mock.return_value = FilterResolution(
            status="resolved",
            clear_fields=["event_dates"],
            active_filters_partial=ActiveFilters(date_from="2026-04-06", date_to="2026-04-11"),
        )
        movie_filter_resolver_mock.return_value = FilterResolution(status="no_input")
        sport_filter_resolver_mock.return_value = FilterResolution(status="no_input")

        result = resolve_turn_filters(
            user_message="not on sunday but this week?",
            current_filters=current_filters,
            reference_date="2026-04-09",
        )

        sport_catalog_inquiry_mock.assert_not_called()
        self.assertEqual(result.clear_fields, ["event_dates"])
        self.assertEqual(result.updates.date_from, "2026-04-06")
        self.assertEqual(result.updates.date_to, "2026-04-11")
        self.assertEqual(result.updates.sport_types, [])

    def test_sanitize_temporal_resolution_clears_conflicting_temporal_mode_fields(self):
        from apps.agents.langchain_tools import _sanitize_temporal_resolution

        resolution = FilterResolution(
            status="resolved",
            active_filters_partial=ActiveFilters(
                event_dates=["2026-04-12"],
                date_from="2026-04-07",
                date_to="2026-04-12",
            ),
        )

        result = _sanitize_temporal_resolution(resolution)

        self.assertEqual(result.active_filters_partial.event_dates, ["2026-04-12"])
        self.assertIsNone(result.active_filters_partial.date_from)
        self.assertIsNone(result.active_filters_partial.date_to)
        self.assertEqual(result.clear_fields, ["date_from", "date_to"])

    @patch("apps.agents.langchain_tools.invoke_sport_filter_resolver")
    @patch("apps.agents.langchain_tools.invoke_sport_catalog_inquiry")
    @patch("apps.agents.langchain_tools.invoke_temporal_resolver")
    @patch("apps.agents.langchain_tools.invoke_location_resolver")
    @patch("apps.agents.langchain_tools.invoke_event_type_resolver")
    def test_resolve_turn_filters_keeps_catalog_inquiry_out_of_saved_filters(
        self,
        event_type_resolver_mock,
        location_resolver_mock,
        temporal_resolver_mock,
        sport_catalog_inquiry_mock,
        sport_filter_resolver_mock,
    ):
        event_type_resolver_mock.return_value = FilterResolution(status="no_input")
        location_resolver_mock.return_value = FilterResolution(status="no_input")
        temporal_resolver_mock.return_value = FilterResolution(status="no_input")
        sport_catalog_inquiry_mock.return_value = CatalogInquiry(
            status="answer",
            inquiry_key="sport_types",
            listed_values=["Badminton", "Cricket", "Football", "Kabaddi"],
        )

        result = resolve_turn_filters(
            user_message="what other sports do you have?",
            current_filters=ActiveFilters(event_types=["sports"], event_dates=["2026-04-12"]),
            reference_date="2026-04-09",
        )

        self.assertEqual(
            result.updates.sport_types,
            ["Badminton", "Cricket", "Football", "Kabaddi"],
        )
        sport_filter_resolver_mock.assert_not_called()

    @patch("apps.agents.langchain_tools.invoke_sport_filter_resolver")
    @patch("apps.agents.langchain_tools.invoke_sport_catalog_inquiry")
    @patch("apps.agents.langchain_tools.invoke_temporal_resolver")
    @patch("apps.agents.langchain_tools.invoke_location_resolver")
    @patch("apps.agents.langchain_tools.invoke_event_type_resolver")
    def test_resolve_turn_filters_skips_catalog_inquiry_on_explicit_domain_switch(
        self,
        event_type_resolver_mock,
        location_resolver_mock,
        temporal_resolver_mock,
        sport_catalog_inquiry_mock,
        sport_filter_resolver_mock,
    ):
        event_type_resolver_mock.return_value = FilterResolution(
            status="resolved",
            message="Resolved event type.",
            active_filters_partial=ActiveFilters(event_types=["sports"]),
        )
        location_resolver_mock.return_value = FilterResolution(status="no_input")
        temporal_resolver_mock.return_value = FilterResolution(status="no_input")
        sport_filter_resolver_mock.return_value = FilterResolution(status="no_input")

        result = resolve_turn_filters(
            user_message="show sports instead",
            current_filters=ActiveFilters(event_types=["movies"], cities=["Mumbai"], languages=["Hindi"]),
            reference_date="2026-04-09",
        )

        self.assertEqual(result.updates.event_types, ["sports"])
        self.assertEqual(result.updates.sport_types, [])
        sport_catalog_inquiry_mock.assert_not_called()

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


class BookingStateTests(TestCase):
    def test_mark_and_confirm_pending_thread_booking(self):
        thread = ChatThread.objects.create(title="Booking thread")
        thread_filter = ThreadFilter.objects.create(
            thread=thread,
            active_filters={"event_types": ["sports"], "cities": ["Mumbai"]},
            latest_result_context={
                "thread_id": str(thread.id),
                "search_domains": ["sports"],
                "results": [
                    {
                        "position": 1,
                        "listing_code": "SPT-BOOK-1",
                        "title": "Royal Challengers Bengaluru vs Mumbai Indians",
                        "city": "Mumbai",
                        "venue_name": "Wankhede Stadium",
                        "event_date": "2026-04-12",
                        "start_at": "2026-04-12T19:30:00+05:30",
                    }
                ],
            },
        )
        starts_at = timezone.make_aware(datetime(2026, 4, 12, 19, 30))
        SportEvent.objects.create(
            listing_code="SPT-BOOK-1",
            title="Royal Challengers Bengaluru vs Mumbai Indians",
            event_date=starts_at.date(),
            start_at=starts_at,
            city="Mumbai",
            venue_name="Wankhede Stadium",
            sport_type="Cricket",
            tournament_name="Indian Premier League",
            home_team="Royal Challengers Bengaluru",
            away_team="Mumbai Indians",
            participant_names=["Royal Challengers Bengaluru", "Mumbai Indians"],
        )

        pending_booking = mark_thread_pending_booking(thread_filter=thread_filter, listing_code="SPT-BOOK-1")
        self.assertEqual(pending_booking["listing_code"], "SPT-BOOK-1")

        first_attempt = attempt_thread_pending_booking_confirmation(
            thread=thread,
            thread_filter=thread_filter,
            confirmed_via="test",
            append_confirmation_message=False,
        )
        self.assertEqual(first_attempt["status"], "missing_user_info")
        save_thread_booking_user_info(thread_filter=thread_filter, field_name="name", value="Nandan Kumar")
        save_thread_booking_user_info(thread_filter=thread_filter, field_name="email", value="nandan@example.com")
        save_thread_booking_user_info(thread_filter=thread_filter, field_name="contact_number", value="+91 9876543210")
        final_attempt = attempt_thread_pending_booking_confirmation(
            thread=thread,
            thread_filter=thread_filter,
            confirmed_via="test",
            append_confirmation_message=False,
        )

        self.assertEqual(Booking.objects.count(), 1)
        self.assertEqual(final_attempt["status"], "confirmed")
        self.assertEqual(Booking.objects.get().event_title, "Royal Challengers Bengaluru vs Mumbai Indians")
        thread_filter.refresh_from_db()
        self.assertEqual(thread_filter.pending_booking, {})

    def test_select_thread_pending_booking_preserves_existing_customer_info(self):
        thread = ChatThread.objects.create(title="Booking thread")
        thread_filter = ThreadFilter.objects.create(
            thread=thread,
            latest_result_context={
                "thread_id": str(thread.id),
                "search_domains": ["sports"],
                "results": [
                    {
                        "position": 1,
                        "domain": "sports",
                        "listing_code": "SPT-BOOK-1",
                        "title": "Mumbai Match",
                        "city": "Mumbai",
                        "venue_name": "Wankhede Stadium",
                        "event_date": "2026-04-12",
                        "start_at": "2026-04-12T19:30:00+05:30",
                    },
                    {
                        "position": 2,
                        "domain": "sports",
                        "listing_code": "SPT-BOOK-2",
                        "title": "Delhi Match",
                        "city": "New Delhi",
                        "venue_name": "Arun Jaitley Stadium",
                        "event_date": "2026-04-13",
                        "start_at": "2026-04-13T19:30:00+05:30",
                    },
                ],
            },
            pending_booking={
                "status": "awaiting_user_info",
                "listing_code": "SPT-BOOK-1",
                "awaiting_field": "contact_number",
                "customer_info": {
                    "name": "Nandan Kumar",
                    "email": "nandan@example.com",
                    "contact_number": "",
                },
                "event_snapshot": {"listing_code": "SPT-BOOK-1", "title": "Mumbai Match"},
            },
        )

        result = select_thread_pending_booking(thread_filter=thread_filter, listing_code="SPT-BOOK-2")

        self.assertEqual(result["pending_booking"]["listing_code"], "SPT-BOOK-2")
        self.assertEqual(
            result["pending_booking"]["customer_info"],
            {
                "name": "Nandan Kumar",
                "email": "nandan@example.com",
                "contact_number": "",
            },
        )


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
