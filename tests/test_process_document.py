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
    monkeypatch.setattr(ocr_worker.Config, "PAPERLESS_PROCESSING_TAG", "paddle_processing")
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


def test_process_document_skips_document_with_processing_tag(monkeypatch):
    monkeypatch.setattr(ocr_worker.Config, "PAPERLESS_PROCESSING_TAG", "paddle_processing")
    monkeypatch.setattr(ocr_worker, "get_or_create_tag_id", lambda _: 11)
    get_mock = MagicMock()
    extract_mock = MagicMock()
    monkeypatch.setattr(ocr_worker.SESSION, "get", get_mock)
    monkeypatch.setattr(ocr_worker, "extract_text", extract_mock)

    ocr_worker.process_document({"id": 123, "title": "In Flight", "tags": [11]})

    get_mock.assert_not_called()
    extract_mock.assert_not_called()


def _tag_id_lookup(name):
    return {"paddle_processing": 11, "paddle_processed": 10, "ocr_done": 20, "ocr_failed": 30}.get(name)


def test_process_document_claims_tracking_tag_before_ocr(monkeypatch):
    """Regression test for GH #23: the tracking tag must be written *before*
    OCR runs (not after it finishes), so a second worker/poll-cycle can't
    pick up the same document while OCR is still in flight."""
    ocr_worker._TAG_ID_CACHE.clear()
    monkeypatch.setattr(ocr_worker.Config, "PAPERLESS_DRY_RUN", False)
    monkeypatch.setattr(ocr_worker.Config, "PAPERLESS_PROCESSING_TAG", "paddle_processing")
    monkeypatch.setattr(ocr_worker.Config, "PAPERLESS_TRACKING_TAG", "paddle_processed")
    monkeypatch.setattr(ocr_worker.Config, "PAPERLESS_OUTPUT_TAG", None)
    monkeypatch.setattr(ocr_worker.Config, "PAPERLESS_ERROR_TAG", None)
    monkeypatch.setattr(ocr_worker, "get_or_create_tag_id", _tag_id_lookup)

    monkeypatch.setattr(
        ocr_worker.SESSION, "get", MagicMock(return_value=_mock_response(content=b"%PDF-fake"))
    )

    call_order = []

    def fake_patch(url, json):
        call_order.append(("patch", json["tags"]))
        return _mock_response()

    def fake_extract_text(*a, **k):
        call_order.append(("extract", None))
        return "hello world"

    monkeypatch.setattr(ocr_worker.SESSION, "patch", fake_patch)
    monkeypatch.setattr(ocr_worker, "extract_text", fake_extract_text)

    doc = {"id": 123, "title": "Test Doc", "tags": []}
    ocr_worker.process_document(doc)

    # The claim PATCH (carrying the tracking tag) must happen before OCR,
    # and OCR must be followed by the final content+tags PATCH.
    assert [step for step, _ in call_order] == ["patch", "extract", "patch"]
    claim_tags = call_order[0][1]
    assert claim_tags == [11]
    assert call_order[2][1] == [10]


def test_process_document_rolls_back_claim_on_ocr_failure(monkeypatch):
    """If OCR fails after the document was claimed, the tracking tag must be
    removed again so the document is retried on a later run instead of
    being silently treated as permanently done."""
    ocr_worker._TAG_ID_CACHE.clear()
    monkeypatch.setattr(ocr_worker.Config, "PAPERLESS_DRY_RUN", False)
    monkeypatch.setattr(ocr_worker.Config, "PAPERLESS_PROCESSING_TAG", "paddle_processing")
    monkeypatch.setattr(ocr_worker.Config, "PAPERLESS_TRACKING_TAG", "paddle_processed")
    monkeypatch.setattr(ocr_worker.Config, "PAPERLESS_OUTPUT_TAG", None)
    monkeypatch.setattr(ocr_worker.Config, "PAPERLESS_ERROR_TAG", "ocr_failed")
    monkeypatch.setattr(ocr_worker, "get_or_create_tag_id", _tag_id_lookup)

    monkeypatch.setattr(
        ocr_worker.SESSION, "get", MagicMock(return_value=_mock_response(content=b"%PDF-fake"))
    )
    patch_mock = MagicMock(return_value=_mock_response())
    monkeypatch.setattr(ocr_worker.SESSION, "patch", patch_mock)

    def failing_extract_text(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(ocr_worker, "extract_text", failing_extract_text)

    doc = {"id": 456, "title": "Bad Doc", "tags": []}
    ocr_worker.process_document(doc)

    # First call = the pre-OCR claim (tracking tag 10). Second call = the
    # post-failure update, which must drop the tracking tag and add the
    # error tag instead of leaving the document marked "done".
    assert patch_mock.call_count == 2
    claim_tags = patch_mock.call_args_list[0].kwargs["json"]["tags"]
    failure_tags = patch_mock.call_args_list[1].kwargs["json"]["tags"]
    assert claim_tags == [11]
    assert 11 not in failure_tags
    assert 10 not in failure_tags
    assert 30 in failure_tags


def test_process_document_aborts_before_ocr_if_claim_fails(monkeypatch):
    """If the pre-OCR claim PATCH itself fails, we must not proceed to run
    OCR at all -- otherwise we've lost the whole point of claiming first."""
    ocr_worker._TAG_ID_CACHE.clear()
    monkeypatch.setattr(ocr_worker.Config, "PAPERLESS_DRY_RUN", False)
    monkeypatch.setattr(ocr_worker.Config, "PAPERLESS_PROCESSING_TAG", "paddle_processing")
    monkeypatch.setattr(ocr_worker.Config, "PAPERLESS_TRACKING_TAG", "paddle_processed")
    monkeypatch.setattr(ocr_worker, "get_or_create_tag_id", _tag_id_lookup)

    monkeypatch.setattr(
        ocr_worker.SESSION, "get", MagicMock(return_value=_mock_response(content=b"%PDF-fake"))
    )

    import requests

    monkeypatch.setattr(
        ocr_worker.SESSION, "patch", MagicMock(side_effect=requests.RequestException("network down"))
    )
    extract_mock = MagicMock()
    monkeypatch.setattr(ocr_worker, "extract_text", extract_mock)

    doc = {"id": 789, "title": "Unclaimable", "tags": []}
    ocr_worker.process_document(doc)

    extract_mock.assert_not_called()
