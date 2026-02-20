# ============================================================
#  soji-ai — AD Recognition Pipeline
#  Base: NVIDIA CUDA 13.0 + cuDNN (matches paddlepaddle-gpu cu130)
# ============================================================

FROM nvidia/cuda:13.0.2-cudnn-runtime-ubuntu24.04

# Prevent interactive prompts
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

# Copy dependency files first (for layer caching)
COPY pyproject.toml uv.lock* ./

# Install dependencies
RUN uv sync --frozen --no-dev --no-install-project

# Copy source code
COPY . .

# Install the project itself
RUN uv sync --frozen --no-dev

# ------------------------------------------------------------ #
#  PaddleOCR model cache (pre-download to avoid runtime delay)
# ------------------------------------------------------------ #
# Uncomment below to bake models into the image:
# RUN uv run python -c "from paddleocr import PaddleOCR; PaddleOCR(text_detection_model_name='PP-OCRv5_mobile_det', text_recognition_model_name='PP-OCRv5_mobile_rec', device='cpu')"

# ------------------------------------------------------------ #
#  Environment
# ------------------------------------------------------------ #
ENV PYTHONUNBUFFERED=1
ENV PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True

# ------------------------------------------------------------ #
#  Entrypoint
# ------------------------------------------------------------ #
ENTRYPOINT ["uv", "run", "python", "-m", "src.run"]