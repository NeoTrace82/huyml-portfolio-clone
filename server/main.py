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

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener
from starlette.middleware.sessions import SessionMiddleware

register_heif_opener()
MAX_IMAGE_PIXELS = 40_000_000
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

ROOT = Path(__file__).resolve().parent
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
MAX_UPLOAD_BYTES = 15 * 1024 * 1024
MAX_IMAGE_EDGE = 2200
ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
}
ALLOWED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}


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

    def authenticated(request: Request) -> bool:
        return request.session.get("studio_authenticated") is True

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
            raise HTTPException(status_code=413, detail="Images must be 15 MB or smaller")
        try:
            with Image.open(io.BytesIO(payload)) as source:
                if source.width * source.height > MAX_IMAGE_PIXELS:
                    raise HTTPException(status_code=413, detail="Image dimensions are too large")
                source.load()
                image = ImageOps.exif_transpose(source)
                if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
                    image = image.convert("RGBA")
                    matte = Image.new("RGB", image.size, "#f0f0ed")
                    matte.paste(image, mask=image.getchannel("A"))
                    image = matte
                else:
                    image = image.convert("RGB")
                image.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE), Image.Resampling.LANCZOS)
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
        if not hmac.compare_digest(password, password_value):
            token = secrets.token_urlsafe(32)
            request.session["login_csrf"] = token
            return templates.TemplateResponse(
                request=request,
                name="login.html",
                context={"request": request, "csrf_token": token, "error": "That password is not correct."},
                status_code=401,
            )
        request.session.clear()
        request.session["studio_authenticated"] = True
        request.session["csrf_token"] = secrets.token_urlsafe(32)
        return RedirectResponse("/studio", status_code=303)

    @app.get("/studio", response_class=HTMLResponse)
    def studio(request: Request):
        if not authenticated(request):
            return RedirectResponse("/studio/login", status_code=303)
        return templates.TemplateResponse(
            request=request,
            name="studio.html",
            context={"request": request, "projects": all_projects(), "csrf_token": request.session["csrf_token"]},
        )

    @app.post("/studio/logout")
    def studio_logout(request: Request, csrf_token: str = Form()):
        require_auth(request)
        require_csrf(request, csrf_token)
        request.session.clear()
        return RedirectResponse("/studio/login", status_code=303)

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
