# HUYML — editable portfolio direction

An original portfolio experience inspired by the editorial interaction language of [huyml.co](https://huyml.co): oversized typography, compact metadata, project rail, live image previews, and panel-based navigation.

The implementation does not copy the reference site's proprietary artwork, code, or portfolio media. Default project visuals use open Unsplash imagery.

## Features

- Portfolio opens immediately with no entry or splash screen
- Hover, click, and next-project preview switching
- Responsive desktop and mobile layouts
- Password-protected `/studio` editor
- Editable project title, year, role, description, palette, and picture
- JPG, PNG, WebP, HEIC, and HEIF picture uploads
- macOS Finder/Photos-picker uploads are materialized before transfer for reliable browser submission
- Uploads up to 50 MB are cropped from the top-center to 1:1 and saved as progressive JPEG at up to 1800 × 1800 px
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
npm ci && npm run build # Required: CMS tests serve dist/.
.venv/bin/pytest -q
```

## Studio sessions

Studio sessions expire **12 hours after login**, without sliding renewal on use.
Logout revokes the session server-side, so copied cookies cannot log back in.
Legacy signed authentication cookies are rejected; sign in again after upgrading.
Opaque random session tokens are stored only as hashes in `/data/studio-sessions.db`.
Keep this private ledger durable alongside `site.db`. Unchanged configuration
preserves valid sessions across restarts. Observed `ADMIN_PASSWORD` or
`SESSION_SECRET` changes durably revoke all sessions, including after reversion
to an old value. All workers must share the ledger and identical configuration;
mixed configuration revokes sessions rather than accepting both credentials.
Changes never loaded by an app instance cannot be detected. The existing signed
session cookie continues to hold CSRF state, not an authentication boolean.

## Deployment

Public site: `https://testsite.digital-impressions.at`

Editor: `https://testsite.digital-impressions.at/studio`

The multi-architecture GHCR image is deployed as a genuine Portainer stack. The service joins the shared `proxy` network without publishing a direct host port. Mutable state is mounted from `/home/debian/portainer/huyml-portfolio-clone` to `/data`; `ADMIN_PASSWORD` and `SESSION_SECRET` are supplied through protected Portainer stack environment values.
