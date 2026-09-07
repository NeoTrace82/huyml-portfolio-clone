# HUYML — editable portfolio direction

An original portfolio experience inspired by the editorial interaction language of [huyml.co](https://huyml.co): oversized typography, compact metadata, project rail, live image previews, and panel-based navigation.

The implementation does not copy the reference site's proprietary artwork, code, or portfolio media. Default project visuals use open Unsplash imagery.

## Features

- Portfolio opens immediately with no entry or splash screen
- Hover, click, and next-project preview switching
- Responsive desktop and mobile layouts
- Password-protected `/studio` editor
- Editable project title, year, role, description, palette, and picture
- Image URL support plus JPG, PNG, WebP, HEIC, and HEIF uploads
- macOS Finder/Photos-picker uploads are materialized before transfer for reliable browser submission
- Uploaded images are normalized to progressive JPEG with a 2200 px maximum edge
- SQLite project data and uploads persist under `/data`
- CSRF-protected writes, secure sessions, security headers, and non-root container runtime

## Frontend development

```bash
npm install
npm run dev
```

The Vite-only preview uses `public/projects.json` as a read-only fallback.

## Full CMS development

```bash
npm run build
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt -r requirements-dev.txt
DATA_DIR=/tmp/huyml-data \
ADMIN_PASSWORD='choose-a-password' \
SESSION_SECRET='use-at-least-32-random-characters-here' \
COOKIE_SECURE=0 \
.venv/bin/uvicorn server.main:app --host 127.0.0.1 --port 8080
```

Run the tests with:

```bash
.venv/bin/pytest -q
```

## Deployment

Public site: `https://testsite.digital-impressions.at`

Editor: `https://testsite.digital-impressions.at/studio`

The multi-architecture GHCR image is deployed as a genuine Portainer stack. The service joins the shared `proxy` network without publishing a direct host port. Mutable state is mounted from `/home/debian/portainer/huyml-portfolio-clone` to `/data`; `ADMIN_PASSWORD` and `SESSION_SECRET` are supplied through protected Portainer stack environment values.
