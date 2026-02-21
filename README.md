# 🛫 Soji AI — Airworthiness Directive Recognition Pipeline

Automated pipeline for extracting and classifying Airworthiness Directives (AD) against aircraft fleet data using OCR and LLM-powered document understanding.

## Overview

Soji AI reads AD PDF documents, extracts structured applicability data (affected models, MSN constraints, modification/SB exclusions), and classifies your fleet aircraft as **Affected** or **Not Applicable** against each AD.

Two pipeline modes are available:

| Mode | How it works | Best for |
|------|-------------|----------|
| `ocr` | PDF → Images → PaddleOCR → Text → Gemini LLM | Cost-efficient, works with scanned PDFs |
| `llm` | PDF → Images → Gemini LLM (multimodal) | Higher accuracy, native image understanding |

---

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- [Poppler](https://poppler.freedesktop.org/) (for `pdf2image`)
- A [Google AI API key](https://aistudio.google.com/apikey) (Gemini)
- **GPU mode only**: NVIDIA GPU with CUDA 13.0+ drivers

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/naufal-fachri/soji-ai-assignment.git
cd soji-ai-assignment
```

### 2. Install system dependencies

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y poppler-utils libgl1 libglib2.0-0
```

### 3. Set up environment variables

```bash
cp .env.example .env
```

Edit `.env` and add your Google API key:

```env
GOOGLE_API_KEY=your-api-key-here
```

### 4. Install Python dependencies

Choose **one** of the following based on your hardware:

#### Option A: GPU (NVIDIA CUDA 13.0+)

```bash
uv sync --frozen
source .venv/bin/activate
```

Verify the installation:

```bash
python -c "import paddle; print('✅ paddle', paddle.__version__)"
```

#### Option B: CPU only (no NVIDIA GPU)

```bash
uv sync --frozen
source .venv/bin/activate

# Swap paddlepaddle-gpu for CPU version
uv pip uninstall paddlepaddle-gpu paddlepaddle
uv pip install paddlepaddle==3.3.0 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
```

Verify the installation:

```bash
python -c "import paddle; print('✅ paddle', paddle.__version__)"
```

---

## Quick Start

> Make sure you have completed the [Installation](#installation) steps and activated the virtual environment before proceeding.

```bash
python -m src.run \
    --ad-files <path-to-ad-pdf> [<path-to-ad-pdf> ...] \
    --test-data <path-to-test-csv> \
    --save-dir <output-directory>
```

---

## Usage

### Examples

**Single AD file (OCR mode, CPU):**

```bash
python -m src.run \
    --device cpu \
    --ad-files documents/EASA_AD_2025-0254R1_1.pdf \
    --test-data test/ad_test_data.csv \
    --save-dir results/
```

**Multiple AD files (OCR mode, GPU):**

```bash
python -m src.run \
    --device gpu:0 \
    --ad-files documents/EASA_AD_2025-0254R1_1.pdf documents/EASA_AD_US-2025-23-53_1.pdf \
    --test-data test/ad_test_data.csv \
    --save-dir results/
```

**LLM mode (multimodal, images sent directly to Gemini):**

```bash
python -m src.run \
    --mode llm \
    --ad-files documents/EASA_AD_2025-0254R1_1.pdf \
    --test-data test/ad_test_data.csv \
    --save-dir results/
```

### CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--mode` | `ocr` | Pipeline mode: `ocr` or `llm` |
| `--device` | From `.env` | Inference device: `cpu`, `gpu:0`, etc. |
| `--ad-files` | *required* | One or more AD PDF file paths |
| `--test-data` | *required* | Path to fleet test data CSV |
| `--save-dir` | `./results` | Output directory for results |
| `--no-cleanup` | `false` | Keep temp files for debugging |
| `--no-ocr-viz` | `false` | Skip OCR bbox visualization (OCR mode only) |

---

## Test Data Format

The test CSV file should contain the following columns:

| Column | Type | Description |
|--------|------|-------------|
| `aircraft_model` | string | Aircraft type/model (e.g., `A320-214`) |
| `msn` | integer | Manufacturer Serial Number |
| `modifications_applied` | string | Comma-separated mods/SBs applied (e.g., `mod 24591, SB A320-57-1089`). Use `None` or leave empty if none. |

**Example `test_data.csv`:**

```csv
aircraft_model,msn,modifications_applied
A320-214,1234,mod 24591
A320-232,5678,None
A321-111,9999,SB A320-57-1089
A320-211,1111,
```

---

## Output

Results are saved in a timestamped directory: `<save-dir>/<run_id>_<YYMMDD>/`

```
results/
└── a1b2c3d4_250220/
    ├── ad_classification_results.csv    # Fleet classification results
    ├── ad_extractions.json              # Raw LLM extraction data
    ├── EASA_AD_2025-0254R1_1_ocr_viz/   # OCR bbox visualizations
    │   ├── page_1_ocr_viz.png
    │   ├── page_2_ocr_viz.png
    │   └── ...
    └── EASA_AD_US-2025-23-53_1_ocr_viz/
        ├── page_1_ocr_viz.png
        └── ...
```

### Classification Results

The output CSV appends a column for each AD with one of the following statuses:

| Status | Meaning |
|--------|---------|
| ✅ Affected | Aircraft is within AD scope and requires action |
| ❌ Not applicable | Aircraft model/MSN is outside AD scope |
| ❌ Not Affected | Aircraft is excluded by an applied modification or SB |

| aircraft_model   |   msn | modifications_applied   | EASA_AD_2025-0254R1_1   | EASA_AD_US-2025-23-53_1   |
|------------------|-------|-------------------------|-------------------------|---------------------------|
| MD-11            | 48123 | nan                     | ❌ Not applicable       | ✅ Affected               |
| DC-10-30F        | 47890 | nan                     | ❌ Not applicable       | ✅ Affected               |
| Boeing 737-800   | 30123 | nan                     | ❌ Not applicable       | ❌ Not applicable         |
| A320-214         |  5234 | nan                     | ✅ Affected             | ❌ Not applicable         |
| A320-232         |  6789 | mod 24591 (production)  | ❌ Not Affected         | ❌ Not applicable         |
| A320-214         |  7456 | SB A320-57-1089 Rev 04  | ❌ Not Affected         | ❌ Not applicable         |
| A321-111         |  8123 | nan                     | ✅ Affected             | ❌ Not applicable         |
| A321-112         |   364 | mod 24977 (production)  | ❌ Not Affected         | ❌ Not applicable         |
| A319-100         |  9234 | nan                     | ❌ Not applicable       | ❌ Not applicable         |
| MD-10-10F        | 46234 | nan                     | ❌ Not applicable       | ✅ Affected               |

---

## Docker

Two Dockerfiles are provided depending on your hardware:

| File | Base Image | Requires |
|------|-----------|----------|
| `Dockerfile` | `nvidia/cuda:13.0.2` | NVIDIA GPU + [nvidia-container-toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) |
| `Dockerfile.cpu` | `ubuntu:24.04` | No GPU required |

### GPU

```bash
# Build
docker build -t soji-ai:gpu -f Dockerfile .

# Run
docker run --gpus all --env-file .env \
    -v $(pwd)/documents:/app/documents \
    -v $(pwd)/test:/app/test \
    -v $(pwd)/results:/app/results \
    soji-ai:gpu \
    --device gpu:0 \
    --ad-files documents/EASA_AD_2025-0254R1_1.pdf \
    --test-data test/ad_test_data.csv \
    --save-dir results/
```

> **Prerequisite:** Requires `nvidia-container-toolkit` installed on the host:
> ```bash
> sudo apt-get install -y nvidia-container-toolkit
> sudo systemctl restart docker
> ```

### CPU

```bash
# Build
docker build -t soji-ai:cpu -f Dockerfile.cpu .

# Run
docker run --env-file .env \
    -v $(pwd)/documents:/app/documents \
    -v $(pwd)/test:/app/test \
    -v $(pwd)/results:/app/results \
    soji-ai:cpu \
    --ad-files documents/EASA_AD_2025-0254R1_1.pdf \
    --test-data test/ad_test_data.csv \
    --save-dir results/
```

> **Note:** The CPU image uses `paddlepaddle` (CPU-only) instead of `paddlepaddle-gpu`, so no NVIDIA drivers or GPU are required. The `--device cpu` flag is set automatically.

### Docker Tips

- `--env-file .env` passes your `GOOGLE_API_KEY` without baking it into the image.
- Volume mounts (`-v`) map your local `documents/`, `test/`, and `results/` directories into the container.
- On first run, PaddleOCR will download detection and recognition models (~50MB). Subsequent runs use cached models.
- The GPU Dockerfile supports both `--device gpu:0` and `--device cpu` at runtime.
- To clean up unused Docker images: `docker image prune -a`

---

## Configuration

All settings can be configured via `.env` file:

```env
# Required
GOOGLE_API_KEY=your-api-key-here

# LLM (optional)
GEMINI_MODEL=gemini-2.5-flash
GEMINI_TEMPERATURE=0.1

# OCR Engine (optional)
OCR_DEVICE=gpu:0
OCR_PRECISION=fp16
OCR_DET_MODEL=PP-OCRv5_mobile_det
OCR_REC_MODEL=PP-OCRv5_mobile_rec
OCR_CPU_THREADS=8
OCR_Y_THRESHOLD=15.0
OCR_SAVE_VIZ=True

# Pipeline (optional)
DPI=300
```

---

## Project Structure

```
soji-ai/
├── src/
│   ├── __init__.py
│   ├── config.py                  # Settings from .env
│   ├── run.py                     # CLI entrypoint
│   ├── core/
│   │   ├── __init__.py
│   │   ├── prompt.py              # LLM system prompts
│   │   ├── schemas.py             # Pydantic output schemas
│   │   └── utils.py               # Shared utility function
│   └── pipeline/
│       ├── __init__.py
│       ├── llm_pipeline.py        # Multimodal LLM pipeline
│       └── ocr_llm_pipeline.py    # OCR + LLM pipeline
├── documents/                     # AD PDF files
├── notebooks/                     # Notebooks
├── test/                          # Test data CSVs
├── results/                       # Output directory
├── Dockerfile                     # GPU Docker image
├── Dockerfile.cpu                 # CPU Docker image
├── .dockerignore
├── .env.example
├── pyproject.toml
└── README.md
```

---

## License

Proprietary — Internal use only.