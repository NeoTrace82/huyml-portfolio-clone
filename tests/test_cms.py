import io
import os
import re
import tempfile
from pathlib import Path

import pytest
from PIL import Image

BOOTSTRAP = tempfile.TemporaryDirectory(prefix="huyml-test-bootstrap-")
os.environ["DATA_DIR"] = BOOTSTRAP.name
os.environ["ADMIN_PASSWORD"] = "bootstrap-password"
os.environ["SESSION_SECRET"] = "bootstrap-session-secret-that-is-long-enough"
os.environ["COOKIE_SECURE"] = "0"

from fastapi.testclient import TestClient

from server.main import create_app

ROOT = Path(__file__).resolve().parents[1]


def make_client(data_dir: Path) -> TestClient:
    app = create_app(
        data_dir=data_dir,
        static_dir=ROOT / "dist",
        defaults_path=ROOT / "public" / "projects.json",
        admin_password="correct-horse-battery-staple",
        session_secret="test-session-secret-value-with-more-than-32-characters",
        secure_cookies=False,
    )
    return TestClient(app)


def test_session_secret_is_mandatory(tmp_path):
    with pytest.raises(RuntimeError, match="SESSION_SECRET"):
        create_app(
            data_dir=tmp_path,
            static_dir=ROOT / "dist",
            defaults_path=ROOT / "public" / "projects.json",
            admin_password="correct-horse-battery-staple",
            session_secret="",
        )


def login(client: TestClient) -> str:
    page = client.get("/studio/login")
    assert page.status_code == 200
    token = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
    response = client.post(
        "/studio/login",
        data={"password": "correct-horse-battery-staple", "csrf_token": token},
        follow_redirects=False,
    )
    assert response.status_code == 303
    studio = client.get("/studio")
    assert studio.status_code == 200
    return re.search(r'name="csrf_token" value="([^"]+)"', studio.text).group(1)


def project_payload(project: dict, csrf_token: str, **updates) -> dict:
    colors = project["colors"]
    data = {
        "title": project["title"],
        "year": project["year"],
        "role": project["role"],
        "description": project["description"],
        "color1": colors[0],
        "color2": colors[1],
        "color3": colors[2],
        "image_url": project["image"],
        "csrf_token": csrf_token,
    }
    data.update(updates)
    return data


def test_public_site_has_no_enter_page_and_loads_projects(tmp_path):
    client = make_client(tmp_path)
    homepage = client.get("/")
    assert homepage.status_code == 200
    assert "Enter portfolio" not in homepage.text
    assert '<main class="site">' in homepage.text
    projects = client.get("/api/projects")
    assert projects.status_code == 200
    assert len(projects.json()) == 19
    assert projects.headers["cache-control"] == "no-store"


def test_studio_requires_login_and_rejects_invalid_csrf(tmp_path):
    client = make_client(tmp_path)
    response = client.get("/studio", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/studio/login"
    project = client.get("/api/projects").json()[0]
    unauthenticated = client.post(f"/api/projects/{project['id']}", data=project_payload(project, "wrong"))
    assert unauthenticated.status_code == 401
    login(client)
    bad_csrf = client.post(f"/api/projects/{project['id']}", data=project_payload(project, "wrong"))
    assert bad_csrf.status_code == 403


def test_text_edit_persists_and_is_public(tmp_path):
    client = make_client(tmp_path)
    csrf = login(client)
    project = client.get("/api/projects").json()[0]
    response = client.post(
        f"/api/projects/{project['id']}",
        data=project_payload(
            project,
            csrf,
            title="Edited Lumen",
            year="2027",
            role="Direction / Digital",
            description="A saved description shown on the public selected-work preview.",
            color1="#112233",
        ),
    )
    assert response.status_code == 200
    saved = response.json()
    assert saved["title"] == "Edited Lumen"
    assert saved["description"].startswith("A saved description")
    assert saved["colors"][0] == "#112233"

    fresh_client = make_client(tmp_path)
    public = fresh_client.get("/api/projects").json()[0]
    assert public["title"] == "Edited Lumen"
    assert public["year"] == "2027"


def test_uploaded_picture_is_normalized_and_served(tmp_path):
    client = make_client(tmp_path)
    csrf = login(client)
    project = client.get("/api/projects").json()[0]
    source = Image.new("RGBA", (3000, 1800), (255, 60, 80, 180))
    payload = io.BytesIO()
    source.save(payload, format="PNG")

    response = client.post(
        f"/api/projects/{project['id']}",
        data=project_payload(project, csrf),
        files={"image_file": ("portfolio.png", payload.getvalue(), "image/png")},
    )
    assert response.status_code == 200
    image_url = response.json()["image"]
    assert image_url.startswith("/media/project-")
    assert image_url.endswith(".jpg")

    stored = tmp_path / "uploads" / Path(image_url).name
    assert stored.exists()
    with Image.open(stored) as image:
        assert image.format == "JPEG"
        assert max(image.size) == 2200
        assert image.mode == "RGB"
    served = client.get(image_url)
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/jpeg"


def test_heif_picture_without_filename_extension_is_accepted(tmp_path):
    client = make_client(tmp_path)
    csrf = login(client)
    project = client.get("/api/projects").json()[0]
    payload = io.BytesIO()
    Image.new("RGB", (120, 80), (20, 90, 180)).save(payload, format="HEIF")

    response = client.post(
        f"/api/projects/{project['id']}",
        data=project_payload(project, csrf),
        files={"image_file": ("photo", payload.getvalue(), "image/heif")},
    )

    assert response.status_code == 200
    assert response.json()["image"].endswith(".jpg")


def test_valid_extension_is_accepted_when_browser_omits_image_mime(tmp_path):
    client = make_client(tmp_path)
    csrf = login(client)
    project = client.get("/api/projects").json()[0]
    payload = io.BytesIO()
    Image.new("RGB", (120, 80), (180, 90, 20)).save(payload, format="JPEG")

    response = client.post(
        f"/api/projects/{project['id']}",
        data=project_payload(project, csrf),
        files={"image_file": ("photo.jpg", payload.getvalue(), "application/octet-stream")},
    )

    assert response.status_code == 200
    assert response.json()["image"].endswith(".jpg")


def test_invalid_image_is_rejected_without_changing_project(tmp_path):
    client = make_client(tmp_path)
    csrf = login(client)
    project = client.get("/api/projects").json()[0]
    response = client.post(
        f"/api/projects/{project['id']}",
        data=project_payload(project, csrf),
        files={"image_file": ("not-an-image.png", b"not an image", "image/png")},
    )
    assert response.status_code == 415
    assert client.get("/api/projects").json()[0]["image"] == project["image"]
