# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

**Widget Reservations** — a **Flask + SQLite** reservation system (served with **gunicorn**).
Users register/log in, browse "widgets" (any bookable resource), and reserve one for a
start/end time; **overlapping reservations are rejected**. Ships a server-rendered web UI
**and** a JSON API. (Same app skeleton as the `Gradebook` repo.)

## Layout (`app/` package)

- `__init__.py` — Flask **app factory**.
- `web.py` — server-rendered routes; `api.py` — JSON API routes.
- `auth.py` — accounts/login (password hashing via **Werkzeug**); `admin.py` — admin views.
- `models.py` — data access; `db.py` — connection/helpers; `utils.py`; `notifications.py`
  (e.g. password-reset emails).
- `schema.sql` — **SQLite schema** (source of truth for tables).
- `templates/` (Jinja, by area), `static/` (css/svg/js).
- `tests/` — `pytest` with `conftest.py` fixtures.

## Setup, run & test

- Python **3.12**. `pip install -r requirements.txt` (dev: `requirements-dev.txt`).
- Run via the app factory — gunicorn in prod, Flask dev server locally. Initialize the DB from
  `app/schema.sql`.
- **Tests:** `pytest` (config in `pytest.ini`; fixtures in `tests/conftest.py`).

## Conventions

- Keep **web vs API** split (`web.py` vs `api.py`); share logic via `models.py`/`utils.py`.
- Auth/session is centralized in `auth.py` — route new endpoints through it; never roll your own
  password handling.
- **Overlap prevention** is the core invariant for reservations — cover it with tests on any
  change to booking logic.
- Schema changes go in `app/schema.sql` and `models.py` together.

## Public repo

This repository is **public**. Do not commit secrets, real user data, or sensitive fixtures.
`SECRET_KEY`/DB paths come from env/config, never hardcoded.
