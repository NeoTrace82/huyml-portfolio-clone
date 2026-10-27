"""All test imports and requests use scratch configuration; no outbound work."""
import os
from pathlib import Path
import secrets
import tempfile
from unittest.mock import patch

import pytest

scratch = Path(os.environ.get("TMPDIR", str(Path.home() / ".hermes/cache/scratch")))
scratch.mkdir(parents=True, exist_ok=True)
root = tempfile.mkdtemp(prefix="huyml-offline-", dir=scratch)
path = os.environ.get("PATH", "/usr/bin:/bin")
os.environ.clear()
os.environ.update(PATH=path, HOME=root, TMPDIR=root, DATA_DIR=root,
                  ADMIN_PASSWORD=secrets.token_urlsafe(24), SESSION_SECRET=secrets.token_urlsafe(48), COOKIE_SECURE="0")
tempfile.tempdir = root


def denied(*args, **kwargs):
    raise AssertionError("Outbound network forbidden during isolated tests")


@pytest.fixture(autouse=True)
def offline():
    with patch("socket.socket.connect", denied), patch("socket.create_connection", denied), patch("socket.getaddrinfo", denied):
        yield
