# Architecture

## Overview

`ocr_worker.py` is a single-process, single-file worker:

```
+-----------------+      poll (tagged docs)      +------------------+
| paperless-ngx    | <---------------------------- | ocr_worker.py    |
| (REST API)       | ----------------------------> | (this container) |
+-----------------+   download doc / PATCH content +------------------+
                                                            |
                                                            v
                                                  PyMuPDF renders PDF
                                                  pages -> PIL images
                                                            |
                                                            v
                                                  PaddleOCR PP-OCRv6
                                                  predict() per page
                                                            |
                                                            v
                                                  joined text -> PATCH
                                                  back to paperless-ngx
```

There's a small built-in HTTP server (`HealthHandler`) exposing `/health` on
`PAPERLESS_HEALTH_PORT`, used by the Docker `HEALTHCHECK`. It runs on a
background thread so it stays responsive even mid-OCR-run.

## Why PyMuPDF instead of `pdf2image`/poppler

The original prototype used `pdf2image`, which shells out to `poppler-utils`
(`pdftoppm`). That means an extra system package, an extra subprocess per
page, and an extra failure mode ("poppler not found"/version mismatches).
PyMuPDF is a self-contained Python wheel with no external binary, and lets
pages be rendered and processed one at a time (`iter_pdf_page_images`)
without loading the whole PDF's rendered pages into memory at once.

## Why PP-OCRv6's `predict()` instead of `ocr.ocr()`

PaddleOCR's older `.ocr()` method is deprecated in favor of `.predict()`,
which returns a list of result dicts per image with `rec_texts` /
`rec_scores` keys — used directly in `ocr_image()`.

## Configuration philosophy

Everything is an environment variable (see `docs/CONFIGURATION.md`), read
once into the `Config` class at import time. There's no config file and no
CLI flags — the container's environment is the single source of truth,
which keeps `docker-compose.yml` the one place you look to understand how a
deployment is set up.

## Testing without the OCR runtime

`paddlepaddle`/`paddleocr`/`pymupdf` are large binary dependencies. Unit
tests stub them out (see `tests/conftest.py`) so CI can validate the
plumbing (tag handling, pagination, dry-run behavior, config parsing)
without installing gigabytes of ML runtime. Anything that needs real OCR
behavior belongs in a manual/integration test against a real paperless-ngx
instance, not the default `pytest` run.

## Extending

- **New OCR languages**: set `OCR_LANG` — PaddleOCR downloads the
  corresponding model on first use into `OCR_CACHE_DIR`
- **New backends**: `OCR_ENGINE` is passed straight through to
  `PaddleOCR(engine=...)`; anything PaddleOCR itself supports should work
- **Multiple paperless instances / configs**: run multiple containers with
  different env vars and (recommended) different `OCR_CACHE_DIR` volumes
