from unittest.mock import MagicMock

import ocr_worker


def _mock_response(json_data=None, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.raise_for_status.return_value = None
    return resp


def test_get_or_create_tag_id_returns_existing(monkeypatch):
    ocr_worker._TAG_ID_CACHE.clear()
    monkeypatch.setattr(
        ocr_worker.SESSION,
        "get",
        MagicMock(return_value=_mock_response({"count": 1, "results": [{"id": 42}]})),
    )
    tag_id = ocr_worker.get_or_create_tag_id("to_ocr")
    assert tag_id == 42


def test_get_or_create_tag_id_creates_when_missing(monkeypatch):
    ocr_worker._TAG_ID_CACHE.clear()
    monkeypatch.setattr(
        ocr_worker.SESSION,
        "get",
        MagicMock(return_value=_mock_response({"count": 0, "results": []})),
    )
    monkeypatch.setattr(
        ocr_worker.SESSION,
        "post",
        MagicMock(return_value=_mock_response({"id": 99})),
    )
    tag_id = ocr_worker.get_or_create_tag_id("brand_new_tag")
    assert tag_id == 99


def test_get_or_create_tag_id_uses_cache(monkeypatch):
    ocr_worker._TAG_ID_CACHE.clear()
    ocr_worker._TAG_ID_CACHE["cached_tag"] = 7
    get_mock = MagicMock()
    monkeypatch.setattr(ocr_worker.SESSION, "get", get_mock)
    tag_id = ocr_worker.get_or_create_tag_id("cached_tag")
    assert tag_id == 7
    get_mock.assert_not_called()


def test_get_or_create_tag_id_none_name_returns_none():
    assert ocr_worker.get_or_create_tag_id(None) is None
    assert ocr_worker.get_or_create_tag_id("") is None


def test_fetch_candidate_documents_paginates(monkeypatch):
    ocr_worker._TAG_ID_CACHE.clear()
    monkeypatch.setattr(ocr_worker.Config, "PAPERLESS_INPUT_TAG", None)
    monkeypatch.setattr(ocr_worker.Config, "PAPERLESS_REPROCESS", True)

    page1 = _mock_response({"results": [{"id": 1}], "next": "page2"})
    page2 = _mock_response({"results": [{"id": 2}], "next": None})
    get_mock = MagicMock(side_effect=[page1, page2])
    monkeypatch.setattr(ocr_worker.SESSION, "get", get_mock)
    monkeypatch.setattr(ocr_worker, "get_or_create_tag_id", lambda _: None)

    docs = ocr_worker.fetch_candidate_documents()
    assert [d["id"] for d in docs] == [1, 2]
    assert get_mock.call_args.kwargs["params"]["fields"] == "id,title,tags"


def test_fetch_candidate_documents_excludes_processed_and_processing_tags(monkeypatch):
    ocr_worker._TAG_ID_CACHE.clear()
    monkeypatch.setattr(ocr_worker.Config, "PAPERLESS_INPUT_TAG", None)
    monkeypatch.setattr(ocr_worker.Config, "PAPERLESS_REPROCESS", False)
    monkeypatch.setattr(ocr_worker.Config, "PAPERLESS_PROCESSED_TAG", "paddle_ocr")
    monkeypatch.setattr(ocr_worker.Config, "PAPERLESS_PROCESSING_TAG", "paddle_processing")
    monkeypatch.setattr(
        ocr_worker,
        "get_or_create_tag_id",
        lambda name: {"paddle_ocr": 10, "paddle_processing": 20}[name],
    )
    get_mock = MagicMock(return_value=_mock_response({"results": [], "next": None}))
    monkeypatch.setattr(ocr_worker.SESSION, "get", get_mock)

    ocr_worker.fetch_candidate_documents()

    assert get_mock.call_args.kwargs["params"]["tags__id__none"] == "10,20"
    assert "tags__id__not" not in get_mock.call_args.kwargs["params"]


def test_fetch_candidate_documents_reprocess_excludes_only_processing_tag(monkeypatch):
    ocr_worker._TAG_ID_CACHE.clear()
    monkeypatch.setattr(ocr_worker.Config, "PAPERLESS_INPUT_TAG", None)
    monkeypatch.setattr(ocr_worker.Config, "PAPERLESS_REPROCESS", True)
    monkeypatch.setattr(ocr_worker.Config, "PAPERLESS_PROCESSED_TAG", "paddle_ocr")
    monkeypatch.setattr(ocr_worker.Config, "PAPERLESS_PROCESSING_TAG", "paddle_processing")
    monkeypatch.setattr(
        ocr_worker,
        "get_or_create_tag_id",
        lambda name: {"paddle_ocr": 10, "paddle_processing": 20}[name],
    )
    get_mock = MagicMock(return_value=_mock_response({"results": [], "next": None}))
    monkeypatch.setattr(ocr_worker.SESSION, "get", get_mock)

    ocr_worker.fetch_candidate_documents()

    assert get_mock.call_args.kwargs["params"]["tags__id__none"] == "20"
