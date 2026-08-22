import ocr_worker


def test_env_bool_true_values(monkeypatch):
    for value in ("1", "true", "True", "TRUE", "yes", "on"):
        monkeypatch.setenv("SOME_FLAG", value)
        assert ocr_worker._env_bool("SOME_FLAG", False) is True


def test_env_bool_false_values(monkeypatch):
    for value in ("0", "false", "False", "no", "off", ""):
        monkeypatch.setenv("SOME_FLAG", value)
        assert ocr_worker._env_bool("SOME_FLAG", True) is False


def test_env_bool_uses_default_when_unset(monkeypatch):
    monkeypatch.delenv("SOME_FLAG", raising=False)
    assert ocr_worker._env_bool("SOME_FLAG", True) is True
    assert ocr_worker._env_bool("SOME_FLAG", False) is False


def test_config_defaults_are_sane():
    assert ocr_worker.Config.OCR_TIER == "small"
    assert ocr_worker.Config.OCR_ENGINE == "paddle"
    assert ocr_worker.Config.PAPERLESS_RUN_MODE == "daemon"
    assert ocr_worker.Config.PAPERLESS_HEALTH_PORT == 8080
