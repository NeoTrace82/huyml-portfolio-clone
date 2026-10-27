"""Single-admin opaque sessions, independent of Flask/CSRF and sender auth.

All workers must share this durable ledger and the same configuration. Observed
configuration changes revoke all sessions, including across later reversions.
"""
from contextlib import contextmanager
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time

TOKEN_RE = re.compile(r"[A-Za-z0-9_-]{43}\Z")


class SessionLedger:
    def __init__(self, path, password, signing_key, max_age):
        self.path = Path(path)
        self.password = password
        self.max_age = max_age
        # A keyed fingerprint prevents offline password guessing from the ledger.
        self.binding = hmac.new(signing_key.encode(), json.dumps(
            ["admin-session-v1", password, max_age], separators=(",", ":")
        ).encode(), hashlib.sha256).hexdigest()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Keep the ledger private even with a permissive process umask.
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            os.fchmod(fd, 0o600)
        finally:
            os.close(fd)
        with self.transaction():
            pass  # Observe rotations at startup, even without an authenticated request.

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=15)
        try:
            db.execute("BEGIN IMMEDIATE")
            db.execute("CREATE TABLE IF NOT EXISTS admin_sessions (token_hash TEXT PRIMARY KEY, binding TEXT NOT NULL, created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS admin_session_state (id INTEGER PRIMARY KEY CHECK(id=1), binding TEXT NOT NULL)")
            row = db.execute("SELECT binding FROM admin_session_state WHERE id=1").fetchone()
            if row is None or not hmac.compare_digest(row[0], self.binding):
                db.execute("DELETE FROM admin_sessions")
                db.execute("INSERT OR REPLACE INTO admin_session_state VALUES(1,?)", (self.binding,))
            db.execute("DELETE FROM admin_sessions WHERE expires_at<=?", (int(time.time()),))
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def digest(token):
        if not isinstance(token, str) or not TOKEN_RE.fullmatch(token):
            return None
        return hashlib.sha256(token.encode()).hexdigest()

    def issue(self, submitted_password):
        # Verification, state synchronization and insertion share one write lock.
        with self.transaction() as db:
            if not hmac.compare_digest(self.password, submitted_password):
                return None
            token = secrets.token_urlsafe(32)
            now = int(time.time())
            db.execute("INSERT INTO admin_sessions VALUES(?,?,?,?)",
                       (self.digest(token), self.binding, now, now + self.max_age))
            return token

    def valid(self, token):
        with self.transaction() as db:
            digest = self.digest(token)
            row = db.execute("SELECT binding FROM admin_sessions WHERE token_hash=?", (digest,)).fetchone()
            return row is not None and hmac.compare_digest(row[0], self.binding)

    def revoke(self, token):
        with self.transaction() as db:
            db.execute("DELETE FROM admin_sessions WHERE token_hash=?", (self.digest(token),))
