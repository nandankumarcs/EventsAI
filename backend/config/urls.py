from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.core.urls")),
    path("api/chats/", include("apps.chats.urls")),
    path("api/events/", include("apps.events.urls")),
    path("api/agents/", include("apps.agents.urls")),
    path("api/bookings/", include("apps.bookings.urls")),
]
