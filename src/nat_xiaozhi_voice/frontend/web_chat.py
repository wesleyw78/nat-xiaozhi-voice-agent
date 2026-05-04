"""Helpers for the browser-facing chat API."""

from __future__ import annotations

import base64
from typing import Any


class WebChatValidationError(ValueError):
    """Raised when a browser chat request is invalid."""


def normalize_chat_text(text: str) -> str:
    """Strip user text and reject empty browser-chat requests."""
    normalized = text.strip()
    if not normalized:
        raise WebChatValidationError("text is empty")
    return normalized


def build_success_response(
    *,
    device_id: str,
    reply: str,
    audio_bytes: bytes | None,
    mime_type: str | None,
    error: str | None = None,
) -> dict[str, Any]:
    """Build a JSON-safe response for a successful or partial chat turn."""
    if audio_bytes and mime_type:
        audio = {
            "mime_type": mime_type,
            "data_base64": base64.b64encode(audio_bytes).decode("ascii"),
        }
        return {
            "status": "ok",
            "device_id": device_id,
            "reply": reply,
            "audio": audio,
        }

    response = {
        "status": "partial",
        "device_id": device_id,
        "reply": reply,
        "audio": None,
    }
    if error:
        response["error"] = error
    return response


def build_error_response(message: str) -> dict[str, str]:
    """Build a standard browser-chat error response."""
    return {"status": "error", "message": message}
