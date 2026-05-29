# Contributing

Thanks for your interest in improving Widget Reservations! This is a small Flask +
SQLite project, so the workflow is intentionally lightweight.

## Getting set up

1. Fork and clone the repo, then create a branch off `main`:

   ```bash
   git checkout -b my-change
   ```

2. Create a virtual environment and install dependencies:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements-dev.txt
   ```

   > If `python3 -m venv` fails with *"ensurepip is not available"* (common on
   > Debian/Ubuntu without the `python3-venv` package), bootstrap pip manually:
   >
   > ```bash
   > python3 -m venv .venv --without-pip
   > source .venv/bin/activate
   > curl -sS https://bootstrap.pypa.io/get-pip.py | python
   > pip install -r requirements-dev.txt
   > ```

## Running the app

The SQLite database is created automatically on first run at
`instance/reservations.sqlite`. Use Flask's reloader during development:

```bash
flask --app app run --debug
```

To run it the way it's deployed, use gunicorn:

```bash
SECRET_KEY=dev gunicorn -w 4 -b 127.0.0.1:8000 wsgi:app
```

Reset the database at any time with `flask --app app init-db`. Create an admin user with
`flask --app app create-admin <username> <password>` (or `set-admin <username>` to promote
an existing one) to access the `/admin` control panel.

## Tests

Every change should keep the suite green, and new behavior should come with tests.

```bash
pytest
```

Tests live in `tests/` and use a throwaway temporary database per test (see
`tests/conftest.py`), so they never touch your `instance/` data.

## Project layout

| Path | Purpose |
| --- | --- |
| `app/__init__.py` | App factory; auto-creates the DB on first run |
| `app/db.py` | SQLite connection + `init-db` CLI command |
| `app/schema.sql` | `user` / `widget` / `reservation` tables |
| `app/models.py` | Data access + overlap check (`OverlapError`) |
| `app/utils.py` | Datetime parsing/normalization |
| `app/auth.py` | Register/login/logout + `login_required` / `admin_required` / `api_auth_required` |
| `app/web.py` | Server-rendered UI routes |
| `app/api.py` | JSON API routes under `/api` |
| `app/admin.py` | Admin panel routes under `/admin`, CSV export, notifications log |
| `app/notifications.py` | Email (SMTP) + SMS (Twilio) channels with log/audit fallback |
| `app/templates/`, `app/static/` | Jinja templates and CSS |
| `tests/` | pytest suite |
| `wsgi.py` | gunicorn entrypoint (`wsgi:app`) |

A few conventions worth knowing:

- **Shared data logic lives in `app/models.py`.** Both the web and API layers call the
  same functions, so business rules (like overlap rejection) stay in one place. Add new
  query/mutation logic there rather than inside route handlers.
- **Times are stored in UTC.** `app/utils.parse_dt` canonicalizes input to a UTC
  `YYYY-MM-DD HH:MM` string (tz-aware ISO input is converted; naive input is assumed UTC),
  so string ordering matches chronological order and overlap checks work across time zones.
  Reuse it for any new datetime input. The browser (`app/static/tz.js`) handles local↔UTC
  for the UI; keep server-side logic in UTC.
- **API errors** return JSON `{"error": "..."}` with a meaningful status code
  (`400` bad input, `401` unauthenticated, `403` forbidden, `404` missing, `409` overlap).
- **Notifications** fire from the route layer after a reservation is created/changed/cancelled
  via `app/notifications.py`. Email/SMS providers are configured with env vars (`MAIL_*`,
  `TWILIO_*`); when unset, messages are logged and recorded to the `notification` table, so
  tests and local dev work without credentials. Dispatch must never raise into the request.

## Style

- Standard PEP 8 / 4-space indentation. Keep imports tidy and functions small.
- Match the surrounding code; avoid introducing new dependencies without discussion.

## Submitting changes

1. Make sure `pytest` passes.
2. Use clear, focused commits with descriptive messages.
3. Open a pull request against `main` describing **what** changed and **why**, and
   mention any new endpoints or schema changes.

By contributing, you agree that your contributions are licensed under the
[MIT License](LICENSE).
