import ocr_worker


def test_get_tag_ids_from_doc_with_dicts():
    doc = {"tags": [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]}
    assert ocr_worker.get_tag_ids_from_doc(doc) == [1, 2]


def test_get_tag_ids_from_doc_with_plain_ints():
    doc = {"tags": [3, 4]}
    assert ocr_worker.get_tag_ids_from_doc(doc) == [3, 4]


def test_get_tag_ids_from_doc_with_digit_strings():
    doc = {"tags": ["5", "6"]}
    assert ocr_worker.get_tag_ids_from_doc(doc) == [5, 6]


def test_get_tag_ids_from_doc_mixed_and_ignores_junk():
    doc = {"tags": [{"id": 1}, 2, "3", "not-a-number", {"no_id_field": True}]}
    assert ocr_worker.get_tag_ids_from_doc(doc) == [1, 2, 3]


def test_get_tag_ids_from_doc_no_tags_key():
    assert ocr_worker.get_tag_ids_from_doc({}) == []


def test_apply_tag_adds_when_missing():
    result = ocr_worker.apply_tag(doc_id=1, current_tags=[1, 2], tag_id=3)
    assert result == [1, 2, 3]


def test_apply_tag_no_duplicate_when_already_present():
    result = ocr_worker.apply_tag(doc_id=1, current_tags=[1, 2, 3], tag_id=3)
    assert result == [1, 2, 3]


def test_apply_tag_noop_when_tag_id_is_none():
    result = ocr_worker.apply_tag(doc_id=1, current_tags=[1, 2], tag_id=None)
    assert result == [1, 2]
