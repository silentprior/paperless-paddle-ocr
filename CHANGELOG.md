# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.0.1] - 2026-09-16

### Fixed
- **Documents could be OCR'd twice** if two worker loops ever ended up
  running in the same container (e.g. a supervisor/restart policy starting
  a replacement process before the previous one fully exited). A separate
  `PAPERLESS_PROCESSING_TAG` is now written *before* OCR runs, while the
  existing `PAPERLESS_TRACKING_TAG` remains the permanent success marker.
  This closes the multi-hour window (large PDFs) during which a second worker
  could pick up the same untracked document. Added a non-blocking
  `flock`-based singleton guard so a second worker process in the same
  container now fails fast at startup instead of silently running a duplicate
  poll loop. If OCR then fails, the provisional processing claim is rolled
  back so the document is still retried on a later run.
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