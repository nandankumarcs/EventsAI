from django.db import connection
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils.crypto import constant_time_compare
import json

from apps.core.ttl_cache import cache
from apps.core.auth import AUTH_COOKIE_NAME, get_expected_password, issue_auth_token


def health_check(request):
    database = {
        "configured": connection.settings_dict.get("ENGINE") != "django.db.backends.sqlite3",
        "engine": connection.settings_dict.get("ENGINE"),
        "reachable": False,
    }

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        database["reachable"] = True
    except Exception as exc:  # pragma: no cover - surfaced in live verification
        database["detail"] = str(exc)

    status = "ok" if database["reachable"] else "degraded"

    return JsonResponse(
        {
            "status": status,
            "service": "eventsai-backend",
            "timestamp": timezone.now().isoformat(),
            "database": database,
        }
    )


@csrf_exempt
@require_POST
def login_view(request):
    expected = get_expected_password()
    if not expected:
        return JsonResponse({"error": "Server auth not configured"}, status=500)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        payload = {}

    password = (payload.get("password") or "").strip()
    if not password or not constant_time_compare(password, expected):
        return JsonResponse({"error": "Invalid password"}, status=401)

    token = issue_auth_token()
    response = JsonResponse({"success": True})
    response.set_cookie(
        AUTH_COOKIE_NAME,
        token,
        httponly=True,
        samesite="Lax",
        secure=False,
        path="/",
    )
    return response


@csrf_exempt
@require_POST
def logout_view(request):
    response = JsonResponse({"success": True})
    response.delete_cookie(AUTH_COOKIE_NAME, path="/")
    return response


@csrf_exempt
def reset_node_cache(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    before = cache.stats()
    cache.clear()
    after = cache.stats()
    return JsonResponse(
        {
            "status": "ok",
            "cache": "ttl_cache",
            "before": before.__dict__,
            "after": after.__dict__,
        }
    )

# Create your views here.
