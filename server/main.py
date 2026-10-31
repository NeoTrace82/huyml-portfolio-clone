from __future__ import annotations

import hmac
import io
import json
import os
import re
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener
from starlette.middleware.sessions import SessionMiddleware
from .security import SessionLedger

register_heif_opener()
MAX_IMAGE_PIXELS = 100_000_000
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

ROOT = Path(__file__).resolve().parent
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}$")
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_IMAGE_EDGE = 1800
ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
}
ALLOWED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
SITE_SETTING_DEFAULTS = {
    "about_heading": "Good work\nshould feel",
    "about_accent": "alive.",
    "about_intro": "I’m Huy, an independent art director and digital designer working between identity, interaction and the happy accidents in between.",
    "about_details": "For the last decade I’ve helped studios, founders and curious teams turn fuzzy ideas into clear, expressive experiences.",
    "about_email": "hello@huyml.co",
    "contact_heading": "Let’s make\nsomething",
    "contact_accent": "memorable.",
    "contact_intro": "Got a project, a half-formed idea or just a good question? Drop me a line. The inbox is friendly.",
    "contact_email": "hello@huyml.co",
    "behance_url": "https://www.behance.net",
    "instagram_url": "https://www.instagram.com",
    "linkedin_url": "https://www.linkedin.com",
}


def square_web_image(image: Image.Image) -> Image.Image:
    square_edge = min(image.width, image.height)
    left = (image.width - square_edge) // 2
    image = image.crop((left, 0, left + square_edge, square_edge))
    if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
        image = image.convert("RGBA")
        matte = Image.new("RGB", image.size, "#f0f0ed")
        matte.paste(image, mask=image.getchannel("A"))
        image = matte
    else:
        image = image.convert("RGB")
    if image.width > MAX_IMAGE_EDGE:
        image = image.resize((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE), Image.Resampling.LANCZOS)
    return image


