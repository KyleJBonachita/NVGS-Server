"""Verification for short-lived login assertions issued by Google Apps Script."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email


class BridgeTokenError(ValueError):
    """Raised when an Apps Script bridge token cannot be trusted."""


@dataclass(frozen=True)
class BridgeIdentity:
    email: str
    nonce: str


def _decode_segment(segment: str) -> bytes:
    if not segment or len(segment) > 4096:
        raise BridgeTokenError("Invalid token encoding.")
    try:
        raw = segment.encode("ascii")
    except UnicodeEncodeError as exc:
        raise BridgeTokenError("Invalid token encoding.") from exc
    padding = b"=" * (-len(raw) % 4)
    try:
        return base64.b64decode(
            raw + padding,
            altchars=b"-_",
            validate=True,
        )
    except (ValueError, binascii.Error) as exc:
        raise BridgeTokenError("Invalid token encoding.") from exc


def _decode_json(segment: str) -> dict[str, Any]:
    try:
        value = json.loads(_decode_segment(segment).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BridgeTokenError("Invalid token data.") from exc
    if not isinstance(value, dict):
        raise BridgeTokenError("Invalid token data.")
    return value


def _integer_claim(payload: dict[str, Any], name: str) -> int:
    value = payload.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise BridgeTokenError(f"Invalid {name} claim.")
    return value


def verify_bridge_token(
    token: str,
    expected_state: str,
    *,
    now: int | None = None,
) -> BridgeIdentity:
    if not isinstance(token, str) or len(token) > 8192:
        raise BridgeTokenError("Invalid login token.")

    parts = token.split(".")
    if len(parts) != 3:
        raise BridgeTokenError("Invalid login token.")
    header_segment, payload_segment, signature_segment = parts

    header = _decode_json(header_segment)
    if header.get("alg") != "HS256" or header.get("typ") != "JWT":
        raise BridgeTokenError("Unsupported login token.")

    try:
        signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    except UnicodeEncodeError as exc:
        raise BridgeTokenError("Invalid token encoding.") from exc
    expected_signature = hmac.new(
        settings.APPSCRIPT_SSO_SECRET.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    actual_signature = _decode_segment(signature_segment)
    if not hmac.compare_digest(actual_signature, expected_signature):
        raise BridgeTokenError("Invalid login signature.")

    payload = _decode_json(payload_segment)
    if payload.get("iss") != settings.APPSCRIPT_SSO_ISSUER:
        raise BridgeTokenError("Invalid login issuer.")
    if payload.get("aud") != settings.APPSCRIPT_SSO_AUDIENCE:
        raise BridgeTokenError("Invalid login audience.")

    current_time = int(time.time()) if now is None else now
    issued_at = _integer_claim(payload, "iat")
    expires_at = _integer_claim(payload, "exp")
    ttl = settings.APPSCRIPT_SSO_TOKEN_TTL_SECONDS
    skew = settings.APPSCRIPT_SSO_CLOCK_SKEW_SECONDS
    if expires_at <= issued_at or expires_at - issued_at > ttl:
        raise BridgeTokenError("Invalid login lifetime.")
    if issued_at > current_time + skew:
        raise BridgeTokenError("Login token is not active yet.")
    if issued_at < current_time - ttl - skew:
        raise BridgeTokenError("Login token is too old.")
    if expires_at < current_time - skew:
        raise BridgeTokenError("Login token has expired.")

    state = payload.get("state")
    if (
        not isinstance(expected_state, str)
        or not isinstance(state, str)
        or not hmac.compare_digest(state, expected_state)
    ):
        raise BridgeTokenError("Login state did not match this browser.")

    email = payload.get("email")
    subject = payload.get("sub")
    if not isinstance(email, str):
        raise BridgeTokenError("Login email was missing.")
    email = email.strip().lower()
    if subject != email:
        raise BridgeTokenError("Login subject did not match the email.")
    try:
        validate_email(email)
    except ValidationError as exc:
        raise BridgeTokenError("Login email was invalid.") from exc

    domain = email.rsplit("@", 1)[-1]
    if settings.ALLOWED_EMAIL_DOMAINS and domain not in settings.ALLOWED_EMAIL_DOMAINS:
        raise BridgeTokenError("Login email domain was not approved.")

    nonce = payload.get("nonce")
    if not isinstance(nonce, str) or not 16 <= len(nonce) <= 128:
        raise BridgeTokenError("Login nonce was invalid.")
    return BridgeIdentity(email=email, nonce=nonce)
