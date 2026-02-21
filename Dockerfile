# ============================================================
#  soji-ai — AD Recognition Pipeline
#  Base: NVIDIA CUDA 13.0 + cuDNN (paddlepaddle-gpu cu130)
# ============================================================
FROM nvidia/cuda:13.0.2-cudnn-runtime-ubuntu24.04
ENV DEBIAN_FRONTEND=noninteractive

# ------------------------------------------------------------ #
#  System dependencies
# ------------------------------------------------------------ #
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.12 \
    python3.12-venv \
    python3.12-dev \
    python3-pip \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    fonts-dejavu-core \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------ #
#  Install uv
# ------------------------------------------------------------ #
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# ------------------------------------------------------------ #
#  App setup
# ------------------------------------------------------------ #
WORKDIR /app
COPY . .
RUN uv sync --frozen --no-dev

# Verify
RUN /app/.venv/bin/python -c "import paddle; print('✅ paddle', paddle.__version__)"

# ------------------------------------------------------------ #
#  Environment
# ------------------------------------------------------------ #
ENV PYTHONUNBUFFERED=1
ENV PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
ENV PATH="/app/.venv/bin:$PATH"

# ------------------------------------------------------------ #
#  Entrypoint
# ------------------------------------------------------------ #
ENTRYPOINT ["python", "-m", "src.run"]