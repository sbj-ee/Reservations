"""Request-forgery (CSRF) protection and secret-key handling.

CSRF: every server-rendered form carries a per-session token
(``{{ csrf_field() }}``), and every unsafe request outside the JSON API must
present it. The API is exempt from the token because its unsafe methods are
either PUT/DELETE (which cross-site forms can't send) or POST with a JSON body,
and we enforce the JSON content type so a cross-site form can never reach it.
"""
import hmac
import os
import secrets

from flask import abort, request, session
from markupsafe import Markup, escape

CSRF_FIELD = "csrf_token"
CSRF_HEADER = "X-CSRF-Token"
SESSION_KEY = "_csrf_token"
_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_API_BLUEPRINT = "api"


def csrf_token():
    """The current session's CSRF token, created on first use."""
    token = session.get(SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[SESSION_KEY] = token
    return token


def csrf_field():
    """Hidden form input carrying the CSRF token, for use in templates."""
    return Markup(
        f'<input type="hidden" name="{CSRF_FIELD}" value="{escape(csrf_token())}">'
    )


def _check_csrf():
    if request.method not in _UNSAFE_METHODS:
        return
    if request.blueprint == _API_BLUEPRINT:
        # Cross-site forms can only POST urlencoded/multipart/text bodies; a JSON
        # content type requires a CORS preflight, which we never grant.
        if request.method == "POST" and not request.is_json:
            abort(415, description="API requests must send a JSON body.")
        return
    sent = request.form.get(CSRF_FIELD) or request.headers.get(CSRF_HEADER)
    expected = session.get(SESSION_KEY)
    if not sent or not expected or not hmac.compare_digest(sent, expected):
        abort(
            400,
            description="This form has expired or was not submitted from this site. "
            "Go back, reload the page, and try again.",
        )


def load_or_create_secret_key(instance_path):
    """Return the secret key stored in the instance folder, creating it if needed.

    Used when SECRET_KEY isn't set in the environment, instead of a guessable
    default. The file is created atomically (several gunicorn workers may start at
    once) and is readable only by the owner. The instance folder is gitignored.
    """
    path = os.path.join(instance_path, "secret_key")
    try:
        with open(path) as f:
            key = f.read().strip()
        if key:
            return key
    except FileNotFoundError:
        pass

    tmp = f"{path}.{os.getpid()}.{secrets.token_hex(4)}.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(secrets.token_hex(32))
        try:
            os.link(tmp, path)  # fails if another process won the race
        except FileExistsError:
            pass
    finally:
        os.unlink(tmp)
    with open(path) as f:
        return f.read().strip()


def init_app(app):
    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = load_or_create_secret_key(app.instance_path)
    # Flask's defaults include SESSION_COOKIE_SAMESITE=None, so setdefault won't do.
    if app.config.get("SESSION_COOKIE_SAMESITE") is None:
        app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.before_request(_check_csrf)
    app.jinja_env.globals["csrf_token"] = csrf_token
    app.jinja_env.globals["csrf_field"] = csrf_field
