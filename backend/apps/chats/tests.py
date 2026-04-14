import json
from unittest.mock import patch

from django.test import TestCase

from apps.chats.models import ChatMessage, ChatThread, ThreadFilter


class ChatThreadApiTests(TestCase):
    def test_thread_list_returns_saved_threads_with_filter_state(self):
        thread = ChatThread.objects.create(
            title="Weekend sports",
            last_message_preview="Show me cricket in Delhi",
            metadata={
                "goal_state": {
                    "goal_type": "search",
                    "goal_stage": "browsing_results",
                    "goal_summary": "Cricket in New Delhi",
                    "last_open_question": "Do you want this weekend?",
                }
            },
        )
        ThreadFilter.objects.create(
            thread=thread,
            active_filters={"event_types": ["sports"], "cities": ["New Delhi"]},
        )
        ChatMessage.objects.create(
            thread=thread,
            position=1,
            role=ChatMessage.Role.USER,
            content="Show me cricket in Delhi",
        )

        response = self.client.get("/api/chats/threads/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["threads"][0]["title"], "Weekend sports")
        self.assertEqual(payload["threads"][0]["mode"], "unknown")
        self.assertEqual(payload["threads"][0]["active_filters"]["cities"], ["New Delhi"])
        self.assertEqual(payload["threads"][0]["goal_state"]["goal_summary"], "Cricket in New Delhi")

    def test_thread_create_creates_empty_filter_state(self):
        response = self.client.post(
            "/api/chats/threads/",
            data=json.dumps({"title": "Fresh thread"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        created_thread = response.json()["thread"]
        thread_id = created_thread["id"]
        self.assertEqual(created_thread["mode"], "unknown")
        self.assertTrue(ThreadFilter.objects.filter(thread_id=thread_id).exists())

    def test_thread_detail_returns_messages_in_order(self):
        thread = ChatThread.objects.create(
            title="Movie hunt",
            metadata={
                "goal_state": {
                    "goal_type": "search",
                    "goal_stage": "awaiting_clarification",
                    "goal_summary": "Movie options in Mumbai",
                    "last_open_question": "Do you want Hindi or English movies?",
                }
            },
        )
        ThreadFilter.objects.create(thread=thread, active_filters={"event_types": ["movies"]})
        ChatMessage.objects.create(
            thread=thread,
            position=1,
            role=ChatMessage.Role.USER,
            content="Show movies in Mumbai",
        )
        ChatMessage.objects.create(
            thread=thread,
            position=2,
            role=ChatMessage.Role.ASSISTANT,
            content="Here are some options.",
        )

        response = self.client.get(f"/api/chats/threads/{thread.id}/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()["thread"]
        self.assertEqual(len(payload["messages"]), 2)
        self.assertEqual(payload["messages"][0]["position"], 1)
        self.assertEqual(payload["messages"][1]["role"], "assistant")
        self.assertEqual(payload["mode"], "unknown")
        self.assertEqual(payload["goal_state"]["goal_stage"], "awaiting_clarification")

    def test_deleted_thread_detail_returns_json_404(self):
        thread = ChatThread.objects.create(title="Deleted thread", status=ChatThread.Status.DELETED)
        ThreadFilter.objects.create(thread=thread)

        response = self.client.get(f"/api/chats/threads/{thread.id}/")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"error": "Thread not found"})

    @patch("apps.chats.views.process_unified_chat_turn")
    def test_chat_turn_endpoint_returns_unified_chat_payload(self, mock_process):
        mock_process.return_value = {
            "thread": {
                "id": "thread-1",
                "title": "Flights in May",
                "mode": "flights",
                "status": "active",
                "last_message_preview": "I found flight options.",
                "last_activity_at": "2026-04-14T12:00:00+00:00",
            },
            "assistant_message": {
                "id": "msg-1",
                "thread_id": "thread-1",
                "position": 2,
                "role": "assistant",
                "content": "I found flight options.",
                "metadata": {},
                "created_at": "2026-04-14T12:00:00+00:00",
            },
            "active_filters": {},
            "search_domains": ["flights"],
            "results_by_domain": {},
            "latest_result_context": {},
            "pending_booking": {},
            "needs_clarification": False,
            "clarification_question": None,
        }

        response = self.client.post(
            "/api/chats/chat/",
            data=json.dumps({"message": "Show flights Delhi to Mumbai"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["thread"]["mode"], "flights")
        self.assertEqual(payload["search_domains"], ["flights"])

    @patch("apps.chats.services.process_flight_chat_turn")
    @patch("apps.chats.services.invoke_thread_mode_decision")
    def test_unified_chat_sets_thread_mode_from_llm_router(self, mock_decision, mock_process_flight):
        from apps.chats.services import ThreadModeDecision, process_unified_chat_turn

        mock_decision.return_value = ThreadModeDecision(mode="flights", rationale="clear flight request")
        thread = ChatThread.objects.create(title="New thread", mode=ChatThread.Mode.UNKNOWN)
        ThreadFilter.objects.create(thread=thread)
        mock_process_flight.return_value = {"thread": {"id": str(thread.id), "mode": "flights"}}

        result = process_unified_chat_turn(user_message="Need flight from Delhi to Mumbai", thread_id=str(thread.id))
        thread.refresh_from_db()

        self.assertEqual(thread.mode, ChatThread.Mode.FLIGHTS)
        self.assertEqual(result["thread"]["mode"], "flights")

    @patch("apps.chats.services.process_chat_turn")
    @patch("apps.chats.services.invoke_thread_mode_decision")
    def test_unified_chat_switches_thread_mode_when_confident(self, mock_decision, mock_process_chat):
        from apps.chats.services import ThreadModeDecision, process_unified_chat_turn

        thread = ChatThread.objects.create(title="Flight thread", mode=ChatThread.Mode.FLIGHTS)
        ThreadFilter.objects.create(
            thread=thread,
            active_filters={"origin_city": "Delhi"},
            latest_result_context={"results": [{"domain": "flights", "listing_code": "F1"}]},
            pending_booking={"listing_code": "F1"},
        )

        mock_decision.return_value = ThreadModeDecision(
            mode="entertainment",
            rationale="user asked for movies",
            confidence=0.9,
        )
        mock_process_chat.return_value = {"thread": {"id": str(thread.id), "mode": "entertainment"}}

        result = process_unified_chat_turn(user_message="Show movies in Mumbai", thread_id=str(thread.id))
        thread.refresh_from_db()
        thread_filter = ThreadFilter.objects.get(thread=thread)

        self.assertEqual(thread.mode, ChatThread.Mode.ENTERTAINMENT)
        self.assertEqual(result["thread"]["mode"], "entertainment")
        self.assertEqual(thread_filter.active_filters, {})
        self.assertEqual(thread_filter.latest_result_context, {})
        self.assertEqual(thread_filter.pending_booking, {})
