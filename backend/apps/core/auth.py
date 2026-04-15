import os

from django.core.signing import BadSignature, SignatureExpired, TimestampSigner


AUTH_COOKIE_NAME = "eventsai_auth"
_AUTH_SALT = "eventsai-auth"
_AUTH_SIGNING_VALUE = "ok"
_AUTH_MAX_AGE_SECONDS = int(os.getenv("APP_AUTH_MAX_AGE_SECONDS", "86400"))


def get_expected_password() -> str:
    return os.getenv("APP_AUTH_PASSWORD", "")


def issue_auth_token() -> str:
    signer = TimestampSigner(salt=_AUTH_SALT)
    return signer.sign(_AUTH_SIGNING_VALUE)


def verify_auth_token(token: str) -> bool:
    signer = TimestampSigner(salt=_AUTH_SALT)
    try:
        value = signer.unsign(token, max_age=_AUTH_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return False
    return value == _AUTH_SIGNING_VALUE
