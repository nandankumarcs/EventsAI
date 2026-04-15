from __future__ import annotations

from dataclasses import dataclass

from django.http import HttpRequest, JsonResponse

from apps.core.auth import AUTH_COOKIE_NAME, verify_auth_token


@dataclass(frozen=True)
class PasswordCookieAuthMiddleware:
    get_response: callable

    def __call__(self, request: HttpRequest):
        path = request.path or ""

        if request.method == "OPTIONS":
            return self.get_response(request)

        if not path.startswith("/api/"):
            return self.get_response(request)

        if path in {"/api/health/", "/api/auth/login/", "/api/auth/logout/"}:
            return self.get_response(request)

        token = request.COOKIES.get(AUTH_COOKIE_NAME, "")
        if token and verify_auth_token(token):
            return self.get_response(request)

        return JsonResponse({"error": "Authentication required"}, status=401)
