import io
import os
import re
import sqlite3
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

from server.main import MAX_IMAGE_EDGE, MAX_UPLOAD_BYTES, create_app

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
        "alt_text": project["alt_text"],
        "color1": colors[0],
        "color2": colors[1],
        "color3": colors[2],
        "csrf_token": csrf_token,
    }
    data.update(updates)
    return data


def settings_payload(csrf_token: str, **updates) -> dict:
    data = {
        "about_heading": "Good work\nshould feel",
        "about_accent": "alive.",
        "about_intro": "I’m Huy, an independent art director and digital designer.",
        "about_details": "For the last decade I’ve helped curious teams make expressive experiences.",
        "about_email": "hello@huyml.co",
        "contact_heading": "Let’s make\nsomething",
        "contact_accent": "memorable.",
        "contact_intro": "Got a project or a good question? Drop me a line.",
        "contact_email": "hello@huyml.co",
        "behance_url": "https://www.behance.net",
        "instagram_url": "https://www.instagram.com",
        "linkedin_url": "https://www.linkedin.com",
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
    assert '<img class="preview__image"' in homepage.text
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
            alt_text="Blue shapes for the edited Lumen project",
            color1="#112233",
        ),
    )
    assert response.status_code == 200
    saved = response.json()
    assert saved["title"] == "Edited Lumen"
    assert saved["description"].startswith("A saved description")
    assert saved["alt_text"] == "Blue shapes for the edited Lumen project"
    assert saved["colors"][0] == "#112233"

    fresh_client = make_client(tmp_path)
    public = fresh_client.get("/api/projects").json()[0]
    assert public["title"] == "Edited Lumen"
    assert public["year"] == "2027"
    assert public["alt_text"] == "Blue shapes for the edited Lumen project"


def test_free_form_image_url_is_not_an_edit_path(tmp_path):
    client = make_client(tmp_path)
    csrf = login(client)
    project = client.get("/api/projects").json()[0]

    response = client.post(
        f"/api/projects/{project['id']}",
        data=project_payload(project, csrf, image_url="https://example.com/not-an-image"),
    )

    assert response.status_code == 200
    assert response.json()["image"] == project["image"]
    studio = client.get("/studio/work")
    assert 'name="image_url"' not in studio.text


