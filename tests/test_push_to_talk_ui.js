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
  assert.equal(script.includes("setVoiceStatus(\"Recording. Click again to send.\""), true);
  assert.equal(script.includes("voiceButton.textContent = \"Send voice\""), true);
});
