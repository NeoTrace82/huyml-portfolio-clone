import base64
import json
from pathlib import Path
import re
import secrets

from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
import pytest

from server.main import create_app
from server import security

ROOT = Path(__file__).resolve().parents[1]
COOKIE = "huyml_studio_session"


def csrf(page):
    return re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)


def client(path, password, key):
    return TestClient(create_app(data_dir=path, static_dir=ROOT / "dist", admin_password=password,
                                 session_secret=key, secure_cookies=False), follow_redirects=False)


def login(c, password):
    assert c.post('/studio/login', data={'password': password, 'csrf_token': csrf(c.get('/studio/login'))}).status_code == 303
    assert c.get('/studio').status_code == 200


def payload(c):
    p = c.get('/api/projects').json()[0]
    return p['id'], dict(title=p['title'], year=p['year'], role=p['role'], description=p['description'],
                         alt_text=p['alt_text'], color1=p['colors'][0], color2=p['colors'][1], color3=p['colors'][2],
                         csrf_token=csrf(c.get('/studio')))


def test_real_forms_logout_replay_simultaneous_and_legacy(tmp_path):
    password, key = secrets.token_urlsafe(24), secrets.token_urlsafe(48)
    a = client(tmp_path, password, key)
    b = TestClient(a.app, follow_redirects=False)
    login(a, password)
    login(b, password)
    copied = dict(a.cookies)
    ident, data = payload(a)
    assert a.post(f'/api/projects/{ident}', data=data).status_code == 200
    assert a.post(f'/api/projects/{ident}', data={**data, 'csrf_token': 'bad'}).status_code == 403
    assert a.post('/studio/logout', data={'csrf_token': data['csrf_token']}).status_code == 303
    a.cookies.update(copied)
    assert a.get('/studio').status_code == 303
    assert a.post(f'/api/projects/{ident}', data=data).status_code == 401
    assert b.get('/studio').status_code == 200
    old = TestClient(a.app, follow_redirects=False)
    legacy = TimestampSigner(key).sign(base64.b64encode(json.dumps({'studio_authenticated': True, 'csrf_token': 'legacy'}).encode())).decode()
    old.cookies.set('huyml_studio', legacy)
    assert old.get('/studio').status_code == 303
    for value in ['true', 'a' * 43, 'not.a.valid.token']:
        old.cookies.set(COOKIE, value)
        assert old.get('/studio').status_code == 303


@pytest.mark.parametrize('setting', ['password', 'key'])
def test_restart_rotation_and_reversion(tmp_path, setting):
    password, key = secrets.token_urlsafe(24), secrets.token_urlsafe(48)
    a = client(tmp_path, password, key)
    login(a, password)
    copied = dict(a.cookies)
    restarted = client(tmp_path, password, key)
    restarted.cookies.update(copied)
    assert restarted.get('/studio').status_code == 200
    client(tmp_path, password + 'x' if setting == 'password' else password, key + 'x' if setting == 'key' else key)
    restored = client(tmp_path, password, key)
    restored.cookies.update(copied)
    assert restored.get('/studio').status_code == 303
    login(restored, password)


def test_absolute_expiry_no_sliding(tmp_path, monkeypatch):
    password, key = secrets.token_urlsafe(24), secrets.token_urlsafe(48)
    now = [1000000]
    monkeypatch.setattr(security.time, 'time', lambda: now[0])
    a = client(tmp_path, password, key)
    login(a, password)
    now[0] += 12 * 60 * 60 - 1
    assert a.get('/studio').status_code == 200
    now[0] += 1
    assert a.get('/studio').status_code == 303


def test_blackbox_logout_cookie_replay(tmp_path):
    password, key = secrets.token_urlsafe(24), secrets.token_urlsafe(48)
    a = client(tmp_path, password, key)
    login(a, password)
    copied = dict(a.cookies)
    token = csrf(a.get('/studio'))
    assert a.post('/studio/logout', data={'csrf_token': token}).status_code == 303
    a.cookies.update(copied)
    assert a.get('/studio').status_code == 303