def test_existing_database_is_migrated_with_picture_descriptions(tmp_path):
    database_path = tmp_path / "site.db"
    with sqlite3.connect(database_path) as database:
        database.execute(
            """
            CREATE TABLE projects (
                id INTEGER PRIMARY KEY,
                position INTEGER NOT NULL UNIQUE,
                title TEXT NOT NULL,
                year TEXT NOT NULL,
                role TEXT NOT NULL,
                description TEXT NOT NULL,
                colors TEXT NOT NULL,
                image TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        database.execute(
            "INSERT INTO projects VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (1, 1, "Legacy", "2024", "Design", "Existing work", '["#111111", "#222222", "#333333"]', "https://example.com/legacy.jpg", "2024-01-01"),
        )

    project = make_client(tmp_path).get("/api/projects").json()[0]

    assert project["title"] == "Legacy"
    assert project["alt_text"] == "Legacy — Design"


def test_studio_forms_have_unique_accessible_project_names(tmp_path):
    client = make_client(tmp_path)
    login(client)
    studio = client.get("/studio/work")

    assert studio.status_code == 200
    assert 'aria-labelledby="editor-project-1"' in studio.text
    assert 'aria-label="Save Lumen project"' in studio.text
    assert 'name="alt_text"' in studio.text


def test_studio_home_links_to_simple_configuration_subpages(tmp_path):
    client = make_client(tmp_path)
    login(client)

    dashboard = client.get("/studio")
    work = client.get("/studio/work")

    assert dashboard.status_code == 200
    assert "Choose what to edit" in dashboard.text
    assert 'href="/studio/work"' in dashboard.text
    assert 'href="/studio/about"' in dashboard.text
    assert 'href="/studio/contact"' in dashboard.text
    assert dashboard.text.count('class="studio-choice ') == 3
    assert 'class="project-form"' not in dashboard.text
    assert work.status_code == 200
    assert work.text.count('class="project-form"') == 19


def test_all_studio_subpages_require_login(tmp_path):
    client = make_client(tmp_path)

    for path in ("/studio/work", "/studio/about", "/studio/contact"):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/studio/login"


def test_about_page_settings_persist_and_are_public(tmp_path):
    client = make_client(tmp_path)
    csrf = login(client)
    response = client.post(
        "/studio/about",
        data=settings_payload(
            csrf,
            about_heading="Portraits\nwith purpose",
            about_accent="and warmth.",
            about_intro="First line\nSecond line",
            about_details="A safe <script>alert(1)</script> biography.",
            about_email="studio@example.com",
        ),
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/studio/about?saved=1"
    public = client.get("/api/site-settings")
    assert public.status_code == 200
    assert public.headers["cache-control"] == "no-store"
    assert public.json()["about_heading"] == "Portraits\nwith purpose"
    assert public.json()["about_email"] == "studio@example.com"

    fresh = make_client(tmp_path)
    assert fresh.get("/studio/about", follow_redirects=False).status_code == 303
    login(fresh)
    editor = fresh.get("/studio/about")
    assert "Portraits\nwith purpose" in editor.text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in editor.text
    assert "<script>alert(1)</script>" not in editor.text


def test_contact_page_settings_validate_and_persist(tmp_path):
    client = make_client(tmp_path)
    csrf = login(client)
    saved = client.post(
        "/studio/contact",
        data=settings_payload(
            csrf,
            contact_heading="Start a\nconversation",
            contact_accent="today.",
            contact_email="contact@example.com",
            instagram_url="",
        ),
        follow_redirects=False,
    )

    assert saved.status_code == 303
    assert saved.headers["location"] == "/studio/contact?saved=1"
    settings = client.get("/api/site-settings").json()
    assert settings["contact_email"] == "contact@example.com"
    assert settings["instagram_url"] == ""

    rejected = client.post(
        "/studio/contact",
        data=settings_payload(csrf, instagram_url="javascript:alert(1)"),
    )
    assert rejected.status_code == 422
    assert "valid HTTPS URL" in rejected.text
    assert client.get("/api/site-settings").json()["contact_email"] == "contact@example.com"


@pytest.mark.parametrize("path", ["/studio", "/studio/work", "/studio/about", "/studio/contact"])
def test_studio_pages_restore_csrf_state_for_valid_opaque_session(tmp_path, path):
    client = make_client(tmp_path)
    login(client)
    auth_token = client.cookies.get("huyml_studio_session")
    assert auth_token is not None
    client.cookies.clear()
    client.cookies.set("huyml_studio_session", auth_token)

    page = client.get(path)
    assert page.status_code == 200
    match = re.search(r'name="csrf_token" value="([^"]+)"', page.text)
    assert match is not None
    token = match.group(1)
    assert client.post("/studio/logout", data={"csrf_token": token}, follow_redirects=False).status_code == 303


@pytest.mark.parametrize("path", ["/studio/about", "/studio/contact"])
def test_settings_require_auth_csrf_and_reject_logged_out_cookie_replay(tmp_path, path):
    client = make_client(tmp_path)
    original = client.get("/api/site-settings").json()
    assert client.post(path, data=settings_payload("bad")).status_code == 401
    token = login(client)
    copied = dict(client.cookies)
    assert client.post(path, data=settings_payload("bad")).status_code == 403
    assert client.post("/studio/logout", data={"csrf_token": token}, follow_redirects=False).status_code == 303
    client.cookies.update(copied)
    assert client.post(path, data=settings_payload(token)).status_code == 401
    assert client.get("/api/site-settings").json() == original


@pytest.mark.parametrize("value", [
    "https://[invalid", "https://example.com:invalid", "https://example.com:65536",
    "https://example.com/line\nbreak", "https://example.com/has space",
    "https://user:password@example.com", "http://example.com", "//example.com",
    "javascript:alert(1)", "https://",
])
def test_contact_rejects_malformed_social_urls_without_saving(tmp_path, value):
    client = make_client(tmp_path)
    token = login(client)
    before = client.get("/api/site-settings").json()
    response = client.post("/studio/contact", data=settings_payload(token, instagram_url=value))
    assert response.status_code == 422
    assert "valid HTTPS URL" in response.text
    assert client.get("/api/site-settings").json() == before


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
        assert image.size == (1800, 1800)
        assert image.mode == "RGB"
    served = client.get(image_url)
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/jpeg"


def test_upload_limit_and_square_output_size_are_configured_for_portfolio_photos():
    assert MAX_UPLOAD_BYTES == 50 * 1024 * 1024
    assert MAX_IMAGE_EDGE == 1800


def test_valid_picture_larger_than_previous_15_mb_limit_is_accepted(tmp_path):
    client = make_client(tmp_path)
    csrf = login(client)
    project = client.get("/api/projects").json()[0]
    source = Image.frombytes("RGB", (2500, 2200), os.urandom(2500 * 2200 * 3))
    payload = io.BytesIO()
    source.save(payload, format="PNG")
    upload = payload.getvalue()
    assert 15 * 1024 * 1024 < len(upload) < MAX_UPLOAD_BYTES

    response = client.post(
        f"/api/projects/{project['id']}",
        data=project_payload(project, csrf),
        files={"image_file": ("large-photo.png", upload, "image/png")},
    )

    assert response.status_code == 200
    stored = tmp_path / "uploads" / Path(response.json()["image"]).name
    with Image.open(stored) as image:
        assert image.size == (1800, 1800)


def test_vertical_picture_keeps_the_top_square(tmp_path):
    client = make_client(tmp_path)
    csrf = login(client)
    project = client.get("/api/projects").json()[0]
    source = Image.new("RGB", (400, 600), "#d9272e")
    source.paste("#1d43a8", (0, 400, 400, 600))
    payload = io.BytesIO()
    source.save(payload, format="PNG")

    response = client.post(
        f"/api/projects/{project['id']}",
        data=project_payload(project, csrf),
        files={"image_file": ("vertical.png", payload.getvalue(), "image/png")},
    )

    assert response.status_code == 200
    stored = tmp_path / "uploads" / Path(response.json()["image"]).name
    with Image.open(stored) as image:
        assert image.size == (400, 400)
        pixel = image.getpixel((200, 390))
        assert isinstance(pixel, tuple)
        red, green, blue = pixel
        assert red > 150 and blue < 100


def test_horizontal_picture_uses_a_centered_square_crop(tmp_path):
    client = make_client(tmp_path)
    csrf = login(client)
    project = client.get("/api/projects").json()[0]
    source = Image.new("RGB", (600, 400), "#d9272e")
    source.paste("#208747", (100, 0, 500, 400))
    source.paste("#1d43a8", (500, 0, 600, 400))
    payload = io.BytesIO()
    source.save(payload, format="PNG")

    response = client.post(
        f"/api/projects/{project['id']}",
        data=project_payload(project, csrf),
        files={"image_file": ("horizontal.png", payload.getvalue(), "image/png")},
    )

    assert response.status_code == 200
    stored = tmp_path / "uploads" / Path(response.json()["image"]).name
    with Image.open(stored) as image:
        assert image.size == (400, 400)
        pixel = image.getpixel((200, 200))
        assert isinstance(pixel, tuple)
        red, green, blue = pixel
        assert green > red and green > blue


def test_existing_local_picture_is_migrated_once_to_square(tmp_path):
    client = make_client(tmp_path)
    project = client.get("/api/projects").json()[0]
    source = Image.new("RGB", (600, 400), "#d9272e")
    source.paste("#208747", (100, 0, 500, 400))
    source.paste("#1d43a8", (500, 0, 600, 400))
    image_path = tmp_path / "uploads" / "legacy.jpg"
    source.save(image_path, format="JPEG", quality=95)
    with sqlite3.connect(tmp_path / "site.db") as database:
        database.execute("UPDATE projects SET image = '/media/legacy.jpg' WHERE id = ?", (project["id"],))

    make_client(tmp_path)

    with Image.open(image_path) as migrated:
        assert migrated.size == (400, 400)
        pixel = migrated.getpixel((200, 200))
        assert isinstance(pixel, tuple)
        red, green, blue = pixel
        assert green > red and green > blue
    first_mtime = image_path.stat().st_mtime_ns
    make_client(tmp_path)
    assert image_path.stat().st_mtime_ns == first_mtime


def test_public_and_studio_previews_use_square_top_centered_framing(tmp_path):
    client = make_client(tmp_path)
    login(client)
    public_css = (ROOT / "styles.css").read_text(encoding="utf-8")
    studio_css = client.get("/studio-assets/studio.css").text
    studio = client.get("/studio/work").text

    assert "aspect-ratio: 1 / 1" in public_css
    assert "object-position: center top" in public_css
    assert "aspect-ratio:1/1" in studio_css
    assert "object-position:center top" in studio_css
    assert "maximum 50 MB" in studio


def test_featured_image_motion_and_grain_are_restrained():
    public_css = (ROOT / "styles.css").read_text(encoding="utf-8")

    assert "transform: scale(1.002)" in public_css
    assert ".hero__visual:hover .visual__image { transform: scale(1.018); }" in public_css
    assert "baseFrequency='.60' numOctaves='2'" in public_css
    assert ".visual__grain { position: absolute; inset: 0; opacity: .08;" in public_css
    assert "translate(4px,-5px) rotate(2deg)" in public_css
    assert "translate(-6px,4px) scale(1.025)" in public_css


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
