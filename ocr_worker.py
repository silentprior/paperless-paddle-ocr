#!/usr/bin/env python3
"""
Paperless-ngx PaddleOCR Worker
===============================
Polls a paperless-ngx instance for documents tagged for OCR, runs PaddleOCR
(PP-OCRv6) against the PDF/image content, and writes the extracted text back
to the document via the paperless-ngx API.

PDF pages are rendered with PyMuPDF (no poppler / system OCR binaries
needed). Text is extracted with the current PaddleOCR `predict()` API
(the old `ocr.ocr()` API used in earlier PaddleOCR releases is deprecated
and was removed from this script).

All behaviour is controlled via environment variables so the container can
be configured entirely from docker-compose.yml — see README/.env.example
or the table below.

Paperless connection
---------------------
PAPERLESS_BASE_URL        Base URL of the paperless-ngx instance (required)
PAPERLESS_API_TOKEN       API token (required)
PAPERLESS_VERIFY_SSL      Verify TLS certs ("true"/"false", default: true)

Tagging / workflow
-------------------
PAPERLESS_INPUT_TAG       Only process documents with this tag (default: all)
PAPERLESS_OUTPUT_TAG      Tag to apply after successful OCR (optional)
PAPERLESS_ERROR_TAG       Tag to apply if OCR fails (optional)
PAPERLESS_PROCESSING_TAG  Temporary tag used while a document is being OCR'd
                           (default: paddle_processing)
PAPERLESS_PROCESSED_TAG   Tag used to mark docs as "already processed"
                           (default: paddle_processed)
PAPERLESS_REPROCESS       Re-OCR documents that already have the tracking
                           tag ("true"/"false", default: false)
PAPERLESS_DRY_RUN         Log what would happen but don't write anything
                           ("true"/"false", default: false)

Run behaviour
--------------
PAPERLESS_RUN_MODE          "daemon" (loop forever) or "oneshot" (run once
                             and exit). Default: daemon
PAPERLESS_INTERVAL_SECONDS  Seconds between polling runs in daemon mode
                             (default: 3600)
PAPERLESS_DELAY_SECONDS     Seconds to sleep between processing documents,
                             to avoid hammering the API (default: 1)
PAPERLESS_STARTUP_TIMEOUT   Seconds to wait for the paperless API to become
                             reachable before giving up (default: 60)
PAPERLESS_HEALTH_PORT       Port for the internal /health endpoint used by
                             the Docker HEALTHCHECK (default: 8080)

OCR engine (PaddleOCR PP-OCRv6)
---------------------------------
OCR_LANG            Language code, e.g. en, ch, fr, de, ja (default: en)
OCR_DPI             PDF render DPI — higher = better quality, slower
                     (default: 200)
OCR_TIER            Model tier: tiny | small | medium (default: small)
OCR_ENGINE          Inference backend: paddle | onnxruntime | openvino
                     (default: paddle). "openvino" is significantly faster
                     on Intel CPUs but requires the openvino package.
OCR_ENABLE_MKLDNN   Enable the oneDNN CPU backend ("true"/"false",
                     default: false — oneDNN can crash on some CPU/model
                     combinations)
OCR_THREADS         CPU threads PaddleOCR should use (default: 4)
OCR_CACHE_DIR       Where PaddleOCR/PaddleX model weights are downloaded to
                     and cached (default: /app/.paddle_cache). Mount this
                     as a volume so models survive container restarts.

Logging
--------
LOG_LEVEL           Python logging level (default: INFO)
"""

from __future__ import annotations

import fcntl
import io
import logging
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import numpy as np
import requests
from PIL import Image

# ---------------------------------------------------------------------------
# Configuration (all via environment variables)
# ---------------------------------------------------------------------------


