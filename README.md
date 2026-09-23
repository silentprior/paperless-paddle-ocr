# paperless-paddle-ocr

[![CI](https://github.com/silentprior/paperless-paddle-ocr/actions/workflows/ci.yml/badge.svg)](https://github.com/silentprior/paperless-paddle-ocr/actions/workflows/ci.yml)
[![Docker Image](https://github.com/silentprior/paperless-paddle-ocr/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/silentprior/paperless-paddle-ocr/actions/workflows/docker-publish.yml)
[![Docker Pulls](https://img.shields.io/docker/pulls/silentprior/paperless-paddle-ocr)](https://hub.docker.com/r/silentprior/paperless-paddle-ocr)
[![Docker Image Size](https://img.shields.io/docker/image-size/silentprior/paperless-paddle-ocr/latest)](https://hub.docker.com/r/silentprior/paperless-paddle-ocr)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A small, CPU-friendly sidecar worker that OCRs [paperless-ngx](https://github.com/paperless-ngx/paperless-ngx)
documents using **[PaddleOCR PP-OCRv6](https://github.com/PaddlePaddle/PaddleOCR)** and writes the extracted
text back to paperless via its REST API.

It's useful when paperless-ngx's built-in OCR (Tesseract) struggles with a
document, or when you specifically want PaddleOCR's accuracy on scans,
handwriting-adjacent text, or non-Latin scripts.

## Features

- **PP-OCRv6** — the current PaddleOCR model generation, CPU-friendly, with
  optional OpenVINO acceleration on Intel hardware
- **No poppler / system OCR binaries** — PDF pages are rendered with
  [PyMuPDF](https://pymupdf.readthedocs.io/), a pure-Python wheel
- **Tag-driven workflow** — pick up documents by an input tag, mark them
  done/failed with output/error tags, skip anything already processed
- **Fully configurable via environment variables** — no code changes needed
  for day-to-day tuning (language, model tier, DPI, engine, thread count...)
- **Daemon or one-shot** run modes, dry-run mode for safe testing
- **Runs as non-root**, ships a Docker `HEALTHCHECK`, multi-arch image
  (`linux/amd64`, `linux/arm64`)

## Quickstart

### 1. Docker Compose (recommended)

```bash
git clone https://github.com/silentprior/paperless-paddle-ocr.git
cd paperless-paddle-ocr
cp .env.example .env
# edit .env and set PAPERLESS_API_TOKEN
# edit docker-compose.yml and set PAPERLESS_BASE_URL to your paperless instance

docker compose up -d
docker compose logs -f
```

### 2. Plain `docker run`

```bash
docker run -d \
  --name paperless-paddle-ocr \
  -e PAPERLESS_BASE_URL="http://paperless-ngx:8000" \
  -e PAPERLESS_API_TOKEN="your_token_here" \
  -e PAPERLESS_INPUT_TAG="to_ocr" \
  -e PAPERLESS_OUTPUT_TAG="ocr_done" \
  -v paddle-ocr-cache:/app/.paddle_cache \
  -p 8081:8080 \
  silentprior/paperless-paddle-ocr:latest
```

Then in paperless-ngx, tag any document you want OCR'd with your
`PAPERLESS_INPUT_TAG` (default: `to_ocr`). The worker polls on the interval
you configure and writes extracted text back into the document's content.

## How it works

1. Poll paperless-ngx for documents matching `PAPERLESS_INPUT_TAG` that
  don't have `PAPERLESS_PROCESSING_TAG` and, unless `PAPERLESS_REPROCESS=true`,
  don't have `PAPERLESS_PROCESSED_TAG`
2. Apply `PAPERLESS_PROCESSING_TAG` to claim the document before OCR
3. Download each matching document
4. If it's a PDF, render each page to an image with PyMuPDF; otherwise use
   the image directly
5. Run PaddleOCR PP-OCRv6 over each page/image
6. `PATCH` the document's `content` field in paperless-ngx with the
  extracted text, remove the processing tag, and apply the processed/output
  tag. On OCR failure, remove the processing tag and apply the error tag; on
  final-update failure, make a best-effort attempt to remove the processing tag.
7. Sleep for `PAPERLESS_INTERVAL_SECONDS` and repeat (daemon mode), or exit
   (oneshot mode)

## Configuration

All configuration is via environment variables. See
[`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) for the full reference
table, or the docstring at the top of [`ocr_worker.py`](ocr_worker.py).

Having trouble with a large document failing to update after OCR? See
[Troubleshooting](docs/CONFIGURATION.md#troubleshooting).

Most commonly changed:

| Variable | Default | Description |
|---|---|---|
| `PAPERLESS_BASE_URL` | *(required)* | URL of your paperless-ngx instance |
| `PAPERLESS_API_TOKEN` | *(required)* | Paperless API token |
| `PAPERLESS_INPUT_TAG` | *(none, all docs)* | Only process documents with this tag |
| `PAPERLESS_REPROCESS` | `false` | Reprocess completed documents; documents being processed remain excluded |
| `OCR_LANG` | `en` | PaddleOCR language code |
| `OCR_TIER` | `small` | Model tier: `tiny` \| `small` \| `medium` |
| `OCR_ENGINE` | `paddle` | Backend: `paddle` \| `onnxruntime` \| `openvino` |
| `PAPERLESS_DRY_RUN` | `false` | Log intended changes without writing them |

## Building the image locally

```bash
docker build -t paperless-paddle-ocr:dev .
```

Multi-arch build (what CI does on release):

```bash
docker buildx build --platform linux/amd64,linux/arm64 -t paperless-paddle-ocr:dev .
```

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

ruff check .          # lint
mypy ocr_worker.py    # type check
pytest                # unit tests (heavy OCR deps are stubbed, see tests/conftest.py)
```

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the full workflow, and
[`docs/`](docs) for architecture notes.

## Status / limitations

- CPU-only by design; no GPU support is wired up
- Tested against paperless-ngx's documents/tags API; large paperless
  instances with thousands of matching documents per run haven't been
  load-tested
- OCR quality depends heavily on scan quality and the chosen `OCR_TIER`/`OCR_DPI`

Bug reports and PRs welcome — see [Contributing](#development).

## License

[MIT](LICENSE). This project talks to paperless-ngx over its HTTP API only —
it does not bundle or link against paperless-ngx or PaddleOCR source code, so
their own licenses (GPL-3.0 and Apache-2.0, respectively) are unaffected by
and don't apply to this repository.
