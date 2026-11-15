import functools
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from flask import (
    Blueprint, abort, flash, g, redirect, render_template, request, session, url_for, jsonify
)
from werkzeug.security import check_password_hash, generate_password_hash

from . import models, throttle
from .db import get_db
from .notifications import notify_password_reset
from .security import password_problem

bp = Blueprint("auth", __name__, url_prefix="/auth")

RESET_TTL = timedelta(hours=1)
_RESET_TS_FORMAT = "%Y-%m-%d %H:%M:%S"


def _hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def _utc_now_str():
    return datetime.now(timezone.utc).strftime(_RESET_TS_FORMAT)


def safe_next_url(target):
    """Return ``target`` if it is a same-site path, else None.

    Rejects anything a browser could resolve to another host: absolute URLs,
    scheme-relative ``//host``, ``/\\host`` (browsers treat ``\\`` as ``/``), and
    control characters (browsers strip tabs/newlines, so ``/\\t/host`` becomes
    ``//host``).
    """
    if not target or not target.startswith("/"):
        return None
    if "\\" in target or any(ord(c) < 0x20 or ord(c) == 0x7F for c in target):
        return None
    if target.startswith("//"):
        return None
    parts = urlsplit(target)
    if parts.scheme or parts.netloc:
        return None
    return target


@bp.app_context_processor
def inject_last_login_notice():
    # Surface the prior login time once, on the first page rendered after login.
    return {"last_login_notice": session.pop("last_login_notice", None)}


@bp.before_app_request
def load_logged_in_user():
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
    else:
        g.user = get_db().execute(
            "SELECT * FROM user WHERE id = ?", (user_id,)
        ).fetchone()


def _authenticate(username, password):
    """Return the user row if credentials are valid, else None."""
    if not username or not password:
        return None
    user = get_db().execute(
        "SELECT * FROM user WHERE username = ?", (username,)
    ).fetchone()
    if user and check_password_hash(user["password_hash"], password):
        return user
    return None


def check_login(username, password):
    """Authenticate with failed-attempt throttling (see throttle.py).

    Returns ``(user, retry_after)``: the user row (or None), and the number of
    seconds the caller must wait when throttled (0 otherwise). A throttled attempt
    doesn't check the password at all, so it reveals nothing.
    """
    wait = throttle.retry_after(username)
    if wait:
        return None, wait
    user = _authenticate(username, password)
    if user is None:
        throttle.record_failure(username)
    else:
        throttle.record_success(username)
    return user, 0


def login_required(view):
    """For HTML views: redirect to the login page when not authenticated."""

    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("auth.login", next=request.full_path))
        return view(**kwargs)

    return wrapped_view


def admin_required(view):
    """For HTML views: require an authenticated admin user."""

    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("auth.login", next=request.full_path))
        if not g.user["is_admin"]:
            abort(403)
        return view(**kwargs)

    return wrapped_view


def api_auth_required(view):
    """For JSON API views: accept the session cookie or HTTP Basic auth.

    Returns 401 JSON when neither is present/valid.
    """

    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            auth = request.authorization
            if auth and auth.type == "basic":
                user, wait = check_login(auth.username, auth.password)
                if wait:
                    resp = jsonify(error="too many failed login attempts; try again later")
                    resp.status_code = 429
                    resp.headers["Retry-After"] = str(wait)
                    return resp
                if user is not None:
                    g.user = user
        if g.user is None:
            resp = jsonify(error="authentication required")
            resp.status_code = 401
            resp.headers["WWW-Authenticate"] = 'Basic realm="Reservations API"'
            return resp
        return view(**kwargs)

    return wrapped_view


@bp.route("/register", methods=("GET", "POST"))
def register():
    if g.user is not None:
        return redirect(url_for("web.list_widgets"))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        email = (request.form.get("email") or "").strip() or None
        phone = (request.form.get("phone") or "").strip() or None
        error = None
        if not username:
            error = "Username is required."
        else:
            error = password_problem(password)

        if error is None:
            try:
                user_id = models.create_user(
                    username, generate_password_hash(password), email, phone
                )
            except ValueError as e:
                error = str(e)
            else:
                session.clear()
                session["user_id"] = user_id
                return redirect(url_for("web.list_widgets"))

        flash(error)
    return render_template("auth/register.html")


@bp.route("/login", methods=("GET", "POST"))
def login():
    if g.user is not None:
        return redirect(url_for("web.list_widgets"))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user, wait = check_login(username, password)
        if wait:
            flash(
                "Too many failed sign-in attempts. "
                f"Try again in {throttle.minutes(wait)}."
            )
            return render_template("auth/login.html"), 429
        if user is None:
            flash("Incorrect username or password.")
        else:
            previous_login = user["last_login_at"]  # captured before we overwrite it
            models.record_login(user["id"])
            session.clear()
            session["user_id"] = user["id"]
            if previous_login:
                session["last_login_notice"] = previous_login
            next_url = safe_next_url(
                request.form.get("next") or request.args.get("next")
            )
            if next_url:
                return redirect(next_url)
            return redirect(url_for("web.list_widgets"))
    return render_template("auth/login.html")


@bp.route("/logout", methods=("GET", "POST"))
def logout():
    # Logging out changes state, so it's a CSRF-protected POST (the nav has a small
    # form). A plain GET (old bookmark, or a link on another site) only asks.
    if request.method == "POST":
        session.clear()
        return redirect(url_for("web.list_widgets"))
    if g.user is None:
        return redirect(url_for("web.list_widgets"))
    return render_template("auth/logout.html")


@bp.route("/forgot", methods=("GET", "POST"))
def forgot_password():
    if request.method == "POST":
        user = models.find_user_by_identifier(request.form.get("identifier"))
        # Only act when we have an account with an email, but always show the same
        # message so the form can't be used to discover which accounts exist.
        if user is not None and user["email"]:
            token = secrets.token_urlsafe(32)
            expires_at = (datetime.now(timezone.utc) + RESET_TTL).strftime(_RESET_TS_FORMAT)
            models.create_password_reset(user["id"], _hash_token(token), expires_at)
            reset_url = url_for("auth.reset_password", token=token, _external=True)
            notify_password_reset(user["id"], user["email"], user["username"], reset_url)
        flash("If an account matches, a password reset link has been sent.")
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot.html")


@bp.route("/reset/<token>", methods=("GET", "POST"))
def reset_password(token):
    reset = models.get_password_reset(_hash_token(token))
    if reset is None or reset["used"] or reset["expires_at"] < _utc_now_str():
        flash("That password reset link is invalid or has expired.")
        return redirect(url_for("auth.forgot_password"))
    if request.method == "POST":
        new = request.form.get("new_password") or ""
        confirm = request.form.get("confirm_password") or ""
        problem = password_problem(new)
        if problem:
            flash(problem)
        elif new != confirm:
            flash("New passwords do not match.")
        else:
            models.set_password(reset["user_id"], new)
            models.mark_reset_used(reset["id"])
            flash("Your password has been reset. Please log in.")
            return redirect(url_for("auth.login"))
    return render_template("auth/reset.html", token=token)
