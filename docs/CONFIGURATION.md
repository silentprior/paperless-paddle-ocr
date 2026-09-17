# Configuration reference

All configuration is via environment variables — there are no config files.
Set these in `docker-compose.yml`, a `docker run -e ...`, or your `.env` file
(compose only).

## Paperless connection

| Variable | Default | Description |
|---|---|---|
| `PAPERLESS_BASE_URL` | *(required)* | Base URL of your paperless-ngx instance, no trailing slash |
| `PAPERLESS_API_TOKEN` | *(required)* | API token (Settings → My Profile → API Token in paperless-ngx) |
| `PAPERLESS_VERIFY_SSL` | `true` | Set `false` to skip TLS cert verification (e.g. self-signed certs) |

## Tagging / workflow

| Variable | Default | Description |
|---|---|---|
| `PAPERLESS_INPUT_TAG` | *(none — all docs)* | Only process documents carrying this tag |
| `PAPERLESS_OUTPUT_TAG` | *(none)* | Tag applied after a successful OCR |
| `PAPERLESS_ERROR_TAG` | *(none)* | Tag applied if OCR fails; removed automatically on a later success |
| `PAPERLESS_PROCESSING_TAG` | `paddle_processing` | Temporary internal tag applied while a document is being OCR'd |
| `PAPERLESS_PROCESSED_TAG` | `paddle_processed` | Tag used to mark a document as successfully processed |
| `PAPERLESS_TRACKING_TAG` | `paddle_processed` | Legacy alias for `PAPERLESS_PROCESSED_TAG`; used only when the preferred variable is unset |
| `PAPERLESS_REPROCESS` | `false` | If `true`, ignore the processed tag and OCR matching docs again; documents with the processing tag are still skipped |
| `PAPERLESS_DRY_RUN` | `false` | Log what would change without writing anything to paperless |

## Run behaviour

| Variable | Default | Description |
|---|---|---|
| `PAPERLESS_RUN_MODE` | `daemon` | `daemon` (loop forever) or `oneshot` (run once, exit) |
| `PAPERLESS_INTERVAL_SECONDS` | `3600` | Seconds between polling runs in daemon mode |
| `PAPERLESS_DELAY_SECONDS` | `1` | Seconds to sleep between documents within a run |
| `PAPERLESS_STARTUP_TIMEOUT` | `60` | Seconds to wait for the paperless API to become reachable at boot |
| `PAPERLESS_HEALTH_PORT` | `8080` | Port for the internal `/health` endpoint used by the Docker `HEALTHCHECK` |

## OCR engine (PaddleOCR PP-OCRv6)

| Variable | Default | Description |
|---|---|---|
| `OCR_LANG` | `en` | Language code — e.g. `en`, `ch`, `fr`, `de`, `ja` |
| `OCR_DPI` | `200` | PDF render DPI. Higher = better quality, slower |
| `OCR_TIER` | `small` | Model tier: `tiny` (fastest) \| `small` (balanced, default) \| `medium` (most accurate, slowest) |
| `OCR_ENGINE` | `paddle` | Inference backend: `paddle` \| `onnxruntime` \| `openvino`. `openvino` is notably faster on Intel CPUs but requires the `openvino` package (see `requirements.txt`) |
| `OCR_ENABLE_MKLDNN` | `false` | Enable the oneDNN CPU backend. Off by default — it can crash on some CPU/model combinations |
| `OCR_THREADS` | `4` | CPU threads PaddleOCR uses for inference |
| `OCR_CACHE_DIR` | `/app/.paddle_cache` | Where model weights are downloaded/cached. Mount this as a volume so models survive restarts/rebuilds |

## Logging

| Variable | Default | Description |
|---|---|---|
| `LOG_LEVEL` | `INFO` | Python logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

## Enabling the OpenVINO backend

The `openvino` Python package isn't installed by default (it adds
meaningful image size for users who don't need it). To enable
`OCR_ENGINE=openvino`:

1. Uncomment the `openvino` line in `requirements.txt`
2. Rebuild the image: `docker compose build`
3. Set `OCR_ENGINE=openvino` in your environment
