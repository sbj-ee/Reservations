import functools

from flask import (
    Blueprint, abort, flash, g, redirect, render_template, request, session, url_for, jsonify
)
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db

bp = Blueprint("auth", __name__, url_prefix="/auth")


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
                user = _authenticate(auth.username, auth.password)
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
        error = None
        if not username:
            error = "Username is required."
        elif not password:
            error = "Password is required."

        if error is None:
            db = get_db()
            try:
                db.execute(
                    "INSERT INTO user (username, password_hash) VALUES (?, ?)",
                    (username, generate_password_hash(password)),
                )
                db.commit()
            except db.IntegrityError:
                error = f"User {username} is already registered."
            else:
                user = db.execute(
                    "SELECT * FROM user WHERE username = ?", (username,)
                ).fetchone()
                session.clear()
                session["user_id"] = user["id"]
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
        user = _authenticate(username, password)
        if user is None:
            flash("Incorrect username or password.")
        else:
            session.clear()
            session["user_id"] = user["id"]
            next_url = request.form.get("next") or request.args.get("next")
            if next_url and next_url.startswith("/"):
                return redirect(next_url)
            return redirect(url_for("web.list_widgets"))
    return render_template("auth/login.html")


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("web.list_widgets"))
