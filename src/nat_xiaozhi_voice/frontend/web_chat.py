"""Helpers for the browser-facing chat API."""

from __future__ import annotations

import base64
import json
import subprocess
from typing import Any

FIRST_SENTENCE_PUNCTS = frozenset("，,、。！？；：!?;:\n")
NORMAL_SENTENCE_PUNCTS = frozenset("。！？!?\n")
MAX_STREAM_SEGMENT_CHARS = 150


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


def encode_stream_event(event_type: str, **payload: Any) -> bytes:
    """Encode one browser-chat stream event as newline-delimited JSON."""
    event = {"type": event_type, **payload}
    return (json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def _find_sentence_boundary(text: str, is_first_sentence: bool) -> int:
    puncts = FIRST_SENTENCE_PUNCTS if is_first_sentence else NORMAL_SENTENCE_PUNCTS
    for idx, char in enumerate(text):
        if char in puncts:
            return idx
    return -1


def pop_tts_segment(text: str, is_first_sentence: bool) -> tuple[str | None, str, bool]:
    """Pop one TTS segment from buffered streamed text when a boundary is ready."""
    boundary = _find_sentence_boundary(text, is_first_sentence)
    if boundary != -1:
        return text[: boundary + 1], text[boundary + 1 :], False
    if len(text) > MAX_STREAM_SEGMENT_CHARS:
        return text, "", False
    return None, text, is_first_sentence


def decode_web_audio_to_pcm(audio_bytes: bytes) -> bytes:
    """Decode browser-recorded audio into raw 16 kHz mono 16-bit PCM with ffmpeg."""
    if not audio_bytes:
        raise WebChatValidationError("audio is empty")

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        "pipe:0",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-f",
        "s16le",
        "pipe:1",
    ]
    try:
        completed = subprocess.run(
            cmd,
            input=audio_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("ffmpeg is not installed") from exc

    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(detail or "ffmpeg failed to decode audio")
    if not completed.stdout:
        raise RuntimeError("ffmpeg produced no PCM audio")
    return completed.stdout
