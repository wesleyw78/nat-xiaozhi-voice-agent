# Web Voice Conversation Design

## Goal

Upgrade the browser chat page into a smooth voice conversation surface. The page should use the microphone, auto-send speech after silence, interrupt assistant playback when the user starts talking, stream assistant text as it is generated, and play voice segments while text continues to appear.

## Findings

The current `/api/web-chat` endpoint is not streaming. It waits for the full agent reply, synthesizes one complete browser audio file, then returns a single JSON response.

The existing Xiaozhi WebSocket path is streaming. `ConnectionHandler._run_agent_and_speak()` sends `llm.delta` while the agent streams tokens, splits text into TTS segments, and sends Opus audio frames in parallel. That path also supports `abort`. Browsers cannot play the raw Opus frames directly without extra decoding work, so the browser UI needs a web-friendly streaming API.

## Chosen Approach

Add two browser-specific endpoints:

- `POST /api/web-asr`: accepts browser-recorded audio bytes, converts them to 16 kHz mono PCM with `ffmpeg`, and uses the existing FunASR recognizer.
- `POST /api/web-chat-stream`: accepts text and returns newline-delimited JSON events. It streams text deltas and browser-playable audio chunks.

The browser page will:

- Capture microphone audio with `MediaRecorder`.
- Use simple WebAudio volume detection for auto-start and auto-stop.
- Send audio automatically after a short silence.
- Abort the current streaming reply and stop playback when the user starts speaking.
- Render text deltas immediately.
- Queue and play audio chunks as they arrive.

## Stream Event Format

`POST /api/web-chat-stream` returns `application/x-ndjson`.

Example events:

```json
{"type":"start"}
{"type":"delta","text":"你好"}
{"type":"audio","mime_type":"audio/mpeg","data_base64":"..."}
{"type":"done","text":"你好！我是 Xiaozhi。"}
```

Error event:

```json
{"type":"error","message":"agent failed"}
```

The stream is abortable by closing the browser request through `AbortController`.

## Audio Strategy

Browser microphone audio is sent as `webm/opus` or the browser's best supported `MediaRecorder` MIME type. The server uses `ffmpeg` to decode it into raw 16 kHz mono PCM for the existing ASR pipeline.

Assistant audio is generated per TTS text segment through the existing browser-audio TTS method. EdgeTTS returns MP3. CosyVoice returns WAV. The page plays each chunk with a normal `Audio` element.

## UI Behavior

The page keeps text input as a fallback, but adds a voice mode:

- `Start voice` requests microphone permission and begins monitoring.
- When volume crosses a threshold, recording starts.
- When silence lasts about one second, recording stops and audio is sent.
- If assistant audio is playing or a response is streaming, new speech interrupts it.
- `Interrupt` manually stops current playback and cancels the stream.

## Out Of Scope

- Raw Opus decoding in the browser.
- Wake word detection.
- Speaker diarization.
- Authentication or multi-user moderation.