def _env_bool(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _processed_tag_name() -> str:
    return os.environ.get("PAPERLESS_PROCESSED_TAG") or os.environ.get(
        "PAPERLESS_TRACKING_TAG", "paddle_processed"
    )


class Config:
    # Paperless connection
    PAPERLESS_BASE_URL = os.environ.get("PAPERLESS_BASE_URL", "").rstrip("/")
    PAPERLESS_API_TOKEN = os.environ.get("PAPERLESS_API_TOKEN", "")
    PAPERLESS_VERIFY_SSL = _env_bool("PAPERLESS_VERIFY_SSL", True)

    # Tagging / workflow
    PAPERLESS_INPUT_TAG = os.environ.get("PAPERLESS_INPUT_TAG", "") or None
    PAPERLESS_OUTPUT_TAG = os.environ.get("PAPERLESS_OUTPUT_TAG", "") or None
    PAPERLESS_ERROR_TAG = os.environ.get("PAPERLESS_ERROR_TAG", "") or None
    PAPERLESS_PROCESSING_TAG = os.environ.get("PAPERLESS_PROCESSING_TAG", "paddle_processing")
    PAPERLESS_PROCESSED_TAG = _processed_tag_name()
    PAPERLESS_REPROCESS = _env_bool("PAPERLESS_REPROCESS", False)
    PAPERLESS_DRY_RUN = _env_bool("PAPERLESS_DRY_RUN", False)

    # Run behaviour
    PAPERLESS_RUN_MODE = os.environ.get("PAPERLESS_RUN_MODE", "daemon").lower()
    PAPERLESS_INTERVAL_SECONDS = int(os.environ.get("PAPERLESS_INTERVAL_SECONDS", "3600"))
    PAPERLESS_DELAY_SECONDS = float(os.environ.get("PAPERLESS_DELAY_SECONDS", "1.0"))
    PAPERLESS_STARTUP_TIMEOUT = int(os.environ.get("PAPERLESS_STARTUP_TIMEOUT", "60"))
    PAPERLESS_HEALTH_PORT = int(os.environ.get("PAPERLESS_HEALTH_PORT", "8080"))

    # OCR engine
    OCR_LANG = os.environ.get("OCR_LANG", "en")
    OCR_DPI = int(os.environ.get("OCR_DPI", "200"))
    OCR_TIER = os.environ.get("OCR_TIER", "small").lower()
    OCR_ENGINE = os.environ.get("OCR_ENGINE", "paddle").lower()
    OCR_ENABLE_MKLDNN = _env_bool("OCR_ENABLE_MKLDNN", False)
    OCR_THREADS = int(os.environ.get("OCR_THREADS", "4"))
    OCR_CACHE_DIR = Path(os.environ.get("OCR_CACHE_DIR", "/app/.paddle_cache"))

    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()


# Point PaddleOCR/PaddleX/HF model caches at a writable, persistent dir
# BEFORE paddleocr is imported anywhere below.
Config.OCR_CACHE_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(Config.OCR_CACHE_DIR / "paddlex"))
os.environ.setdefault("HF_HOME", str(Config.OCR_CACHE_DIR / "huggingface"))
os.environ.setdefault("MODELSCOPE_CACHE", str(Config.OCR_CACHE_DIR / "modelscope"))
# Skip the network connectivity probe PaddleX does on every startup.
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

import pymupdf  # noqa: E402
from paddleocr import PaddleOCR  # noqa: E402  (import order: after cache env vars are set)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("paperless-paddle-ocr")

OCR_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/tiff",
    "image/bmp",
    "image/webp",
}

SESSION = requests.Session()
SESSION.verify = Config.PAPERLESS_VERIFY_SSL
SESSION.headers.update(
    {
        "Authorization": f"Token {Config.PAPERLESS_API_TOKEN}",
        "Content-Type": "application/json",
    }
)

_TAG_ID_CACHE: dict[str, int] = {}


# ---------------------------------------------------------------------------
# PaddleOCR engine (lazy singleton)
# ---------------------------------------------------------------------------
_OCR_ENGINE: PaddleOCR | None = None


def get_ocr_engine() -> PaddleOCR:
    """Build (once) and return the PP-OCRv6 engine configured from Config."""
    global _OCR_ENGINE
    if _OCR_ENGINE is None:
        logger.info(
            "Initialising PaddleOCR PP-OCRv6 (lang=%s, tier=%s, engine=%s, threads=%s)",
            Config.OCR_LANG,
            Config.OCR_TIER,
            Config.OCR_ENGINE,
            Config.OCR_THREADS,
        )
        kwargs = dict(
            lang=Config.OCR_LANG,
            use_textline_orientation=True,
            text_detection_model_name=f"PP-OCRv6_{Config.OCR_TIER}_det",
            text_recognition_model_name=f"PP-OCRv6_{Config.OCR_TIER}_rec",
            # oneDNN can hit unimplemented op conversions on some CPU/model
            # combinations, so it's opt-in rather than the default.
            enable_mkldnn=Config.OCR_ENABLE_MKLDNN,
            cpu_threads=Config.OCR_THREADS,
        )
        # Only pass `engine` for the accelerated backends; the default
        # "paddle" backend doesn't need (and may not accept) the kwarg.
        if Config.OCR_ENGINE != "paddle":
            kwargs["engine"] = Config.OCR_ENGINE
        _OCR_ENGINE = PaddleOCR(**kwargs)
    return _OCR_ENGINE


