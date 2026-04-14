from django.urls import path

from apps.core.views import health_check, reset_node_cache

app_name = "core"

urlpatterns = [
    path("health/", health_check, name="health-check"),
    path("cache/reset/", reset_node_cache, name="cache-reset"),
]
