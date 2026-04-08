import json

from django.test import TestCase

from apps.chats.models import ChatMessage, ChatThread, ThreadFilter


class ChatThreadApiTests(TestCase):
    def test_thread_list_returns_saved_threads_with_filter_state(self):
        thread = ChatThread.objects.create(
            title="Weekend sports",
            last_message_preview="Show me cricket in Delhi",
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
        self.assertEqual(payload["threads"][0]["active_filters"]["cities"], ["New Delhi"])

    def test_thread_create_creates_empty_filter_state(self):
        response = self.client.post(
            "/api/chats/threads/",
            data=json.dumps({"title": "Fresh thread"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        thread_id = response.json()["thread"]["id"]
        self.assertTrue(ThreadFilter.objects.filter(thread_id=thread_id).exists())

    def test_thread_detail_returns_messages_in_order(self):
        thread = ChatThread.objects.create(title="Movie hunt")
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
