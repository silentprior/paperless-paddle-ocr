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
| `OCR_CACHE_DIR` | `/app/.paddle_cache` | Where model weights are downloaded/cached, and where extracted OCR text is cached (under `results/`) before a paperless update. Mount this as a volume so models survive restarts/rebuilds and OCR results survive a failed update — see [Troubleshooting](#troubleshooting) |

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

## Troubleshooting

### Update fails with an oversized document ("Bad Request" / 400)

Symptom: the worker logs an update failure right after OCR finishes on a
large, image-heavy PDF, something like:

```
[DOC:123] Update failed: 400 Client Error: Bad Request for url: ... | payload=3123456 bytes | response=...
[DOC:123] Payload exceeds Django's default 2.5MB request limit (DATA_UPLOAD_MAX_MEMORY_SIZE). ...
```

paperless-ngx runs on Django, which by default rejects any request body
larger than 2.5 MB (`DATA_UPLOAD_MAX_MEMORY_SIZE`). A long, OCR'd document
can easily produce a `content` field bigger than that, so the PATCH that
writes the extracted text back is rejected — the response body is often a
generic "Bad Request" page rather than a useful error, since paperless-ngx
doesn't run with Django's `DEBUG` on in production.

The worker itself can't raise this limit — it lives on the paperless-ngx
side, and as of the current
[paperless-ngx configuration reference](https://docs.paperless-ngx.com/configuration/)
there is no `PAPERLESS_*` environment variable for it. Some deployments
work around this by overriding `DATA_UPLOAD_MAX_MEMORY_SIZE` at the Django
level — mounting a small settings module that wildcard-imports
`paperless.settings` and overrides the value, then pointing
`DJANGO_SETTINGS_MODULE` at it. See
[paperless-ngx discussion #3228](https://github.com/paperless-ngx/paperless-ngx/discussions/3228)
for this same pattern applied to LDAP config (not `DATA_UPLOAD_MAX_MEMORY_SIZE`
specifically); several users there also hit a `ModuleNotFoundError` until
the settings file was mounted at the exact path Django expected, so treat
this as an unofficial, unverified-for-this-setting workaround rather than
a documented feature — confirm it takes effect on your paperless-ngx
version before relying on it, and check paperless-ngx's docs/release notes
in case a dedicated variable has been added since.

The good news: this worker caches the extracted text under
`OCR_CACHE_DIR/results/` before attempting the update, and reuses it on the
next run instead of re-running OCR. Once the limit is raised, the next poll
picks the cached text back up and retries the update immediately rather
than repeating a potentially multi-hour OCR pass. The cached file is
deleted automatically after a successful update.