def create_app(
    *,
    data_dir: Path | str | None = None,
    static_dir: Path | str | None = None,
    defaults_path: Path | str | None = None,
    admin_password: str | None = None,
    session_secret: str | None = None,
    secure_cookies: bool | None = None,
) -> FastAPI:
    data_path = Path(data_dir or os.getenv("DATA_DIR", "/data"))
    static_path = Path(static_dir or os.getenv("STATIC_DIR", ROOT.parent / "dist"))
    defaults_file = Path(defaults_path or os.getenv("DEFAULT_PROJECTS_PATH", ROOT.parent / "public" / "projects.json"))
    password = admin_password if admin_password is not None else os.getenv("ADMIN_PASSWORD", "")
    secret = session_secret if session_secret is not None else os.getenv("SESSION_SECRET", "")
    cookie_secure = secure_cookies if secure_cookies is not None else os.getenv("COOKIE_SECURE", "1") != "0"
    if not password:
        raise RuntimeError("ADMIN_PASSWORD is required")
    if len(secret) < 32:
        raise RuntimeError("SESSION_SECRET must be at least 32 characters")

    uploads_path = data_path / "uploads"
    data_path.mkdir(parents=True, exist_ok=True)
    uploads_path.mkdir(parents=True, exist_ok=True)
    database_path = data_path / "site.db"
    auth_cookie = "huyml_studio_session"
    auth_max_age = 60 * 60 * 12
    auth_sessions = SessionLedger(data_path / "studio-sessions.db", password, secret, auth_max_age)
    templates = Jinja2Templates(directory=str(ROOT / "templates"))

    @contextmanager
    def connection():
        database = sqlite3.connect(database_path)
        database.row_factory = sqlite3.Row
        database.execute("PRAGMA foreign_keys = ON")
        database.execute("PRAGMA journal_mode = WAL")
        try:
            yield database
            database.commit()
        finally:
            database.close()

    def init_database() -> None:
        with connection() as database:
            database.execute(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY,
                    position INTEGER NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    year TEXT NOT NULL,
                    role TEXT NOT NULL,
                    description TEXT NOT NULL,
                    colors TEXT NOT NULL,
                    image TEXT NOT NULL,
                    alt_text TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL
                )
                """
            )
            columns = {row["name"] for row in database.execute("PRAGMA table_info(projects)").fetchall()}
            if "alt_text" not in columns:
                database.execute("ALTER TABLE projects ADD COLUMN alt_text TEXT NOT NULL DEFAULT ''")
            database.execute("UPDATE projects SET alt_text = title || ' — ' || role WHERE alt_text = ''")
            count = database.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
            if count == 0:
                defaults = json.loads(defaults_file.read_text(encoding="utf-8"))
                now = datetime.now(timezone.utc).isoformat()
                database.executemany(
                    """
                    INSERT INTO projects (id, position, title, year, role, description, colors, image, alt_text, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            int(item["id"]),
                            index,
                            item["title"],
                            item["year"],
                            item["role"],
                            item["description"],
                            json.dumps(item["colors"]),
                            item["image"],
                            item.get("alt_text") or f'{item["title"]} — {item["role"]}',
                            now,
                        )
                        for index, item in enumerate(defaults, start=1)
                    ],
                )
            database.execute(
                """
                CREATE TABLE IF NOT EXISTS site_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL
                )
                """
            )
            settings_now = datetime.now(timezone.utc).isoformat()
            database.executemany(
                "INSERT OR IGNORE INTO site_settings (key, value, updated_at) VALUES (?, ?, ?)",
                [(key, value, settings_now) for key, value in SITE_SETTING_DEFAULTS.items()],
            )

    def normalize_existing_uploads() -> None:
        with connection() as database:
            image_paths = [row[0] for row in database.execute("SELECT image FROM projects WHERE image LIKE '/media/%'")]
        for image_path in image_paths:
            filename = Path(image_path).name
            if image_path != f"/media/{filename}":
                continue
            source_path = uploads_path / filename
            if not source_path.is_file():
                continue
            temporary = uploads_path / f".{filename}.square.tmp"
            try:
                with Image.open(source_path) as source:
                    if source.width * source.height > MAX_IMAGE_PIXELS:
                        continue
                    source.load()
                    oriented = ImageOps.exif_transpose(source)
                    if oriented.width == oriented.height and oriented.width <= MAX_IMAGE_EDGE:
                        continue
                    image = square_web_image(oriented)
                image.save(temporary, format="JPEG", quality=85, optimize=True, progressive=True)
                os.replace(temporary, source_path)
            except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError):
                continue
            finally:
                temporary.unlink(missing_ok=True)

    def serialize(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "title": row["title"],
            "year": row["year"],
            "role": row["role"],
            "description": row["description"],
            "colors": json.loads(row["colors"]),
            "image": row["image"],
            "alt_text": row["alt_text"],
            "updated_at": row["updated_at"],
        }

    def all_projects() -> list[dict]:
        with connection() as database:
            rows = database.execute("SELECT * FROM projects ORDER BY position, id").fetchall()
        return [serialize(row) for row in rows]

    def all_settings() -> dict[str, str]:
        settings = dict(SITE_SETTING_DEFAULTS)
        with connection() as database:
            settings.update({row["key"]: row["value"] for row in database.execute("SELECT key, value FROM site_settings")})
        return settings

    def update_settings(values: dict[str, str]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with connection() as database:
            database.executemany(
                """
                INSERT INTO site_settings (key, value, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
                """,
                [(key, value, now) for key, value in values.items()],
            )

    def clean_email(value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) > 254 or not EMAIL_RE.fullmatch(cleaned):
            raise HTTPException(status_code=422, detail="Enter a valid email address")
        return cleaned

    def clean_optional_https_url(value: str, name: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            return ""
        try:
            parsed = urlparse(cleaned)
            valid = (
                len(cleaned) <= 2048
                and not any(character.isspace() or ord(character) < 32 or ord(character) == 127 for character in cleaned)
                and parsed.scheme == "https"
                and bool(parsed.hostname)
                and parsed.port != 0
                and parsed.username is None
                and parsed.password is None
            )
        except ValueError:
            valid = False
        if not valid:
            raise HTTPException(status_code=422, detail=f"Enter a valid HTTPS URL for {name}")
        return cleaned

    def studio_context(request: Request, **values) -> dict:
        request.session.setdefault("csrf_token", secrets.token_urlsafe(32))
        return {"request": request, "csrf_token": request.session["csrf_token"], **values}

    def authenticated(request: Request) -> bool:
        return auth_sessions.valid(request.cookies.get(auth_cookie))

    def require_auth(request: Request) -> None:
        if not authenticated(request):
            raise HTTPException(status_code=401, detail="Studio login required")

    def require_csrf(request: Request, submitted: str) -> None:
        expected = request.session.get("csrf_token", "")
        if not expected or not hmac.compare_digest(expected, submitted):
            raise HTTPException(status_code=403, detail="Invalid CSRF token")

    def clean_text(value: str, name: str, maximum: int) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise HTTPException(status_code=422, detail=f"{name} is required")
        if len(cleaned) > maximum:
            raise HTTPException(status_code=422, detail=f"{name} is too long")
        return cleaned

    async def save_upload(upload: UploadFile) -> str:
        content_type = (upload.content_type or "").lower()
        suffix = Path(upload.filename or "").suffix.lower()
        if content_type not in ALLOWED_CONTENT_TYPES and suffix not in ALLOWED_IMAGE_SUFFIXES:
            raise HTTPException(status_code=415, detail="Upload a JPG, PNG, WebP, HEIC, or HEIF image")
        payload = await upload.read(MAX_UPLOAD_BYTES + 1)
        await upload.close()
        if not payload:
            raise HTTPException(status_code=415, detail="The selected image is empty")
        if len(payload) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Images must be 50 MB or smaller")
        try:
            with Image.open(io.BytesIO(payload)) as source:
                if source.width * source.height > MAX_IMAGE_PIXELS:
                    raise HTTPException(status_code=413, detail="Image dimensions are too large")
                source.load()
                image = square_web_image(ImageOps.exif_transpose(source))
                filename = f"project-{uuid.uuid4().hex}.jpg"
                temporary = uploads_path / f".{filename}.tmp"
                destination = uploads_path / filename
                try:
                    image.save(temporary, format="JPEG", quality=85, optimize=True, progressive=True)
                    os.replace(temporary, destination)
                finally:
                    temporary.unlink(missing_ok=True)
                return f"/media/{filename}"
        except HTTPException:
            raise
        except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError):
            raise HTTPException(status_code=415, detail="The selected file is not a readable image") from None

    init_database()
    normalize_existing_uploads()
    app = FastAPI(title="HUYML Portfolio CMS", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(
        SessionMiddleware,
        secret_key=secret,
        session_cookie="huyml_studio",
        max_age=60 * 60 * 12,
        same_site="lax",
        https_only=cookie_secure,
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; base-uri 'self'; frame-ancestors 'none'; object-src 'none'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; img-src 'self' data: blob: https:; "
            "script-src 'self'; connect-src 'self'; form-action 'self'"
        )
        return response

    @app.get("/health")
    def health() -> dict:
        with connection() as database:
            count = database.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        return {"status": "ok", "projects": count}

    @app.get("/api/projects")
    def projects_api() -> JSONResponse:
        return JSONResponse(all_projects(), headers={"Cache-Control": "no-store"})

    @app.get("/api/site-settings")
    def site_settings_api() -> JSONResponse:
        return JSONResponse(all_settings(), headers={"Cache-Control": "no-store"})

    @app.get("/studio/login", response_class=HTMLResponse)
    def studio_login(request: Request):
        if authenticated(request):
            return RedirectResponse("/studio", status_code=303)
        token = secrets.token_urlsafe(32)
        request.session["login_csrf"] = token
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"request": request, "csrf_token": token, "error": None},
        )

    @app.post("/studio/login", response_class=HTMLResponse)
    def studio_login_submit(request: Request, password_value: str = Form(alias="password"), csrf_token: str = Form()):
        expected = request.session.get("login_csrf", "")
        if not expected or not hmac.compare_digest(expected, csrf_token):
            raise HTTPException(status_code=403, detail="Invalid CSRF token")
        auth_token = auth_sessions.issue(password_value)
        if auth_token is None:
            token = secrets.token_urlsafe(32)
            request.session["login_csrf"] = token
            return templates.TemplateResponse(
                request=request,
                name="login.html",
                context={"request": request, "csrf_token": token, "error": "That password is not correct."},
                status_code=401,
            )
        auth_sessions.revoke(request.cookies.get(auth_cookie))
        request.session.clear()
        request.session["csrf_token"] = secrets.token_urlsafe(32)
        response = RedirectResponse("/studio", status_code=303)
        response.set_cookie(auth_cookie, auth_token, max_age=auth_max_age, secure=cookie_secure,
                            httponly=True, samesite="lax")
        return response

    @app.get("/studio", response_class=HTMLResponse)
    def studio(request: Request):
        if not authenticated(request):
            return RedirectResponse("/studio/login", status_code=303)
        projects = all_projects()
        return templates.TemplateResponse(
            request=request,
            name="studio.html",
            context=studio_context(
                request,
                projects=projects,
                project_count=len(projects),
                first_project=projects[0] if projects else None,
                settings=all_settings(),
            ),
        )

    @app.get("/studio/work", response_class=HTMLResponse)
    def studio_work(request: Request):
        if not authenticated(request):
            return RedirectResponse("/studio/login", status_code=303)
        return templates.TemplateResponse(
            request=request,
            name="work.html",
            context=studio_context(request, projects=all_projects()),
        )

    @app.get("/studio/about", response_class=HTMLResponse)
    def studio_about(request: Request):
        if not authenticated(request):
            return RedirectResponse("/studio/login", status_code=303)
        return templates.TemplateResponse(
            request=request,
            name="about.html",
            context=studio_context(
                request,
                settings=all_settings(),
                saved=request.query_params.get("saved") == "1",
                error=None,
            ),
        )

    @app.post("/studio/about", response_class=HTMLResponse)
    def studio_about_submit(
        request: Request,
        about_heading: str = Form(),
        about_accent: str = Form(),
        about_intro: str = Form(),
        about_details: str = Form(),
        about_email: str = Form(),
        csrf_token: str = Form(),
    ):
        require_auth(request)
        require_csrf(request, csrf_token)
        submitted = all_settings()
        submitted.update(
            {
                "about_heading": about_heading,
                "about_accent": about_accent,
                "about_intro": about_intro,
                "about_details": about_details,
                "about_email": about_email,
            }
        )
        try:
            values = {
                "about_heading": clean_text(about_heading, "Heading", 120),
                "about_accent": clean_text(about_accent, "Highlighted line", 60),
                "about_intro": clean_text(about_intro, "Introduction", 800),
                "about_details": clean_text(about_details, "Biography", 1200),
                "about_email": clean_email(about_email),
            }
        except HTTPException as error:
            return templates.TemplateResponse(
                request=request,
                name="about.html",
                context=studio_context(request, settings=submitted, saved=False, error=error.detail),
                status_code=error.status_code,
            )
        update_settings(values)
        return RedirectResponse("/studio/about?saved=1", status_code=303)

    @app.get("/studio/contact", response_class=HTMLResponse)
    def studio_contact(request: Request):
        if not authenticated(request):
            return RedirectResponse("/studio/login", status_code=303)
        return templates.TemplateResponse(
            request=request,
            name="contact.html",
            context=studio_context(
                request,
                settings=all_settings(),
                saved=request.query_params.get("saved") == "1",
                error=None,
            ),
        )

    @app.post("/studio/contact", response_class=HTMLResponse)
    def studio_contact_submit(
        request: Request,
        contact_heading: str = Form(),
        contact_accent: str = Form(),
        contact_intro: str = Form(),
        contact_email: str = Form(),
        behance_url: str = Form(default=""),
        instagram_url: str = Form(default=""),
        linkedin_url: str = Form(default=""),
        csrf_token: str = Form(),
    ):
        require_auth(request)
        require_csrf(request, csrf_token)
        submitted = all_settings()
        submitted.update(
            {
                "contact_heading": contact_heading,
                "contact_accent": contact_accent,
                "contact_intro": contact_intro,
                "contact_email": contact_email,
                "behance_url": behance_url,
                "instagram_url": instagram_url,
                "linkedin_url": linkedin_url,
            }
        )
        try:
            values = {
                "contact_heading": clean_text(contact_heading, "Heading", 120),
                "contact_accent": clean_text(contact_accent, "Highlighted line", 60),
                "contact_intro": clean_text(contact_intro, "Introduction", 800),
                "contact_email": clean_email(contact_email),
                "behance_url": clean_optional_https_url(behance_url, "Behance"),
                "instagram_url": clean_optional_https_url(instagram_url, "Instagram"),
                "linkedin_url": clean_optional_https_url(linkedin_url, "LinkedIn"),
            }
        except HTTPException as error:
            return templates.TemplateResponse(
                request=request,
                name="contact.html",
                context=studio_context(request, settings=submitted, saved=False, error=error.detail),
                status_code=error.status_code,
            )
        update_settings(values)
        return RedirectResponse("/studio/contact?saved=1", status_code=303)

    @app.post("/studio/logout")
    def studio_logout(request: Request, csrf_token: str = Form()):
        require_auth(request)
        require_csrf(request, csrf_token)
        auth_sessions.revoke(request.cookies.get(auth_cookie))
        request.session.clear()
        response = RedirectResponse("/studio/login", status_code=303)
        response.delete_cookie(auth_cookie, secure=cookie_secure, httponly=True, samesite="lax")
        return response

    @app.post("/api/projects/{project_id}")
    async def update_project(
        request: Request,
        project_id: int,
        title: str = Form(),
        year: str = Form(),
        role: str = Form(),
        description: str = Form(),
        alt_text: str = Form(),
        color1: str = Form(),
        color2: str = Form(),
        color3: str = Form(),
        csrf_token: str = Form(),
        image_file: UploadFile | None = File(default=None),
    ) -> JSONResponse:
        require_auth(request)
        require_csrf(request, csrf_token)
        title = clean_text(title, "Title", 100)
        year = clean_text(year, "Year", 20)
        role = clean_text(role, "Role", 100)
        description = clean_text(description, "Description", 500)
        alt_text = clean_text(alt_text, "Picture description", 160)
        colors = [color1.lower(), color2.lower(), color3.lower()]
        if any(not COLOR_RE.fullmatch(color) for color in colors):
            raise HTTPException(status_code=422, detail="Every project color must be a six-digit hex value")

        with connection() as database:
            existing = database.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Project not found")

        uploaded = image_file is not None
        new_image = await save_upload(image_file) if uploaded else existing["image"]
        now = datetime.now(timezone.utc).isoformat()
        with connection() as database:
            database.execute(
                """
                UPDATE projects
                SET title=?, year=?, role=?, description=?, colors=?, image=?, alt_text=?, updated_at=?
                WHERE id=?
                """,
                (title, year, role, description, json.dumps(colors), new_image, alt_text, now, project_id),
            )
            row = database.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()

        old_image = existing["image"]
        if old_image.startswith("/media/") and old_image != new_image:
            old_file = uploads_path / Path(old_image).name
            old_file.unlink(missing_ok=True)
        return JSONResponse(serialize(row), headers={"Cache-Control": "no-store"})

    app.mount("/studio-assets", StaticFiles(directory=str(ROOT / "studio_assets")), name="studio-assets")
    app.mount("/media", StaticFiles(directory=str(uploads_path)), name="media")
    app.mount("/", StaticFiles(directory=str(static_path), html=True), name="site")
    return app


app = create_app()
