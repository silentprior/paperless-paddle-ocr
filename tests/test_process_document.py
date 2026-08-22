from unittest.mock import MagicMock

import ocr_worker


def _mock_response(content=b"", headers=None, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = content
    resp.headers = headers or {"Content-Type": "application/pdf"}
    resp.raise_for_status.return_value = None
    return resp


def test_process_document_dry_run_does_not_patch(monkeypatch):
    ocr_worker._TAG_ID_CACHE.clear()
    monkeypatch.setattr(ocr_worker.Config, "PAPERLESS_DRY_RUN", True)
    monkeypatch.setattr(ocr_worker.Config, "PAPERLESS_TRACKING_TAG", "paddle_processed")
    monkeypatch.setattr(ocr_worker.Config, "PAPERLESS_OUTPUT_TAG", None)
    monkeypatch.setattr(ocr_worker.Config, "PAPERLESS_ERROR_TAG", None)

    monkeypatch.setattr(
        ocr_worker.SESSION, "get", MagicMock(return_value=_mock_response(content=b"%PDF-fake"))
    )
    patch_mock = MagicMock()
    monkeypatch.setattr(ocr_worker.SESSION, "patch", patch_mock)
    monkeypatch.setattr(ocr_worker.SESSION, "post", MagicMock(return_value=_mock_response({"id": 1})))

    monkeypatch.setattr(ocr_worker, "extract_text", lambda *a, **k: "hello world")
    monkeypatch.setattr(ocr_worker, "get_or_create_tag_id", lambda name: 1 if name else None)

    doc = {"id": 123, "title": "Test Doc", "tags": []}
    ocr_worker.process_document(doc)

    patch_mock.assert_not_called()


def test_process_document_skips_unsupported_mime(monkeypatch):
    monkeypatch.setattr(
        ocr_worker.SESSION,
        "get",
        MagicMock(return_value=_mock_response(headers={"Content-Type": "text/plain"})),
    )
    extract_mock = MagicMock()
    monkeypatch.setattr(ocr_worker, "extract_text", extract_mock)

    doc = {"id": 456, "title": "Unsupported", "tags": []}
    ocr_worker.process_document(doc)

    extract_mock.assert_not_called()


def test_process_document_missing_id_is_noop(monkeypatch):
    get_mock = MagicMock()
    monkeypatch.setattr(ocr_worker.SESSION, "get", get_mock)
    ocr_worker.process_document({"title": "No ID"})
    get_mock.assert_not_called()
