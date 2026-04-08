from django.urls import path

from apps.agents.views import chat_turn_view

app_name = "agents"

urlpatterns = [
    path("chat/", chat_turn_view, name="chat-turn"),
]
