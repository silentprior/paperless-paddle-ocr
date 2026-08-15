"""
Shared pytest setup.

ocr_worker.py imports `paddleocr` and `pymupdf`, and reads several
environment variables, at *module import time*. To unit test the plumbing
logic (tag handling, config parsing, paperless API helpers) without
installing the heavy paddlepaddle/paddleocr/pymupdf binary packages, this
file installs fake stand-in modules and sets the required env vars before
any test module gets to `import ocr_worker`.

pytest always imports a directory's conftest.py before collecting test
files in that directory, so the module-level code below runs first.

If you're adding a test that needs real OCR/PDF behaviour, write an
integration test gated behind the `integration` marker instead of relying
on these stubs (see pyproject.toml for marker registration).
"""

from __future__ import annotations

import os
import sys
import types
from pathlib import Path

# Make the repo root importable (ocr_worker.py lives at the repo root).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# --- Minimum required env vars so Config validates at import time ----------
os.environ.setdefault("PAPERLESS_BASE_URL", "http://paperless.test")
os.environ.setdefault("PAPERLESS_API_TOKEN", "test-token")

# --- Fake heavy dependencies -------------------------------------------
if "paddleocr" not in sys.modules:
    _fake_paddleocr = types.ModuleType("paddleocr")

    class _FakePaddleOCR:
        """Stand-in for paddleocr.PaddleOCR; records init kwargs only."""

        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def predict(self, _image):  # pragma: no cover - not exercised
            return []

    _fake_paddleocr.PaddleOCR = _FakePaddleOCR
    sys.modules["paddleocr"] = _fake_paddleocr

if "pymupdf" not in sys.modules:
    _fake_pymupdf = types.ModuleType("pymupdf")
    _fake_pymupdf.Matrix = lambda *a, **k: None
    _fake_pymupdf.open = lambda *a, **k: None
    sys.modules["pymupdf"] = _fake_pymupdf
