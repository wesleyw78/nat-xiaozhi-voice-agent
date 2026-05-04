const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const root = path.resolve(__dirname, "..");

test("chat page uses click-to-talk instead of automatic voice gate", () => {
  const html = fs.readFileSync(
    path.join(root, "src/nat_xiaozhi_voice/frontend/static/chat.html"),
    "utf8",
  );
  const script = fs.readFileSync(
    path.join(root, "src/nat_xiaozhi_voice/frontend/static/chat.js"),
    "utf8",
  );

  assert.equal(html.includes("chat_voice_gate.js"), false);
  assert.equal(script.includes("voiceGate"), false);
  assert.equal(script.includes("setVoiceStatus(\"正在录音，请再次点击发送。\""), true);
  assert.equal(script.includes("voiceButton.textContent = \"发送语音\""), true);
});

test("chat page presents user-facing copy in Chinese", () => {
  const html = fs.readFileSync(
    path.join(root, "src/nat_xiaozhi_voice/frontend/static/chat.html"),
    "utf8",
  );
  const script = fs.readFileSync(
    path.join(root, "src/nat_xiaozhi_voice/frontend/static/chat.js"),
    "utf8",
  );

  assert.equal(html.includes("<title>小智语音对话</title>"), true);
  assert.equal(html.includes(">自动播放<"), true);
  assert.equal(html.includes(">开始说话<"), true);
  assert.equal(html.includes(">发送<"), true);
  assert.equal(script.includes('role === "user" ? "我" : "小智"'), true);
  assert.equal(script.includes("服务已连接。"), true);

  for (const oldText of [
    "Web Chat",
    "Checking service",
    "Auto play",
    "Start voice",
    "Interrupt",
    "Replay",
    "Type a message",
    "Voice idle",
    "Playing reply audio",
  ]) {
    assert.equal(html.includes(oldText) || script.includes(oldText), false, oldText);
  }
});
