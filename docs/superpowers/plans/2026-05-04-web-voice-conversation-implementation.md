# Web Voice Conversation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add microphone-driven browser conversation with auto-send, interrupt, streamed text display, and streamed browser audio playback.

**Architecture:** Keep the existing Xiaozhi WebSocket unchanged. Add browser-only ASR and NDJSON streaming chat endpoints to FastAPI, using shared helper functions for stream event formatting and sentence segmentation. Update the static web page to record microphone audio, upload it for ASR, stream chat events, and play audio chunks sequentially.

**Tech Stack:** Python 3.12, FastAPI StreamingResponse, ffmpeg subprocess, existing FunASR/Agent/TTS objects, browser MediaRecorder/WebAudio/fetch streams, standard-library unittest.

---

### Task 1: Stream Helper Tests

**Files:**
- Modify: `src/nat_xiaozhi_voice/frontend/web_chat.py`
- Modify: `tests/test_web_chat_helpers.py`

- [ ] Add tests for NDJSON stream event encoding, sentence boundary detection, and TTS segment popping.
- [ ] Run `PYTHONPATH=src python -m unittest tests.test_web_chat_helpers -v` and confirm the new tests fail before implementation.
- [ ] Implement helper functions.
- [ ] Run the same unittest command and confirm all tests pass.

### Task 2: Browser ASR Endpoint

**Files:**
- Modify: `src/nat_xiaozhi_voice/frontend/ws_server.py`
- Modify: `src/nat_xiaozhi_voice/frontend/web_chat.py`

- [ ] Add `decode_web_audio_to_pcm()` using `ffmpeg -i pipe:0 -ac 1 -ar 16000 -f s16le pipe:1`.
- [ ] Add `POST /api/web-asr` that reads raw request bytes, converts to PCM, calls existing ASR, and returns recognized text.
- [ ] Return clear JSON errors for empty audio, ASR not ready, ffmpeg failure, or no recognized text.

### Task 3: Streaming Chat Endpoint

**Files:**
- Modify: `src/nat_xiaozhi_voice/frontend/ws_server.py`

- [ ] Add `POST /api/web-chat-stream`.
- [ ] Stream `start`, `delta`, `audio`, `done`, and `error` NDJSON events.
- [ ] Use `agent_stream_fn` when available, falling back to `agent_fn`.
- [ ] Run TTS in a concurrent consumer so text deltas keep flowing while audio chunks are generated.
- [ ] Cancel producer and consumer tasks if the client aborts.

### Task 4: Browser Voice UI

**Files:**
- Modify: `src/nat_xiaozhi_voice/frontend/static/chat.html`
- Modify: `src/nat_xiaozhi_voice/frontend/static/chat.css`
- Modify: `src/nat_xiaozhi_voice/frontend/static/chat.js`

- [ ] Add voice controls and interrupt button.
- [ ] Add microphone permission, volume monitoring, auto-record start, silence stop, and upload to `/api/web-asr`.
- [ ] Add NDJSON stream parser for `/api/web-chat-stream`.
- [ ] Render assistant deltas into one live message bubble.
- [ ] Queue and play audio chunks sequentially.
- [ ] Abort current stream and stop playback when the user starts speaking.

### Task 5: Verification

**Files:**
- Verify all changed files.

- [ ] Run `PYTHONPATH=src python -m unittest tests.test_web_chat_helpers -v`.
- [ ] Run `python -m py_compile src/nat_xiaozhi_voice/frontend/web_chat.py src/nat_xiaozhi_voice/frontend/ws_server.py`.
- [ ] Rebuild Docker and manually verify `/chat`, `/api/web-asr`, and `/api/web-chat-stream`.