def ocr_image(ocr: PaddleOCR, image: Image.Image) -> tuple[str, float | None]:
    """Run OCR on a single PIL image. Returns (text, avg_confidence)."""
    results = ocr.predict(np.array(image))

    lines: list[str] = []
    scores: list[float] = []
    for result in results:
        for text in result.get("rec_texts", []):
            text = text.strip()
            if text:
                lines.append(text)
        scores.extend(result.get("rec_scores", []) or [])

    avg_conf = sum(scores) / len(scores) if scores else None
    return "\n".join(lines), avg_conf


def iter_pdf_page_images(pdf_bytes: bytes, dpi: int):
    """Yield (page_number, PIL.Image) one page at a time to keep memory low."""
    zoom = dpi / 72
    mat = pymupdf.Matrix(zoom, zoom)
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        for i in range(doc.page_count):
            pix = doc[i].get_pixmap(matrix=mat, alpha=False)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            yield i + 1, img
    finally:
        doc.close()


def extract_text(file_content: bytes, mime_type: str) -> str:
    """Extract text from a PDF or image using PaddleOCR PP-OCRv6."""
    ocr = get_ocr_engine()
    parts: list[str] = []

    if mime_type == "application/pdf":
        for page_num, image in iter_pdf_page_images(file_content, Config.OCR_DPI):
            try:
                text, avg_conf = ocr_image(ocr, image)
                conf_str = f", avg conf {avg_conf:.2f}" if avg_conf is not None else ""
                logger.debug("Page %d: %d word(s)%s", page_num, len(text.split()), conf_str)
                parts.append(text)
            finally:
                image.close()
    else:
        image = Image.open(io.BytesIO(file_content))
        try:
            text, _ = ocr_image(ocr, image)
            parts.append(text)
        finally:
            image.close()

    return "\n\n".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Paperless-ngx API helpers
# ---------------------------------------------------------------------------
def get_tag_ids_from_doc(doc: dict) -> list[int]:
    ids = []
    for t in doc.get("tags", []):
        if isinstance(t, dict) and "id" in t:
            ids.append(t["id"])
        elif isinstance(t, int):
            ids.append(t)
        elif isinstance(t, str) and t.isdigit():
            ids.append(int(t))
    return ids


def get_or_create_tag_id(tag_name: str | None) -> int | None:
    if not tag_name:
        return None
    if tag_name in _TAG_ID_CACHE:
        return _TAG_ID_CACHE[tag_name]

    resp = SESSION.get(f"{Config.PAPERLESS_BASE_URL}/api/tags/", params={"name__iexact": tag_name})
    resp.raise_for_status()
    data = resp.json()
    if data["count"] > 0:
        tag_id = data["results"][0]["id"]
    else:
        create_resp = SESSION.post(f"{Config.PAPERLESS_BASE_URL}/api/tags/", json={"name": tag_name})
        create_resp.raise_for_status()
        tag_id = create_resp.json()["id"]
        logger.info("Created new tag: %s (ID: %s)", tag_name, tag_id)

    _TAG_ID_CACHE[tag_name] = tag_id
    return tag_id


def wait_for_paperless() -> None:
    logger.info("Waiting for Paperless API at %s ...", Config.PAPERLESS_BASE_URL)
    deadline = time.time() + Config.PAPERLESS_STARTUP_TIMEOUT
    while time.time() < deadline:
        try:
            resp = SESSION.get(f"{Config.PAPERLESS_BASE_URL}/api/", timeout=5)
            if resp.status_code == 200:
                logger.info("Paperless API is ready.")
                return
        except requests.RequestException:
            pass
        time.sleep(2)
    raise RuntimeError(f"Paperless API did not become ready within {Config.PAPERLESS_STARTUP_TIMEOUT}s")


