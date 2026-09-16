"""Tests for the in-container singleton guard added for GH #23.

These exercise acquire_singleton_lock() directly against a temp lock path
rather than the real /tmp/paperless-paddle-ocr.lock, so tests don't step on
each other or on a real worker running on the same machine.
"""

import fcntl

import pytest

import ocr_worker


def test_acquire_singleton_lock_succeeds_when_unlocked(tmp_path, monkeypatch):
    lock_path = tmp_path / "worker.lock"
    monkeypatch.setattr(ocr_worker, "_SINGLETON_LOCK_PATH", str(lock_path))
    monkeypatch.setattr(ocr_worker, "_singleton_lock_fh", None)

    ocr_worker.acquire_singleton_lock()

    assert lock_path.exists()
    assert ocr_worker._singleton_lock_fh is not None


def test_acquire_singleton_lock_exits_when_already_held(tmp_path, monkeypatch):
    lock_path = tmp_path / "worker.lock"
    monkeypatch.setattr(ocr_worker, "_SINGLETON_LOCK_PATH", str(lock_path))
    monkeypatch.setattr(ocr_worker, "_singleton_lock_fh", None)

    # Simulate a first worker instance already holding the lock.
    holder = open(lock_path, "w")  # noqa: SIM115 - held deliberately across the assertions below
    fcntl.flock(holder, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        with pytest.raises(SystemExit) as exc_info:
            ocr_worker.acquire_singleton_lock()
        assert exc_info.value.code == 1
    finally:
        fcntl.flock(holder, fcntl.LOCK_UN)
        holder.close()
