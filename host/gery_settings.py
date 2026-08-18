"""Secure local configuration helpers for Gery AI settings."""

from __future__ import annotations

import hmac
import os
import stat
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit

DEFAULT_GERY_AI_BASE_URL = "http://host.docker.internal:1234"
DEFAULT_GERY_AI_MODEL = "meta-llama-3.1-8b-instruct"


@dataclass(frozen=True)
class GeryAISettings:
    base_url: str
    model: str
    ingestion_ai_enabled: bool
    live_ai_enabled: bool
    api_key_configured: bool = False


def _env_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_gery_ai_settings(
    env: Mapping[str, str],
    api_key_path: Path,
) -> GeryAISettings:
    try:
        api_key_configured = bool(api_key_path.read_text(encoding="utf-8").strip())
    except OSError:
        api_key_configured = False
    return GeryAISettings(
        base_url=env.get("GERY_AI_BASE_URL", DEFAULT_GERY_AI_BASE_URL).strip()
        or DEFAULT_GERY_AI_BASE_URL,
        model=env.get("GERY_AI_MODEL", DEFAULT_GERY_AI_MODEL).strip()
        or DEFAULT_GERY_AI_MODEL,
        ingestion_ai_enabled=_env_bool(env.get("GERY_INGESTION_AI_ENABLED", "false")),
        live_ai_enabled=_env_bool(env.get("GERY_ALLOW_LIVE_AI", "false")),
        api_key_configured=api_key_configured,
    )


def verify_gery_admin_token(provided: str, token_path: Path) -> bool:
    try:
        expected = token_path.read_text(encoding="utf-8").strip()
    except OSError:
        return False
    supplied = str(provided or "").strip()
    return bool(expected and supplied) and hmac.compare_digest(supplied, expected)


def validate_gery_ai_settings(settings: GeryAISettings) -> GeryAISettings:
    base_url = settings.base_url.strip().rstrip("/")
    model = settings.model.strip()
    parsed = urlsplit(base_url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "AI base URL must be a complete http:// or https:// address without "
            "credentials, query parameters, or a fragment."
        )
    if any(character.isspace() for character in base_url) or "#" in base_url:
        raise ValueError("AI base URL cannot contain spaces or #.")
    if not model or len(model) > 200:
        raise ValueError("AI model name must be between 1 and 200 characters.")
    if any(character.isspace() for character in model) or "#" in model:
        raise ValueError("AI model name cannot contain spaces or #.")
    return replace(settings, base_url=base_url, model=model)


def _updated_env_text(original: str, updates: Mapping[str, str]) -> str:
    remaining = dict(updates)
    output: list[str] = []
    for raw_line in original.splitlines():
        stripped = raw_line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in remaining:
                output.append(f"{key}={remaining.pop(key)}")
                continue
        output.append(raw_line)
    if remaining:
        if output and output[-1]:
            output.append("")
        output.extend(f"{key}={value}" for key, value in remaining.items())
    return "\n".join(output) + "\n"


def _atomic_write(path: Path, contents: str, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(contents)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.chmod(temporary_path, mode)
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def save_gery_ai_settings(
    settings: GeryAISettings,
    env_path: Path,
    api_key_path: Path,
    api_key_update: str | None = None,
) -> GeryAISettings:
    validated = validate_gery_ai_settings(settings)
    if api_key_update is not None:
        if "\n" in api_key_update or "\r" in api_key_update:
            raise ValueError("AI API key cannot contain line breaks.")
        if len(api_key_update) > 8192:
            raise ValueError("AI API key is too long.")

    try:
        original = env_path.read_text(encoding="utf-8")
        env_mode = stat.S_IMODE(env_path.stat().st_mode)
    except FileNotFoundError as exc:
        raise ValueError("The NVGS root .env file is missing.") from exc
    except OSError as exc:
        raise ValueError(f"The NVGS root .env file could not be read: {exc}") from exc

    updates = {
        "GERY_INGESTION_AI_ENABLED": str(validated.ingestion_ai_enabled).lower(),
        "GERY_ALLOW_LIVE_AI": str(validated.live_ai_enabled).lower(),
        "GERY_AI_BASE_URL": validated.base_url,
        "GERY_AI_MODEL": validated.model,
    }
    try:
        if api_key_update is not None:
            # The parent secrets directory is private. Mode 0644 lets the
            # unprivileged container user read this individual Docker secret.
            _atomic_write(api_key_path, f"{api_key_update.strip()}\n", 0o644)
        _atomic_write(env_path, _updated_env_text(original, updates), env_mode or 0o600)
    except OSError as exc:
        raise ValueError(f"Gery settings could not be saved: {exc}") from exc

    return replace(
        validated,
        api_key_configured=(
            bool(api_key_update.strip())
            if api_key_update is not None
            else validated.api_key_configured
        ),
    )