def fetch_candidate_documents() -> list[dict]:
    params: dict = {"page_size": 100, "fields": "id,title,tags"}

    input_tag_id = None
    if Config.PAPERLESS_INPUT_TAG:
        input_tag_id = get_or_create_tag_id(Config.PAPERLESS_INPUT_TAG)
        if input_tag_id:
            params["tags__id"] = input_tag_id
        else:
            logger.warning(
                "Input tag '%s' could not be resolved – no documents will match.", Config.PAPERLESS_INPUT_TAG
            )

    processing_tag_id = get_or_create_tag_id(Config.PAPERLESS_PROCESSING_TAG)
    excluded_tag_ids = [processing_tag_id] if processing_tag_id else []
    if not Config.PAPERLESS_REPROCESS:
        tracking_tag_id = get_or_create_tag_id(Config.PAPERLESS_PROCESSED_TAG)
        if tracking_tag_id:
            excluded_tag_ids.insert(0, tracking_tag_id)
    if excluded_tag_ids:
        params["tags__id__none"] = ",".join(map(str, excluded_tag_ids))

    docs: list[dict] = []
    page = 1
    while True:
        params["page"] = page
        resp = SESSION.get(f"{Config.PAPERLESS_BASE_URL}/api/documents/", params=params)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results")
        if not isinstance(results, list):
            logger.warning("Unexpected API response – 'results' is not a list")
            break
        docs.extend(results)
        if not data.get("next"):
            break
        page += 1

    # Paperless' tag filter can be permissive depending on version; double
    # check membership explicitly when an input tag was requested.
    if input_tag_id:
        docs = [d for d in docs if input_tag_id in get_tag_ids_from_doc(d)]

    return docs


def apply_tag(doc_id: int, current_tags: list[int], tag_id: int | None) -> list[int]:
    if tag_id and tag_id not in current_tags:
        current_tags = current_tags + [tag_id]
    return current_tags


def remove_processing_tag(doc_id: int, current_tags: list[int], processing_tag_id: int | None) -> None:
    if not processing_tag_id or processing_tag_id not in current_tags:
        return

    try:
        cleanup_resp = SESSION.patch(
            f"{Config.PAPERLESS_BASE_URL}/api/documents/{doc_id}/",
            json={"tags": [tag_id for tag_id in current_tags if tag_id != processing_tag_id]},
        )
        cleanup_resp.raise_for_status()
        logger.info("[DOC:%s] Removed processing tag after failed update", doc_id)
    except requests.RequestException as exc:
        logger.error("[DOC:%s] Failed to remove processing tag after failed update: %s", doc_id, exc)


