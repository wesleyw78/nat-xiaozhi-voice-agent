(function () {
  const statusText = document.getElementById("statusText");
  const voiceStatus = document.getElementById("voiceStatus");
  const volumeMeter = document.getElementById("volumeMeter");
  const messageList = document.getElementById("messageList");
  const composerForm = document.getElementById("composerForm");
  const messageInput = document.getElementById("messageInput");
  const sendButton = document.getElementById("sendButton");
  const replayButton = document.getElementById("replayButton");
  const autoPlayToggle = document.getElementById("autoPlayToggle");
  const deviceIdInput = document.getElementById("deviceIdInput");
  const saveDeviceButton = document.getElementById("saveDeviceButton");
  const voiceButton = document.getElementById("voiceButton");
  const interruptButton = document.getElementById("interruptButton");

  const SILENCE_MS = 1350;
  const MIN_RECORDING_MS = 650;
  const MAX_RECORDING_MS = 15000;

  let lastAudioUrl = null;
  let currentAudio = null;
  let audioQueue = [];
  let streamAbortController = null;
  let voiceEnabled = false;
  let micStream = null;
  let audioContext = null;
  let analyser = null;
  let analyserBuffer = null;
  let mediaRecorder = null;
  let recordedChunks = [];
  let recordingStartedAt = 0;
  let lastVoiceAt = 0;
  let monitorFrame = null;
  let voiceGate = null;

  function getDeviceId() {
    const stored = localStorage.getItem("xiaozhi-web-device-id");
    if (stored) return stored;
    const generated = "web-" + Math.random().toString(16).slice(2, 10);
    localStorage.setItem("xiaozhi-web-device-id", generated);
    return generated;
  }

  function setStatus(text, kind) {
    statusText.textContent = text;
    statusText.classList.remove("error", "warning");
    if (kind) statusText.classList.add(kind);
  }

  function setVoiceStatus(text) {
    voiceStatus.textContent = text;
  }

  function clearEmptyState() {
    const empty = messageList.querySelector(".empty-state");
    if (empty) empty.remove();
  }

  function appendMessage(role, text) {
    clearEmptyState();
    const item = document.createElement("div");
    item.className = "message " + role;

    const bubble = document.createElement("div");
    bubble.className = "bubble";

    const meta = document.createElement("span");
    meta.className = "meta";
    meta.textContent = role === "user" ? "You" : "Xiaozhi";

    const body = document.createElement("span");
    body.textContent = text || "";

    bubble.appendChild(meta);
    bubble.appendChild(body);
    item.appendChild(bubble);
    messageList.appendChild(item);
    messageList.scrollTop = messageList.scrollHeight;
    return body;
  }

  function base64ToBlobUrl(dataBase64, mimeType) {
    const raw = atob(dataBase64);
    const bytes = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i += 1) {
      bytes[i] = raw.charCodeAt(i);
    }
    const blob = new Blob([bytes], { type: mimeType });
    return URL.createObjectURL(blob);
  }

  function stopCurrentAudio() {
    if (currentAudio) {
      currentAudio.pause();
      currentAudio.src = "";
      currentAudio = null;
    }
    audioQueue = [];
  }

  function isAssistantBusy() {
    return Boolean(streamAbortController || currentAudio || audioQueue.length > 0);
  }

  function interruptCurrent(reason) {
    if (streamAbortController) {
      streamAbortController.abort();
      streamAbortController = null;
    }
    stopCurrentAudio();
    interruptButton.disabled = true;
    if (reason) setStatus(reason, "warning");
  }

  function playNextAudio() {
    if (currentAudio || audioQueue.length === 0 || !autoPlayToggle.checked) return;
    const url = audioQueue.shift();
    currentAudio = new Audio(url);
    currentAudio.onplay = () => setStatus("Playing reply audio...");
    currentAudio.onended = () => {
      currentAudio = null;
      if (audioQueue.length > 0) playNextAudio();
      else {
        interruptButton.disabled = streamAbortController === null;
        setStatus("Ready.");
      }
    };
    currentAudio.onerror = () => {
      currentAudio = null;
      setStatus("Audio playback failed. Press Replay or check browser audio.", "warning");
      playNextAudio();
    };
    currentAudio.play().catch(() => {
      currentAudio = null;
      setStatus("Browser blocked autoplay. Press Replay to listen.", "warning");
    });
  }

  function enqueueAudio(audio) {
    if (!audio || !audio.data_base64) return;
    const url = base64ToBlobUrl(audio.data_base64, audio.mime_type || "audio/mpeg");
    lastAudioUrl = url;
    replayButton.disabled = false;
    audioQueue.push(url);
    playNextAudio();
  }

  async function refreshHealth() {
    try {
      const response = await fetch("/health");
      if (!response.ok) throw new Error("health request failed");
      const data = await response.json();
      const ttsState = data.pipeline && data.pipeline.tts ? "TTS ready" : "TTS not ready";
      const asrState = data.pipeline && data.pipeline.asr ? "ASR ready" : "ASR not ready";
      setStatus("Service online. " + asrState + ", " + ttsState + ".");
    } catch (error) {
      setStatus("Service health check failed.", "error");
    }
  }

  async function readNdjson(response, onEvent) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const result = await reader.read();
      if (result.done) break;
      buffer += decoder.decode(result.value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (!line.trim()) continue;
        onEvent(JSON.parse(line));
      }
    }
    buffer += decoder.decode();
    if (buffer.trim()) onEvent(JSON.parse(buffer));
  }

  async function sendMessage(text) {
    interruptCurrent();
    appendMessage("user", text);
    const assistantBody = appendMessage("assistant", "");
    let assistantText = "";

    sendButton.disabled = true;
    interruptButton.disabled = false;
    streamAbortController = new AbortController();
    setStatus("Thinking...");

    try {
      const response = await fetch("/api/web-chat-stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          device_id: deviceIdInput.value.trim() || "web-client",
          text: text,
        }),
        signal: streamAbortController.signal,
      });
      if (!response.ok || !response.body) throw new Error("stream request failed");

      await readNdjson(response, (event) => {
        if (event.type === "start") {
          setStatus("Streaming reply...");
        } else if (event.type === "delta") {
          assistantText += event.text || "";
          assistantBody.textContent = assistantText;
          messageList.scrollTop = messageList.scrollHeight;
        } else if (event.type === "audio") {
          enqueueAudio(event);
        } else if (event.type === "audio_error") {
          setStatus(event.message || "Audio generation failed.", "warning");
        } else if (event.type === "done") {
          if (event.text) {
            assistantText = event.text;
            assistantBody.textContent = assistantText;
          }
          setStatus(audioQueue.length > 0 || currentAudio ? "Playing reply audio..." : "Ready.");
        } else if (event.type === "error") {
          setStatus(event.message || "Chat stream failed.", "error");
        }
      });
    } catch (error) {
      if (error.name !== "AbortError") {
        setStatus("Network error while streaming reply.", "error");
      }
    } finally {
      streamAbortController = null;
      sendButton.disabled = false;
      interruptButton.disabled = currentAudio === null;
      messageInput.disabled = false;
      messageInput.focus();
    }
  }

  function getRecorderMimeType() {
    const types = [
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/ogg;codecs=opus",
      "audio/mp4",
    ];
    return types.find((type) => MediaRecorder.isTypeSupported(type)) || "";
  }

  function startRecording() {
    if (!micStream || mediaRecorder) return;
    interruptCurrent("Listening...");
    recordedChunks = [];
    recordingStartedAt = performance.now();
    lastVoiceAt = recordingStartedAt;
    const mimeType = getRecorderMimeType();
    mediaRecorder = new MediaRecorder(micStream, mimeType ? { mimeType } : undefined);
    mediaRecorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) recordedChunks.push(event.data);
    };
    mediaRecorder.onstop = () => {
      const stoppedRecorder = mediaRecorder;
      mediaRecorder = null;
      const blob = new Blob(recordedChunks, { type: stoppedRecorder.mimeType || "audio/webm" });
      recordedChunks = [];
      if (blob.size > 0) uploadRecording(blob);
    };
    mediaRecorder.start();
    setVoiceStatus("Recording...");
  }

  function stopRecording() {
    if (!mediaRecorder || mediaRecorder.state === "inactive") return;
    mediaRecorder.stop();
    setVoiceStatus("Recognizing...");
  }

  async function uploadRecording(blob) {
    try {
      const deviceId = deviceIdInput.value.trim() || "web-client";
      const response = await fetch("/api/web-asr?device_id=" + encodeURIComponent(deviceId), {
        method: "POST",
        headers: { "Content-Type": blob.type || "application/octet-stream" },
        body: blob,
      });
      const data = await response.json();
      if (data.status !== "ok" || !data.text) {
        setVoiceStatus(data.message || "No speech recognized.");
        return;
      }
      setVoiceStatus("Recognized: " + data.text);
      sendMessage(data.text);
    } catch (error) {
      setVoiceStatus("ASR upload failed.");
      setStatus("Could not recognize microphone audio.", "error");
    }
  }

  function monitorVolume() {
    if (!voiceEnabled || !analyser) return;
    analyser.getByteTimeDomainData(analyserBuffer);
    let sum = 0;
    for (let i = 0; i < analyserBuffer.length; i += 1) {
      const value = (analyserBuffer[i] - 128) / 128;
      sum += value * value;
    }
    const rms = Math.sqrt(sum / analyserBuffer.length);
    volumeMeter.style.width = Math.min(100, Math.round(rms * 420)) + "%";

    const now = performance.now();
    if (!mediaRecorder && voiceGate) {
      const gateState = voiceGate.update({ rms, now, isBusy: isAssistantBusy() });
      if (gateState === "candidate") {
        setVoiceStatus(isAssistantBusy() ? "Keep speaking to interrupt..." : "Voice detected...");
      } else if (gateState === "start") {
        startRecording();
      } else if (!isAssistantBusy()) {
        setVoiceStatus("Voice mode on. Start speaking.");
      }
    } else if (mediaRecorder && voiceGate && rms > voiceGate.getReleaseThreshold()) {
      lastVoiceAt = now;
    } else if (
      mediaRecorder &&
      now - lastVoiceAt > SILENCE_MS &&
      now - recordingStartedAt > MIN_RECORDING_MS
    ) {
      stopRecording();
    }

    if (mediaRecorder && now - recordingStartedAt > MAX_RECORDING_MS) {
      stopRecording();
    }
    monitorFrame = requestAnimationFrame(monitorVolume);
  }

  async function startVoiceMode() {
    if (voiceEnabled) return;
    try {
      micStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      audioContext = new AudioContext();
      const source = audioContext.createMediaStreamSource(micStream);
      analyser = audioContext.createAnalyser();
      analyser.fftSize = 1024;
      analyserBuffer = new Uint8Array(analyser.fftSize);
      source.connect(analyser);
      voiceGate = window.XiaozhiVoiceGate.createVoiceGate();
      voiceEnabled = true;
      voiceButton.textContent = "Stop voice";
      setVoiceStatus("Voice mode on. Start speaking.");
      monitorVolume();
    } catch (error) {
      setVoiceStatus("Microphone permission denied or unavailable.");
      setStatus("Microphone is unavailable.", "error");
    }
  }

  function stopVoiceMode() {
    voiceEnabled = false;
    if (monitorFrame) cancelAnimationFrame(monitorFrame);
    monitorFrame = null;
    if (mediaRecorder) stopRecording();
    if (micStream) micStream.getTracks().forEach((track) => track.stop());
    micStream = null;
    if (audioContext) audioContext.close();
    audioContext = null;
    analyser = null;
    analyserBuffer = null;
    voiceGate = null;
    volumeMeter.style.width = "0%";
    voiceButton.textContent = "Start voice";
    setVoiceStatus("Voice idle.");
  }

  composerForm.addEventListener("submit", function (event) {
    event.preventDefault();
    const text = messageInput.value.trim();
    if (!text) {
      setStatus("Type a message before sending.", "warning");
      return;
    }
    messageInput.value = "";
    sendMessage(text);
  });

  messageInput.addEventListener("keydown", function (event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      composerForm.requestSubmit();
    }
  });

  replayButton.addEventListener("click", function () {
    if (!lastAudioUrl) return;
    audioQueue = [lastAudioUrl];
    playNextAudio();
  });

  interruptButton.addEventListener("click", function () {
    interruptCurrent("Interrupted.");
  });

  voiceButton.addEventListener("click", function () {
    if (voiceEnabled) stopVoiceMode();
    else startVoiceMode();
  });

  saveDeviceButton.addEventListener("click", function () {
    const value = deviceIdInput.value.trim() || "web-client";
    deviceIdInput.value = value;
    localStorage.setItem("xiaozhi-web-device-id", value);
    setStatus("Device ID saved.");
  });

  deviceIdInput.value = getDeviceId();
  refreshHealth();
  messageInput.focus();
})();
