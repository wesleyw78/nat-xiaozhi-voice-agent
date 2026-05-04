FROM nvidia/cuda:12.8.1-runtime-ubuntu24.04

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Asia/Taipei \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# ── System packages ──────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3.12 python3.12-venv python3.12-dev python3-pip \
        build-essential \
        ffmpeg \
        libopus-dev libopus0 libsndfile1-dev \
        git curl ca-certificates tzdata \
    && ln -sf /usr/bin/python3.12 /usr/bin/python3 \
    && ln -sf /usr/bin/python3.12 /usr/bin/python \
    && rm -f /usr/lib/python3.12/EXTERNALLY-MANAGED \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Install uv for fast dependency resolution ────────────────────────────────
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# ── Python dependencies (cached layer — only rebuilds when pyproject changes) ─
COPY pyproject.toml ./
RUN printf 'torch==2.11.0+cu128\ntorchaudio==2.11.0+cu128\n' > /tmp/torch-cu128-constraints.txt && \
    mkdir -p src/nat_xiaozhi_voice && \
    touch src/nat_xiaozhi_voice/__init__.py && \
    uv pip install --system -e . \
        --extra-index-url https://download.pytorch.org/whl/cu128 \
        --index-strategy unsafe-best-match \
        --constraint /tmp/torch-cu128-constraints.txt && \
    rm -rf src/nat_xiaozhi_voice

# ── Download models ──────────────────────────────────────────────────────────
RUN mkdir -p models && \
    for attempt in 1 2 3 4 5; do \
        git clone --depth 1 https://github.com/snakers4/silero-vad.git models/snakers4_silero-vad && break; \
        status=$?; \
        echo "silero-vad download failed on attempt $attempt; retrying in $((attempt * 10))s"; \
        rm -rf models/snakers4_silero-vad; \
        sleep $((attempt * 10)); \
        if [ "$attempt" = "5" ]; then exit $status; fi; \
    done && \
    for attempt in 1 2 3 4 5; do \
        python3 -c "from huggingface_hub import snapshot_download; snapshot_download('FunAudioLLM/SenseVoiceSmall', local_dir='models/SenseVoiceSmall')" && break; \
        status=$?; \
        echo "SenseVoiceSmall download failed on attempt $attempt; retrying in $((attempt * 20))s"; \
        rm -rf models/SenseVoiceSmall/.cache; \
        sleep $((attempt * 20)); \
        if [ "$attempt" = "5" ]; then exit $status; fi; \
    done && \
    test -f models/SenseVoiceSmall/model.pt

# ── Copy application source ─────────────────────────────────────────────────
COPY src/ src/
COPY configs/ configs/
COPY knowledge/ knowledge/
COPY ./client/py-xiaozhi-ws.py test_vlm.py ./

# ── Re-install in editable mode with actual source ───────────────────────────
RUN uv pip install --system -e . --no-deps

# ── NAT timezone config ─────────────────────────────────────────────────────
RUN mkdir -p /root/.config/nat && \
    echo '{"fallback_timezone": "system"}' > /root/.config/nat/config.json

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

ENTRYPOINT ["nat", "start", "xiaozhi_voice"]
CMD ["--config_file", "/app/configs/xiaozhi_voice.yml"]
