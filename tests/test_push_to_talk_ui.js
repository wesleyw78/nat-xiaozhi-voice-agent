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
  assert.equal(html.includes(">发送文字<"), true);
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

test("voice and text entry are integrated in the composer", () => {
  const html = fs.readFileSync(
    path.join(root, "src/nat_xiaozhi_voice/frontend/static/chat.html"),
    "utf8",
  );

  assert.equal(html.includes('class="composer-status"'), true);
  assert.equal(html.includes('class="composer-main"'), true);
  assert.equal(html.includes('class="composer-actions"'), true);
  assert.equal(html.includes('<section class="voice-row"'), false);

  const composerStart = html.indexOf('<form id="composerForm"');
  const composerEnd = html.indexOf("</form>", composerStart);
  const composer = html.slice(composerStart, composerEnd);
  assert.equal(composer.includes('id="messageInput"'), true);
  assert.equal(composer.includes('id="voiceButton"'), true);
  assert.equal(composer.includes('id="sendButton"'), true);
  assert.equal(composer.includes('id="voiceStatus"'), true);
  assert.equal(composer.includes('id="volumeMeter"'), true);

  const toolbarStart = html.indexOf('class="toolbar"');
  const toolbarEnd = html.indexOf("</div>", toolbarStart);
  const toolbar = html.slice(toolbarStart, toolbarEnd);
  assert.equal(toolbar.includes('id="voiceButton"'), false);
});

test("chat page hides device id controls and keeps header and composer fixed", () => {
  const html = fs.readFileSync(
    path.join(root, "src/nat_xiaozhi_voice/frontend/static/chat.html"),
    "utf8",
  );
  const styles = fs.readFileSync(
    path.join(root, "src/nat_xiaozhi_voice/frontend/static/chat.css"),
    "utf8",
  );
  const script = fs.readFileSync(
    path.join(root, "src/nat_xiaozhi_voice/frontend/static/chat.js"),
    "utf8",
  );

  assert.equal(html.includes("device-row"), false);
  assert.equal(html.includes("设备 ID"), false);
  assert.equal(html.includes("saveDeviceButton"), false);
  assert.equal(html.includes("deviceIdInput"), false);
  assert.equal(script.includes("deviceIdInput"), false);
  assert.equal(script.includes("saveDeviceButton"), false);

  assert.match(styles, /\.app-shell\s*{[^}]*height:\s*100vh/s);
  assert.match(styles, /\.topbar\s*{[^}]*position:\s*sticky/s);
  assert.match(styles, /\.composer\s*{[^}]*position:\s*sticky/s);
  assert.match(styles, /\.message-list\s*{[^}]*overflow-y:\s*auto/s);
});
