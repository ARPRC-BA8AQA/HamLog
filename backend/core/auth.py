import base64
import hashlib
import hmac
import json
import secrets
import time
from flask import current_app


def _encode(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _secret():
    return current_app.config["HAMLOG_CONFIG"]["auth"].get("jwt_secret", "")


def issue_token(identity, role, token_type="access"):
    now = int(time.time())
    auth = current_app.config["HAMLOG_CONFIG"]["auth"]
    expires = auth.get("refresh_token_expires", 604800) if token_type == "refresh" else auth.get("access_token_expires", 7200)
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": identity, "role": role, "type": token_type, "iat": now, "exp": now + int(expires), "jti": secrets.token_urlsafe(12)}
    encoded_header = _encode(json.dumps(header, separators=(",", ":")).encode())
    encoded_payload = _encode(json.dumps(payload, separators=(",", ":")).encode())
    unsigned = f"{encoded_header}.{encoded_payload}"
    signature = hmac.new(_secret().encode(), unsigned.encode(), hashlib.sha256).digest()
    return f"{unsigned}.{_encode(signature)}"


def decode_token(token, expected_type="access"):
    try:
        header, encoded_payload, encoded_signature = token.split(".")
        unsigned = f"{header}.{encoded_payload}"
        expected = hmac.new(_secret().encode(), unsigned.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _decode(encoded_signature)):
            return None
        payload = json.loads(_decode(encoded_payload))
        if payload.get("type") != expected_type or int(payload.get("exp", 0)) <= int(time.time()):
            return None
        if payload.get("jti") in current_app.extensions.setdefault("revoked_tokens", set()):
            return None
        return payload
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def revoke_token(token):
    payload = decode_token(token, expected_type="access") or decode_token(token, expected_type="refresh")
    if payload:
        current_app.extensions.setdefault("revoked_tokens", set()).add(payload["jti"])
