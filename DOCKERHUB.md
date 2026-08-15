# paperless-paddle-ocr

A CPU-friendly sidecar that OCRs [paperless-ngx](https://github.com/paperless-ngx/paperless-ngx)
documents with **PaddleOCR PP-OCRv6** and writes the extracted text back via
the paperless-ngx API.

- Full source, issue tracker, and docs: https://github.com/silentprior/paperless-paddle-ocr
- No poppler / system OCR binaries needed (PDF pages render via PyMuPDF)
- Runs as non-root, ships a `HEALTHCHECK`, multi-arch (`linux/amd64`, `linux/arm64`)
- Fully configured via environment variables — no image rebuild needed to tune

## Supported tags

- `latest` — most recent tagged release
- `1.0.0`, `1.0`, `1` — semantic version tags (immutable per-patch tag recommended for production)

## Quickstart

```bash
docker run -d \
  --name paperless-paddle-ocr \
  -e PAPERLESS_BASE_URL="http://your-paperless-host:8000" \
  -e PAPERLESS_API_TOKEN="your_token_here" \
  -e PAPERLESS_INPUT_TAG="to_ocr" \
  -e PAPERLESS_OUTPUT_TAG="ocr_done" \
  -v paddle-ocr-cache:/app/.paddle_cache \
  -p 8081:8080 \
  YOUR_DOCKERHUB_USERNAME/paperless-paddle-ocr:latest
```

Or with Docker Compose — see the
[docker-compose.yml](https://github.com/silentprior/paperless-paddle-ocr/blob/main/docker-compose.yml)
in the source repo.

Tag any paperless-ngx document with your `PAPERLESS_INPUT_TAG` (default:
`to_ocr`) and the worker will pick it up on its next poll.

## Key environment variables

| Variable | Default | Description |
|---|---|---|
| `PAPERLESS_BASE_URL` | *(required)* | URL of your paperless-ngx instance |
| `PAPERLESS_API_TOKEN` | *(required)* | Paperless API token |
| `PAPERLESS_INPUT_TAG` | *(none — all docs)* | Only process documents with this tag |
| `PAPERLESS_OUTPUT_TAG` | *(none)* | Tag applied after a successful OCR |
| `PAPERLESS_ERROR_TAG` | *(none)* | Tag applied if OCR fails |
| `PAPERLESS_DRY_RUN` | `false` | Log intended changes without writing them |
| `PAPERLESS_RUN_MODE` | `daemon` | `daemon` (loop) or `oneshot` |
| `OCR_LANG` | `en` | PaddleOCR language code |
| `OCR_TIER` | `small` | `tiny` \| `small` \| `medium` |
| `OCR_ENGINE` | `paddle` | `paddle` \| `onnxruntime` \| `openvino` |
| `OCR_DPI` | `200` | PDF render DPI |
| `OCR_THREADS` | `4` | CPU threads for inference |

Full reference: see the docstring in
[`ocr_worker.py`](https://github.com/silentprior/paperless-paddle-ocr/blob/main/ocr_worker.py)
or [`docs/CONFIGURATION.md`](https://github.com/silentprior/paperless-paddle-ocr/blob/main/docs/CONFIGURATION.md).

## License

MIT — see the [source repository](https://github.com/silentprior/paperless-paddle-ocr) for details.
