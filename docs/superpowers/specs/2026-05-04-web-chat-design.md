# Web Chat With Audio Design

## Goal

Build a browser page for talking to the Xiaozhi voice agent. The user can type a message in the page, see the assistant reply, and play the assistant's voice response from the browser.

The web page should not consume the existing Xiaozhi Opus audio WebSocket directly. Instead, the server will expose a browser-friendly chat API that returns text plus standard browser-playable audio.

## Context

The current service already supports:

- Xiaozhi-compatible WebSocket at `/xiaozhi/v1/`.
- ASR, LLM, and TTS pipeline.
- Per-device conversation memory through the existing LangGraph agent.
- EdgeTTS as the configured TTS backend.

The Python client can play server-sent Opus frames with `opuslib`, but browsers do not reliably play arbitrary raw Opus frames without extra decoder work. For a web UI, the stable path is to let the backend produce standard audio for the browser.

## Chosen Approach

Add a browser-specific HTTP API and a static web UI served by the existing FastAPI app.

The page sends text to the backend:

```http
POST /api/web-chat
```

The backend:

1. Receives `device_id` and `text`.
2. Calls the existing agent function using `device_id` as the memory thread.
3. Cleans the reply for TTS using the existing TTS cleanup behavior.
4. Synthesizes browser-playable audio.
5. Returns JSON containing the assistant text and an audio payload or URL.

The page:

1. Displays user and assistant messages.
2. Shows loading, connected, error, and audio playback states.
3. Plays the assistant audio when available.
4. Still shows the text reply if audio synthesis fails.

## API Design

### `GET /chat`

Serves the browser chat page.

### `POST /api/web-chat`

Request:

```json
{
  "device_id": "web-client",
  "text": "你好"
}
```

Response on success:

```json
{
  "status": "ok",
  "device_id": "web-client",
  "reply": "你好！有什么我可以帮忙的吗？",
  "audio": {
    "mime_type": "audio/mpeg",
    "data_base64": "..."
  }
}
```

Response when the agent succeeds but TTS fails:

```json
{
  "status": "partial",
  "device_id": "web-client",
  "reply": "你好！有什么我可以帮忙的吗？",
  "audio": null,
  "error": "TTS failed"
}
```

Response on validation or agent failure:

```json
{
  "status": "error",
  "message": "text is empty"
}
```

## Audio Strategy

The first implementation will use standard browser audio, not the Xiaozhi Opus stream.

Preferred response format is MP3 in base64 because browsers can play it with a normal `Audio` element. If the current TTS implementation only exposes PCM or Opus callbacks, add a small browser-audio method to the TTS layer rather than forcing the frontend to decode Opus.

The UI must tolerate missing audio. A text reply is still useful and should remain visible even when playback fails.

## Frontend Design

The page is a focused chat app, not a landing page.

Primary elements:

- Header with service status and device id.
- Message list with user and assistant bubbles.
- Composer with text input and send button.
- Audio controls: auto-play toggle, replay last response, and muted/error indicator.
- Status row for "thinking", "generating voice", "playing", and error messages.

The visual style should be quiet and operational: clear spacing, readable text, stable message layout, and no decorative hero section.

## Files And Boundaries

Expected additions or changes:

- `src/nat_xiaozhi_voice/frontend/ws_server.py`
  - Add `/chat` static page route.
  - Add `/api/web-chat` route.
  - Reuse existing agent and TTS instances.

- `src/nat_xiaozhi_voice/pipeline/tts.py`
  - Add a browser-audio helper if needed, keeping existing Xiaozhi Opus streaming behavior unchanged.

- `src/nat_xiaozhi_voice/frontend/static/chat.html`
  - Browser UI.

- `src/nat_xiaozhi_voice/frontend/static/chat.js`
  - API calls, message rendering, audio playback.

- `src/nat_xiaozhi_voice/frontend/static/chat.css`
  - Layout and styling.

Tests should focus on backend behavior where practical. The UI can be manually verified in a browser after implementation.

## Error Handling

- Empty input returns a clear validation error.
- Agent failure returns an error and does not attempt TTS.
- TTS failure returns `partial` with the text reply.
- Browser autoplay restrictions are handled by showing a replay button and playback status.
- Network failure leaves the user's message visible and shows a retry-friendly error state.

## Verification

Backend verification:

- `POST /api/web-chat` rejects empty text.
- `POST /api/web-chat` returns a non-empty reply for a normal prompt.
- TTS failure still returns the reply with `status: partial`.

Manual browser verification:

- Open `/chat`.
- Send a text prompt.
- See the user message and assistant reply.
- Hear audio or see a clear playback prompt if browser autoplay blocks it.
- Confirm repeated messages preserve per-device memory.

## Out Of Scope For First Version

- Browser microphone capture.
- Direct playback of Xiaozhi Opus WebSocket frames.
- Camera relay UI.
- Full memory management UI.
- Streaming token-by-token display.
- Multi-user authentication.
