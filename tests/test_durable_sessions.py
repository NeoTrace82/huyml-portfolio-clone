"""Offline regression coverage for the durable dashboard ledger."""
import secrets
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from server import security


def test_lifecycle_rotation_reversion_restart_expiry(tmp_path, monkeypatch):
    path = tmp_path / "sessions.db"
    password, key = secrets.token_urlsafe(24), secrets.token_urlsafe(48)
    now = [1000]
    monkeypatch.setattr(security.time, "time", lambda: now[0])
    ledger = security.SessionLedger(path, password, key, 100)
    a, b = ledger.issue(password), ledger.issue(password)
    assert isinstance(a, str) and isinstance(b, str)
    assert a != b and ledger.valid(a) and ledger.valid(b)
    assert ledger.issue("incorrect") is None
    with sqlite3.connect(path) as db:
        dump = "\n".join(db.iterdump())
        assert a not in dump and b not in dump and password not in dump and key not in dump
    assert security.SessionLedger(path, password, key, 100).valid(a)
    now[0] = 1099
    assert ledger.valid(a)
    now[0] = 1100
    assert not ledger.valid(a)  # reads never slide the absolute deadline
    now[0] = 1000
    assert not ledger.valid(a)  # expired rows are removed durably
    ledger.revoke(b)
    assert not security.SessionLedger(path, password, key, 100).valid(b)
    for changed_password, changed_key in [(password + "x", key), (password, key + "x")]:
        original = security.SessionLedger(path, password, key, 100)
        token = original.issue(password)
        security.SessionLedger(path, changed_password, changed_key, 100)
        restored = security.SessionLedger(path, password, key, 100)
        assert not restored.valid(token)
    for malformed in [None, "", "true", "a" * 42, "a" * 44, "!" * 43, {}, 1]:
        assert not ledger.valid(malformed)


def test_transactional_concurrent_sessions(tmp_path):
    password, key = secrets.token_urlsafe(24), secrets.token_urlsafe(48)
    ledger = security.SessionLedger(tmp_path / "sessions.db", password, key, 100)
    with ThreadPoolExecutor(max_workers=4) as pool:
        tokens = list(pool.map(lambda _: ledger.issue(password), range(8)))
    assert len(set(tokens)) == 8
    assert all(ledger.valid(token) for token in tokens)
    ledger.revoke(tokens[0])
    assert not ledger.valid(tokens[0]) and all(ledger.valid(t) for t in tokens[1:])


def test_ledger_private_permissions_and_symlink_rejection(tmp_path):
    import os
    import stat
    path = tmp_path / "private-sessions.db"
    password, key = secrets.token_urlsafe(24), secrets.token_urlsafe(48)
    previous = os.umask(0)
    try:
        security.SessionLedger(path, password, key, 100)
    finally:
        os.umask(previous)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    path.chmod(0o666)
    security.SessionLedger(path, password, key, 100)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    link = tmp_path / "linked-sessions.db"
    link.symlink_to(path)
    with pytest.raises(OSError):
        security.SessionLedger(link, password, key, 100)
