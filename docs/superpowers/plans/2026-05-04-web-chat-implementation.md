# Web Chat With Audio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a browser chat page that sends text to the Xiaozhi agent, displays replies, and plays browser-friendly TTS audio.

**Architecture:** Add a focused web-chat helper module for request validation and response shaping, extend the existing TTS classes with browser-audio methods, expose `/chat` and `/api/web-chat` from the existing FastAPI server, and add static HTML/CSS/JS assets. The existing Xiaozhi WebSocket Opus path remains unchanged.

**Tech Stack:** Python 3.12, FastAPI, existing LangGraph agent functions, EdgeTTS/CosyVoice TTS layer, browser HTML/CSS/JavaScript, standard-library `unittest` for pure helper tests.

---

### Task 1: Web Chat Helper Module

**Files:**
- Create: `src/nat_xiaozhi_voice/frontend/web_chat.py`
- Create: `tests/test_web_chat_helpers.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_web_chat_helpers.py`:

```python
import base64
import unittest

from nat_xiaozhi_voice.frontend.web_chat import (
    WebChatValidationError,
    build_error_response,
    build_success_response,
    normalize_chat_text,
)


class WebChatHelperTests(unittest.TestCase):
    def test_normalize_chat_text_rejects_blank_text(self):
        with self.assertRaises(WebChatValidationError) as ctx:
            normalize_chat_text("   \n\t  ")
        self.assertEqual(str(ctx.exception), "text is empty")

    def test_normalize_chat_text_strips_outer_whitespace(self):
        self.assertEqual(normalize_chat_text("  你好  "), "你好")

    def test_build_success_response_encodes_audio(self):
        result = build_success_response(
            device_id="web-client",
            reply="你好",
            audio_bytes=b"abc",
            mime_type="audio/mpeg",
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["device_id"], "web-client")
        self.assertEqual(result["reply"], "你好")
        self.assertEqual(result["audio"]["mime_type"], "audio/mpeg")
        self.assertEqual(base64.b64decode(result["audio"]["data_base64"]), b"abc")

    def test_build_success_response_without_audio_is_partial(self):
        result = build_success_response(
            device_id="web-client",
            reply="你好",
            audio_bytes=None,
            mime_type=None,
            error="TTS failed",
        )
        self.assertEqual(result["status"], "partial")
        self.assertIsNone(result["audio"])
        self.assertEqual(result["error"], "TTS failed")

    def test_build_error_response(self):
        self.assertEqual(
            build_error_response("text is empty"),
            {"status": "error", "message": "text is empty"},
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `python -m unittest tests.test_web_chat_helpers -v`

Expected: FAIL or ERROR because `nat_xiaozhi_voice.frontend.web_chat` does not exist.

- [ ] **Step 3: Implement the helper module**

Create `src/nat_xiaozhi_voice/frontend/web_chat.py` with `WebChatValidationError`, `normalize_chat_text`, `build_success_response`, and `build_error_response`.

- [ ] **Step 4: Run tests and verify they pass**

Run: `python -m unittest tests.test_web_chat_helpers -v`

Expected: all tests pass.

---

### Task 2: Browser Audio TTS Methods

**Files:**
- Modify: `src/nat_xiaozhi_voice/pipeline/tts.py`

- [ ] **Step 1: Add browser-audio methods**

Add `synthesize_browser_audio()` to both TTS classes:

- `EdgeTTS.synthesize_browser_audio(text) -> tuple[str, bytes]` returns `("audio/mpeg", mp3_bytes)`.
- `CosyVoiceTTS.synthesize_browser_audio(text, sample_rate=24000) -> tuple[str, bytes]` collects PCM from the existing HTTP stream and wraps it as WAV bytes.

Keep `synthesize_stream()` behavior unchanged for the Xiaozhi Opus client.

- [ ] **Step 2: Refactor Edge streaming to reuse MP3 fetch**

In `EdgeTTS.synthesize_stream()`, call `synthesize_browser_audio()` first, then decode the returned MP3 with `miniaudio` and encode Opus as before.

- [ ] **Step 3: Compile-check the file**

Run: `python -m py_compile src/nat_xiaozhi_voice/pipeline/tts.py`

Expected: no syntax errors.

---

### Task 3: FastAPI Web Chat Routes

**Files:**
- Modify: `src/nat_xiaozhi_voice/frontend/ws_server.py`
- Create: `src/nat_xiaozhi_voice/frontend/static/chat.html`
- Create: `src/nat_xiaozhi_voice/frontend/static/chat.css`
- Create: `src/nat_xiaozhi_voice/frontend/static/chat.js`

- [ ] **Step 1: Add request model and routes**

Add `WebChatRequest` with `text` and `device_id`. Register:

- `GET /chat` to serve `static/chat.html`.
- `GET /chat.css` to serve `static/chat.css`.
- `GET /chat.js` to serve `static/chat.js`.
- `POST /api/web-chat` to call the existing agent and TTS.

- [ ] **Step 2: Implement route behavior**

`_web_chat()` should:

1. Validate text with `normalize_chat_text`.
2. Use `device_id` or `"web-client"`.
3. Await `self._agent_fn(text, device_id)`.
4. If reply is empty, return `status: error`.
5. Try `self._tts.synthesize_browser_audio(reply)`.
6. Return `ok` with audio or `partial` with text if TTS fails.

- [ ] **Step 3: Compile-check route module**

Run: `python -m py_compile src/nat_xiaozhi_voice/frontend/ws_server.py`

Expected: no syntax errors.

---

### Task 4: Browser Chat UI

**Files:**
- Create: `src/nat_xiaozhi_voice/frontend/static/chat.html`
- Create: `src/nat_xiaozhi_voice/frontend/static/chat.css`
- Create: `src/nat_xiaozhi_voice/frontend/static/chat.js`

- [ ] **Step 1: Create the page structure**

`chat.html` includes a header, connection/device controls, message log, status row, audio controls, and composer.

- [ ] **Step 2: Add interaction logic**

`chat.js` should:

1. Generate or persist a `device_id` in `localStorage`.
2. Fetch `/health` on load and update status.
3. POST `/api/web-chat` when the user sends text.
4. Render user and assistant messages.
5. Convert base64 audio to a Blob URL and play it when auto-play is enabled.
6. Keep a replay button for the last audio response.

- [ ] **Step 3: Add restrained UI styling**

`chat.css` should provide a compact operational chat layout, stable message widths, clear buttons, responsive behavior, and no landing page.

---

### Task 5: Final Verification

**Files:**
- Verify all changed files.

- [ ] **Step 1: Run helper tests**

Run: `python -m unittest tests.test_web_chat_helpers -v`

Expected: pass.

- [ ] **Step 2: Compile Python files**

Run: `python -m py_compile src/nat_xiaozhi_voice/frontend/web_chat.py src/nat_xiaozhi_voice/frontend/ws_server.py src/nat_xiaozhi_voice/pipeline/tts.py`

Expected: no syntax errors.

- [ ] **Step 3: Report Docker verification command**

Because local Python dependencies are not installed, verify the integrated route in Docker with:

```bash
docker compose build
docker compose up -d
curl -s http://172.16.1.120:8000/health
curl -s -X POST http://172.16.1.120:8000/api/web-chat \
  -H 'Content-Type: application/json' \
  -d '{"device_id":"web-client","text":"你好"}'
```

Expected: health is `ok`, and `/api/web-chat` returns `status` of `ok` or `partial` with a non-empty `reply`.
