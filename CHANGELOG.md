# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

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

[Unreleased]: https://github.com/silentprior/paperless-paddle-ocr/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/silentprior/paperless-paddle-ocr/releases/tag/v1.0.0
