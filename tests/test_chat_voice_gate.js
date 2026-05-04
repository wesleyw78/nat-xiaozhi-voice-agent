const assert = require("node:assert/strict");
const test = require("node:test");

const { createVoiceGate } = require("../src/nat_xiaozhi_voice/frontend/static/chat_voice_gate.js");

test("ignores short noise spikes before starting recording", () => {
  const gate = createVoiceGate();
  [0.01, 0.012, 0.011, 0.01, 0.012, 0.011].forEach((rms, index) => {
    assert.equal(gate.update({ rms, now: index * 16, isBusy: false }), "idle");
  });

  assert.equal(gate.update({ rms: 0.09, now: 120, isBusy: false }), "candidate");
  assert.equal(gate.update({ rms: 0.012, now: 140, isBusy: false }), "idle");
});

test("starts recording after sustained speech above adaptive floor", () => {
  const gate = createVoiceGate();
  [0.008, 0.009, 0.01, 0.011, 0.01, 0.009].forEach((rms, index) => {
    gate.update({ rms, now: index * 30, isBusy: false });
  });

  assert.equal(gate.update({ rms: 0.07, now: 240, isBusy: false }), "candidate");
  assert.equal(gate.update({ rms: 0.075, now: 380, isBusy: false }), "candidate");
  assert.equal(gate.update({ rms: 0.08, now: 540, isBusy: false }), "start");
});

test("requires stronger sustained speech to barge in during playback", () => {
  const gate = createVoiceGate();
  [0.009, 0.01, 0.011, 0.01, 0.009, 0.01].forEach((rms, index) => {
    gate.update({ rms, now: index * 30, isBusy: false });
  });

  assert.equal(gate.update({ rms: 0.07, now: 240, isBusy: true }), "idle");
  assert.equal(gate.update({ rms: 0.13, now: 340, isBusy: true }), "candidate");
  assert.equal(gate.update({ rms: 0.13, now: 620, isBusy: true }), "candidate");
  assert.equal(gate.update({ rms: 0.13, now: 830, isBusy: true }), "start");
});
