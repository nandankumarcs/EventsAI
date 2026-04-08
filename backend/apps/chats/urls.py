from django.urls import path

from apps.chats.views import thread_detail_view, thread_list_create_view

app_name = "chats"

urlpatterns = [
    path("threads/", thread_list_create_view, name="thread-list-create"),
    path("threads/<uuid:thread_id>/", thread_detail_view, name="thread-detail"),
]
