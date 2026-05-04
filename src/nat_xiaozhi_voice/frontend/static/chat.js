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
  const voiceButton = document.getElementById("voiceButton");
  const interruptButton = document.getElementById("interruptButton");

  let lastAudioUrl = null;
  let currentAudio = null;
  let audioQueue = [];
  let streamAbortController = null;
  let micStream = null;
  let audioContext = null;
  let analyser = null;
  let analyserBuffer = null;
  let mediaRecorder = null;
  let recordedChunks = [];
  let monitorFrame = null;
  const deviceId = getDeviceId();

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
    meta.textContent = role === "user" ? "我" : "小智";

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
    currentAudio.onplay = () => setStatus("正在播放回复语音...");
    currentAudio.onended = () => {
      currentAudio = null;
      if (audioQueue.length > 0) playNextAudio();
      else {
        interruptButton.disabled = streamAbortController === null;
        setStatus("准备好了。");
      }
    };
    currentAudio.onerror = () => {
      currentAudio = null;
      setStatus("语音播放失败。请点击重播，或检查浏览器声音设置。", "warning");
      playNextAudio();
    };
    currentAudio.play().catch(() => {
      currentAudio = null;
      setStatus("浏览器阻止了自动播放，请点击重播收听。", "warning");
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
      const ttsState = data.pipeline && data.pipeline.tts ? "语音合成就绪" : "语音合成未就绪";
      const asrState = data.pipeline && data.pipeline.asr ? "语音识别就绪" : "语音识别未就绪";
      setStatus("服务已连接。" + asrState + "，" + ttsState + "。");
    } catch (error) {
      setStatus("服务健康检查失败。", "error");
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
    setStatus("正在思考...");

    try {
      const response = await fetch("/api/web-chat-stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          device_id: deviceId,
          text: text,
        }),
        signal: streamAbortController.signal,
      });
      if (!response.ok || !response.body) throw new Error("stream request failed");

      await readNdjson(response, (event) => {
        if (event.type === "start") {
          setStatus("正在流式回复...");
        } else if (event.type === "delta") {
          assistantText += event.text || "";
          assistantBody.textContent = assistantText;
          messageList.scrollTop = messageList.scrollHeight;
        } else if (event.type === "audio") {
          enqueueAudio(event);
        } else if (event.type === "audio_error") {
          setStatus(event.message || "语音生成失败。", "warning");
        } else if (event.type === "done") {
          if (event.text) {
            assistantText = event.text;
            assistantBody.textContent = assistantText;
          }
          setStatus(audioQueue.length > 0 || currentAudio ? "正在播放回复语音..." : "准备好了。");
        } else if (event.type === "error") {
          setStatus(event.message || "对话流失败。", "error");
        }
      });
    } catch (error) {
      if (error.name !== "AbortError") {
        setStatus("流式回复时发生网络错误。", "error");
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

  async function prepareMicrophone() {
    if (micStream && analyser && analyserBuffer) return true;
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
      return true;
    } catch (error) {
      setVoiceStatus("麦克风权限被拒绝或不可用。");
      setStatus("麦克风不可用。", "error");
      return false;
    }
  }

  function cleanupMicrophone() {
    if (monitorFrame) cancelAnimationFrame(monitorFrame);
    monitorFrame = null;
    if (micStream) micStream.getTracks().forEach((track) => track.stop());
    micStream = null;
    if (audioContext) audioContext.close();
    audioContext = null;
    analyser = null;
    analyserBuffer = null;
    volumeMeter.style.width = "0%";
  }

  async function startRecording() {
    if (mediaRecorder) return;
    const ready = await prepareMicrophone();
    if (!ready) return;

    interruptCurrent("正在听...");
    recordedChunks = [];
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
      cleanupMicrophone();
      voiceButton.textContent = "开始说话";
      voiceButton.classList.remove("recording");
      if (blob.size > 0) {
        uploadRecording(blob);
      } else {
        voiceButton.disabled = false;
        setVoiceStatus("没有录到语音。");
      }
    };
    mediaRecorder.start();
    voiceButton.textContent = "发送语音";
    voiceButton.classList.add("recording");
    setVoiceStatus("正在录音，请再次点击发送。");
    monitorVolume();
  }

  function stopRecording() {
    if (!mediaRecorder || mediaRecorder.state === "inactive") return;
    voiceButton.disabled = true;
    mediaRecorder.stop();
    setVoiceStatus("正在识别...");
  }

  async function uploadRecording(blob) {
    try {
      const response = await fetch("/api/web-asr?device_id=" + encodeURIComponent(deviceId), {
        method: "POST",
        headers: { "Content-Type": blob.type || "application/octet-stream" },
        body: blob,
      });
      const data = await response.json();
      if (data.status !== "ok" || !data.text) {
        setVoiceStatus(data.message || "未识别到语音。");
        voiceButton.disabled = false;
        voiceButton.classList.remove("recording");
        return;
      }
      setVoiceStatus("已识别：" + data.text);
      voiceButton.disabled = false;
      sendMessage(data.text);
    } catch (error) {
      setVoiceStatus("语音上传失败。");
      setStatus("无法识别麦克风语音。", "error");
      voiceButton.disabled = false;
      voiceButton.classList.remove("recording");
    }
  }

  function monitorVolume() {
    if (!mediaRecorder || !analyser) {
      volumeMeter.style.width = "0%";
      return;
    }
    analyser.getByteTimeDomainData(analyserBuffer);
    let sum = 0;
    for (let i = 0; i < analyserBuffer.length; i += 1) {
      const value = (analyserBuffer[i] - 128) / 128;
      sum += value * value;
    }
    const rms = Math.sqrt(sum / analyserBuffer.length);
    volumeMeter.style.width = Math.min(100, Math.round(rms * 420)) + "%";
    monitorFrame = requestAnimationFrame(monitorVolume);
  }

  composerForm.addEventListener("submit", function (event) {
    event.preventDefault();
    const text = messageInput.value.trim();
    if (!text) {
      setStatus("请先输入消息再发送。", "warning");
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
    interruptCurrent("已打断。");
  });

  voiceButton.addEventListener("click", function () {
    if (mediaRecorder) stopRecording();
    else startRecording();
  });

  refreshHealth();
  messageInput.focus();
})();