def process_document(doc: dict) -> None:
    doc_id = doc.get("id")
    if not doc_id:
        logger.error("Document missing 'id' field: %s", doc)
        return

    title = doc.get("title", "untitled")
    processing_tag_id = get_or_create_tag_id(Config.PAPERLESS_PROCESSING_TAG)
    if processing_tag_id and processing_tag_id in get_tag_ids_from_doc(doc):
        logger.info("[DOC:%s] Skipping document already being processed: %s", doc_id, title)
        return

    logger.info("[DOC:%s] Starting processing: %s", doc_id, title)

    download_url = f"{Config.PAPERLESS_BASE_URL}/api/documents/{doc_id}/download/"
    try:
        resp = SESSION.get(download_url)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.error("[DOC:%s] Download failed: %s", doc_id, exc)
        return

    file_content = resp.content
    mime_type = resp.headers.get("Content-Type", "").split(";")[0].strip()

    if mime_type not in OCR_MIME_TYPES:
        logger.info("[DOC:%s] Skipping unsupported MIME type: %s", doc_id, mime_type)
        return

    current_tags = get_tag_ids_from_doc(doc)

    # Claim the document with a temporary processing tag *before* running OCR, not after. OCR on a large
    # multi-hundred-page PDF can take a long time. Claiming it first provides
    # defense-in-depth against concurrent workers or poll cycles (see GitHub
    # issue #23, whose reported duplicate execution was not conclusively
    # reproduced).
    # Writing the tracking tag immediately shrinks that window down to a
    # single PATCH call. If OCR then fails, the claim is rolled back below
    # so the document is still retried on a later run.
    tracking_tag_id = get_or_create_tag_id(Config.PAPERLESS_PROCESSED_TAG)
    claimed = False
    if processing_tag_id and not Config.PAPERLESS_DRY_RUN:
        claim_tags = apply_tag(doc_id, current_tags, processing_tag_id)
        if claim_tags != current_tags:
            try:
                claim_resp = SESSION.patch(
                    f"{Config.PAPERLESS_BASE_URL}/api/documents/{doc_id}/",
                    json={"tags": claim_tags},
                )
                claim_resp.raise_for_status()
                current_tags = claim_tags
                claimed = True
            except requests.RequestException as exc:
                logger.error(
                    "[DOC:%s] Failed to claim document before OCR, skipping this run to avoid "
                    "duplicate processing: %s",
                    doc_id,
                    exc,
                )
                return

    try:
        extracted_text = extract_text(file_content, mime_type)
    except Exception as exc:  # noqa: BLE001 - one bad doc shouldn't kill the run
        logger.error("[DOC:%s] OCR failed: %s", doc_id, exc, exc_info=True)
        if not Config.PAPERLESS_DRY_RUN:
            try:
                updated_tags = set(current_tags)
                if claimed and processing_tag_id:
                    # Undo the provisional claim so the document is
                    # retried on a future run instead of being treated as
                    # permanently "done".
                    updated_tags.discard(processing_tag_id)
                if Config.PAPERLESS_ERROR_TAG:
                    error_tag_id = get_or_create_tag_id(Config.PAPERLESS_ERROR_TAG)
                    if error_tag_id:
                        updated_tags.add(error_tag_id)
                if updated_tags != set(current_tags):
                    cleanup_resp = SESSION.patch(
                        f"{Config.PAPERLESS_BASE_URL}/api/documents/{doc_id}/",
                        json={"tags": sorted(updated_tags)},
                    )
                    cleanup_resp.raise_for_status()
                    logger.info("[DOC:%s] Updated tags after failure -> %s", doc_id, sorted(updated_tags))
            except Exception as tag_exc:  # noqa: BLE001
                logger.error("[DOC:%s] Failed to update tags after failure: %s", doc_id, tag_exc)
        return

    if not extracted_text:
        logger.warning("[DOC:%s] No text extracted (empty result)", doc_id)

    output_tag_id = get_or_create_tag_id(Config.PAPERLESS_OUTPUT_TAG)
    error_tag_id = get_or_create_tag_id(Config.PAPERLESS_ERROR_TAG)

    final_tags = set(current_tags)
    final_tags.discard(error_tag_id) if error_tag_id else None
    if processing_tag_id:
        final_tags.discard(processing_tag_id)
    if tracking_tag_id:
        final_tags.add(tracking_tag_id)
    if output_tag_id:
        final_tags.add(output_tag_id)

    if Config.PAPERLESS_DRY_RUN:
        logger.info(
            "[DOC:%s] DRY RUN: would update content (%d chars) and tags -> %s",
            doc_id,
            len(extracted_text),
            sorted(final_tags),
        )
        return

    try:
        patch_resp = SESSION.patch(
            f"{Config.PAPERLESS_BASE_URL}/api/documents/{doc_id}/",
            json={"content": extracted_text, "tags": sorted(final_tags)},
        )
        patch_resp.raise_for_status()
        logger.info("[DOC:%s] Updated (chars=%d, tags=%s)", doc_id, len(extracted_text), sorted(final_tags))
    except requests.RequestException as exc:
        logger.error("[DOC:%s] Update failed: %s", doc_id, exc)
        remove_processing_tag(doc_id, current_tags, processing_tag_id)


# ---------------------------------------------------------------------------
# Healthcheck HTTP server
# ---------------------------------------------------------------------------
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - required by BaseHTTPRequestHandler
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):  # noqa: A002 - silence per-request logs
        pass


