(function () {
  const statusText = document.getElementById("statusText");
  const messageList = document.getElementById("messageList");
  const composerForm = document.getElementById("composerForm");
  const messageInput = document.getElementById("messageInput");
  const sendButton = document.getElementById("sendButton");
  const replayButton = document.getElementById("replayButton");
  const autoPlayToggle = document.getElementById("autoPlayToggle");
  const deviceIdInput = document.getElementById("deviceIdInput");
  const saveDeviceButton = document.getElementById("saveDeviceButton");

  let lastAudioUrl = null;
  let currentAudio = null;

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
    body.textContent = text;

    bubble.appendChild(meta);
    bubble.appendChild(body);
    item.appendChild(bubble);
    messageList.appendChild(item);
    messageList.scrollTop = messageList.scrollHeight;
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

  async function playAudio(url) {
    if (currentAudio) {
      currentAudio.pause();
      currentAudio = null;
    }
    currentAudio = new Audio(url);
    currentAudio.onplay = () => setStatus("Playing reply audio...");
    currentAudio.onended = () => setStatus("Ready.");
    currentAudio.onerror = () => setStatus("Audio playback failed. Use Replay or check browser audio.", "warning");
    await currentAudio.play();
  }

  async function handleAudio(audio) {
    if (!audio || !audio.data_base64) {
      replayButton.disabled = true;
      return;
    }

    if (lastAudioUrl) URL.revokeObjectURL(lastAudioUrl);
    lastAudioUrl = base64ToBlobUrl(audio.data_base64, audio.mime_type || "audio/mpeg");
    replayButton.disabled = false;

    if (autoPlayToggle.checked) {
      try {
        await playAudio(lastAudioUrl);
      } catch (error) {
        setStatus("Browser blocked autoplay. Press Replay to listen.", "warning");
      }
    } else {
      setStatus("Reply ready. Press Replay to listen.");
    }
  }

  async function refreshHealth() {
    try {
      const response = await fetch("/health");
      if (!response.ok) throw new Error("health request failed");
      const data = await response.json();
      const ttsState = data.pipeline && data.pipeline.tts ? "TTS ready" : "TTS not ready";
      setStatus("Service online. " + ttsState + ".");
    } catch (error) {
      setStatus("Service health check failed.", "error");
    }
  }

  async function sendMessage(text) {
    appendMessage("user", text);
    sendButton.disabled = true;
    messageInput.disabled = true;
    setStatus("Thinking...");

    try {
      const response = await fetch("/api/web-chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          device_id: deviceIdInput.value.trim() || "web-client",
          text: text,
        }),
      });
      const data = await response.json();

      if (data.status === "error") {
        setStatus(data.message || "Chat request failed.", "error");
        return;
      }

      appendMessage("assistant", data.reply || "");
      if (data.status === "partial") {
        setStatus(data.error || "Reply received without audio.", "warning");
      } else {
        setStatus("Generating playback...");
      }
      await handleAudio(data.audio);
    } catch (error) {
      setStatus("Network error while sending message.", "error");
    } finally {
      sendButton.disabled = false;
      messageInput.disabled = false;
      messageInput.focus();
    }
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
    playAudio(lastAudioUrl).catch(function () {
      setStatus("Audio playback failed. Check output device and browser permissions.", "error");
    });
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
