from pathlib import Path

from django.conf import settings
from django.contrib import admin
from django.http import FileResponse, HttpResponse
from django.urls import include, path, re_path


def serve_react(request, *args, **kwargs):
    """Catch-all: serve the React SPA index.html for any non-API route."""
    index_file = Path(settings.FRONTEND_DIR) / "index.html"
    return HttpResponse(
        index_file.read_bytes(),
        content_type="text/html; charset=utf-8",
    )


def serve_root_file(request, filename):
    """Serve static files placed at the root of the dist folder (e.g. favicon.svg)."""
    file_path = Path(settings.FRONTEND_DIR) / filename
    if file_path.exists() and file_path.is_file():
        return FileResponse(open(file_path, "rb"))
    return HttpResponse(status=404)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.core.urls")),
    path("api/chats/", include("apps.chats.urls")),
    path("api/events/", include("apps.events.urls")),
    path("api/agents/", include("apps.agents.urls")),
    path("api/bookings/", include("apps.bookings.urls")),
    # Root-level static files from the dist folder (favicon, icons, etc.)
    re_path(r"^(?P<filename>[\w.-]+\.\w+)$", serve_root_file),
    # SPA catch-all — must be last
    re_path(r"^.*$", serve_react),
]