def start_health_server() -> None:
    try:
        server = DualStackHTTPServer(("::", Config.PAPERLESS_HEALTH_PORT), HealthHandler)
    except OSError:
        # IPv6 unavailable in this environment; fall back to IPv4-only.
        server = HTTPServer(("0.0.0.0", Config.PAPERLESS_HEALTH_PORT), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Healthcheck server listening on port %d", Config.PAPERLESS_HEALTH_PORT)


# ---------------------------------------------------------------------------
# Singleton guard
# ---------------------------------------------------------------------------
# Fixed path (not user-configurable): this is a defensive, in-container
# guard against *this* container ending up with two worker loops running
# at once -- e.g. a process supervisor or restart policy starting a
# replacement process before the previous one has fully exited. It is not
# meant to coordinate across multiple containers/hosts.
_SINGLETON_LOCK_PATH = "/tmp/paperless-paddle-ocr.lock"
_singleton_lock_fh = None  # kept open for the lifetime of the process


def acquire_singleton_lock() -> None:
    """Make sure only one worker loop runs inside this container.

    Uses a non-blocking flock() on a fixed path. If a second instance of
    ocr_worker.py starts in the same container while the first is still
    running, it will fail to acquire the lock here and exit immediately
    instead of silently running a second, identical poll loop alongside
    the first. This is preventive concurrency hardening for GitHub issue #23;
    the reported duplicate execution was not conclusively reproduced.
    """
    global _singleton_lock_fh
    _singleton_lock_fh = open(_SINGLETON_LOCK_PATH, "a+")  # noqa: SIM115 - held for process lifetime
    try:
        fcntl.flock(_singleton_lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        logger.critical(
            "Another instance of the OCR worker already appears to be running "
            "in this container (lock held on %s). Refusing to start a second "
            "worker loop.",
            _SINGLETON_LOCK_PATH,
        )
        sys.exit(1)
    _singleton_lock_fh.seek(0)
    _singleton_lock_fh.truncate()
    _singleton_lock_fh.write(str(os.getpid()))
    _singleton_lock_fh.flush()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    if not Config.PAPERLESS_BASE_URL:
        logger.error("PAPERLESS_BASE_URL is required.")
        sys.exit(1)
    if not Config.PAPERLESS_API_TOKEN:
        logger.error("PAPERLESS_API_TOKEN is required.")
        sys.exit(1)

    logger.info("=== Configuration ===")
    logger.info("PAPERLESS_BASE_URL     : %s", Config.PAPERLESS_BASE_URL)
    logger.info("PAPERLESS_INPUT_TAG    : %s", Config.PAPERLESS_INPUT_TAG or "(none - process all)")
    logger.info("PAPERLESS_OUTPUT_TAG   : %s", Config.PAPERLESS_OUTPUT_TAG or "(none)")
    logger.info("PAPERLESS_PROCESSING_TAG: %s", Config.PAPERLESS_PROCESSING_TAG)
    logger.info("PAPERLESS_PROCESSED_TAG : %s", Config.PAPERLESS_PROCESSED_TAG)
    logger.info("PAPERLESS_REPROCESS    : %s", Config.PAPERLESS_REPROCESS)
    logger.info("PAPERLESS_DRY_RUN      : %s", Config.PAPERLESS_DRY_RUN)
    logger.info("PAPERLESS_RUN_MODE     : %s", Config.PAPERLESS_RUN_MODE)
    logger.info("OCR_LANG / TIER / ENGN : %s / %s / %s", Config.OCR_LANG, Config.OCR_TIER, Config.OCR_ENGINE)
    logger.info("OCR_DPI / THREADS      : %s / %s", Config.OCR_DPI, Config.OCR_THREADS)
    logger.info("======================")

    acquire_singleton_lock()
    wait_for_paperless()
    start_health_server()

    while True:
        try:
            logger.info("=== Starting OCR run ===")
            docs = fetch_candidate_documents()
            logger.info("Found %d document(s) to process", len(docs))

            for doc in docs:
                process_document(doc)
                time.sleep(Config.PAPERLESS_DELAY_SECONDS)

            logger.info("=== Run completed ===")
        except Exception as exc:  # noqa: BLE001 - keep the daemon alive
            logger.error("Run failed: %s", exc, exc_info=True)

        if Config.PAPERLESS_RUN_MODE == "oneshot":
            logger.info("Oneshot mode - exiting.")
            break

        logger.debug("Sleeping for %ds ...", Config.PAPERLESS_INTERVAL_SECONDS)
        time.sleep(Config.PAPERLESS_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
