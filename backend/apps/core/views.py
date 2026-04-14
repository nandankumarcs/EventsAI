from django.db import connection
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from apps.core.ttl_cache import cache


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
