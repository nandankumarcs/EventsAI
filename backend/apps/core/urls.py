from django.urls import path

from apps.core.views import health_check, login_view, logout_view, reset_node_cache

app_name = "core"

urlpatterns = [
    path("health/", health_check, name="health-check"),
    path("auth/login/", login_view, name="auth-login"),
    path("auth/logout/", logout_view, name="auth-logout"),
    path("cache/reset/", reset_node_cache, name="cache-reset"),
]
