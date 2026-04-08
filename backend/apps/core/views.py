from django.db import connection
from django.http import JsonResponse
from django.utils import timezone


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
            "service": "attend-backend",
            "timestamp": timezone.now().isoformat(),
            "database": database,
        }
    )

# Create your views here.
