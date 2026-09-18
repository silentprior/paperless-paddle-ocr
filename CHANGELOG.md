# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Extracted OCR text is now cached to `OCR_CACHE_DIR/results/` before the
  paperless update, and reused on the next run instead of re-running OCR
  if that update fails. A large document no longer loses hours of OCR
  work to a single failed PATCH; the cache file is removed automatically
  after a successful update.
  ([#25](https://github.com/silentprior/paperless-paddle-ocr/issues/25))

### Changed
- Update failure logs now include the outgoing JSON payload size and a
  pointer to the Django `DATA_UPLOAD_MAX_MEMORY_SIZE` limit when a large
  document's update is rejected with a 400/413, instead of only logging
  the (often unhelpful) response body.
  ([#25](https://github.com/silentprior/paperless-paddle-ocr/issues/25))

### Fixed
- Use PaddleX 3.x's `PADDLE_PDX_CACHE_HOME` environment variable so model
  downloads stay under `OCR_CACHE_DIR` and persist across one-shot runs.
  ([#27](https://github.com/silentprior/paperless-paddle-ocr/issues/27))

## [1.0.1] - 2026-09-17

### Fixed
- **Concurrency hardening** for worker processing. Issue #23's reported
  duplicate execution was not conclusively reproduced, but a separate
  `PAPERLESS_PROCESSING_TAG` is now written *before* OCR runs while the
  completed tag remains the permanent success marker. A non-blocking
  `flock`-based singleton guard also makes a second worker process in the
  same container fail fast. If OCR then fails, the provisional processing
  claim is rolled back so the document is retried on a later run. If the
  final Paperless update fails, the worker also makes a best-effort attempt
  to remove the processing tag.
  ([#23](https://github.com/silentprior/paperless-paddle-ocr/issues/23))

## [1.0.0] - 2026-08-12

### Added
- Initial public release.
- PaddleOCR PP-OCRv6 integration via the current `predict()` API.
- PDF rendering via PyMuPDF (no poppler/system OCR binaries required).
- Full environment-variable configuration surface (`OCR_*`, `PAPERLESS_*`).
- Non-root Docker image with `HEALTHCHECK`, multi-arch build
  (`linux/amd64`, `linux/arm64`).
- Daemon and one-shot run modes, dry-run mode.
- Unit test suite with heavy OCR/PDF dependencies stubbed out.
- CI (lint, type check, tests) and release (multi-arch Docker Hub publish)
  GitHub Actions workflows.

### Changed
- Replaced the deprecated `PaddleOCR.ocr()` call with `PaddleOCR.predict()`.
- Replaced `pdf2image`/poppler-based PDF rendering with PyMuPDF.

[Unreleased]: https://github.com/silentprior/paperless-paddle-ocr/compare/v1.0.1...HEAD
[1.0.1]: https://github.com/silentprior/paperless-paddle-ocr/releases/tag/v1.0.1
[1.0.0]: https://github.com/silentprior/paperless-paddle-ocr/releases/tag/v1.0.0