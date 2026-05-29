# Widget Reservations

![Python](https://img.shields.io/badge/python-3.12-3776AB.svg?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.x-000000.svg?logo=flask&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-3-003B57.svg?logo=sqlite&logoColor=white)
![Gunicorn](https://img.shields.io/badge/server-gunicorn-499848.svg?logo=gunicorn&logoColor=white)
![Tests](https://img.shields.io/badge/tests-pytest-0A9EDC.svg?logo=pytest&logoColor=white)

A small reservation system built with **Python, Flask, and SQLite**. Users register and
log in, browse **widgets** (any bookable resource), and reserve a widget for a time range.
Overlapping reservations for the same widget are rejected. It ships with both a
server-rendered web UI and a JSON API, and is served with **gunicorn**.

![Widget detail page showing the reservations table and the reserve form](docs/screenshot.png)

## Features

- Username/password accounts (session login + password hashing via Werkzeug)
- Widgets: anyone can browse; logged-in users can create them
- Reservations: book a widget for a `start`/`end` time, with overlap prevention
- Web UI (Jinja templates) **and** a JSON API under `/api`
- API accepts either the session cookie or HTTP Basic auth

## Setup

Python 3.12. Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The SQLite database is created automatically on first run at
`instance/reservations.sqlite`. To reset it explicitly:

```bash
flask --app app init-db
```

## Run

Production-style, with gunicorn (the WSGI entrypoint is `wsgi:app`):

```bash
SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')" \
  gunicorn -w 4 -b 127.0.0.1:8000 wsgi:app
```

Then open http://127.0.0.1:8000/.

For local development with auto-reload you can instead use Flask's server:

```bash
flask --app app run --debug
```

## API

`POST`/`DELETE` endpoints require authentication (session cookie or HTTP Basic).
`GET` endpoints for widgets are public.

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| GET | `/api/widgets` | no | List widgets |
| POST | `/api/widgets` | yes | Create a widget (`{name, description}`) |
| GET | `/api/widgets/<id>` | no | Widget detail + its reservations |
| GET | `/api/widgets/<id>/reservations` | no | List a widget's reservations |
| POST | `/api/widgets/<id>/reservations` | yes | Reserve (`{start_time, end_time, note}`) — `409` on overlap |
| GET | `/api/reservations` | yes | List the current user's reservations |
| DELETE | `/api/reservations/<id>` | yes | Cancel your reservation |

Times accept `YYYY-MM-DDTHH:MM` or `YYYY-MM-DD HH:MM` and are stored/returned as
`YYYY-MM-DD HH:MM`.

### Example

```bash
# create a widget with HTTP Basic auth
curl -u alice:secret -X POST http://127.0.0.1:8000/api/widgets \
  -H 'Content-Type: application/json' \
  -d '{"name": "Conference Room", "description": "Seats 8"}'

# reserve it
curl -u alice:secret -X POST http://127.0.0.1:8000/api/widgets/1/reservations \
  -H 'Content-Type: application/json' \
  -d '{"start_time": "2026-06-01T09:00", "end_time": "2026-06-01T10:00"}'
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

## Project layout

```
app/
  __init__.py      app factory; auto-creates the DB on first run
  db.py            SQLite connection + init-db CLI command
  schema.sql       user / widget / reservation tables
  models.py        data access + overlap check (raises OverlapError)
  utils.py         datetime parsing/normalization
  auth.py          register/login/logout + login_required / api_auth_required
  web.py           server-rendered UI routes
  api.py           JSON API routes (/api)
  templates/       Jinja templates
  static/style.css styling
tests/             pytest suite
wsgi.py            gunicorn entrypoint (wsgi:app)
```
