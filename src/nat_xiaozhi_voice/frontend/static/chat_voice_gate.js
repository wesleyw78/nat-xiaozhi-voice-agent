(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.XiaozhiVoiceGate = factory();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  function createVoiceGate(options) {
    const config = Object.assign(
      {
        idleFloor: 0.012,
        floorSmoothing: 0.04,
        idleMinThreshold: 0.045,
        busyMinThreshold: 0.11,
        idleHoldMs: 260,
        busyHoldMs: 480,
        speechReleaseMinThreshold: 0.026,
      },
      options || {},
    );

    let floor = config.idleFloor;
    let candidateSince = 0;

    function updateFloor(rms, isCandidate) {
      if (isCandidate) return;
      floor = floor * (1 - config.floorSmoothing) + rms * config.floorSmoothing;
      floor = Math.max(0.004, Math.min(0.045, floor));
    }

    function getStartThreshold(isBusy) {
      const adaptive = floor * (isBusy ? 4.2 : 2.8) + (isBusy ? 0.045 : 0.018);
      return Math.max(isBusy ? config.busyMinThreshold : config.idleMinThreshold, adaptive);
    }

    function getReleaseThreshold() {
      return Math.max(config.speechReleaseMinThreshold, floor * 1.8 + 0.012);
    }

    function reset() {
      candidateSince = 0;
    }

    function update(sample) {
      const rms = Number(sample.rms) || 0;
      const now = Number(sample.now) || 0;
      const isBusy = Boolean(sample.isBusy);
      const threshold = getStartThreshold(isBusy);
      const holdMs = isBusy ? config.busyHoldMs : config.idleHoldMs;
      const isCandidate = rms >= threshold;

      updateFloor(rms, isCandidate);

      if (!isCandidate) {
        reset();
        return "idle";
      }

      if (!candidateSince) {
        candidateSince = now;
        return "candidate";
      }

      if (now - candidateSince >= holdMs) {
        reset();
        return "start";
      }

      return "candidate";
    }

    return {
      update,
      reset,
      getStartThreshold,
      getReleaseThreshold,
    };
  }

  return { createVoiceGate };
});
