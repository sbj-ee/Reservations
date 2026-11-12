import os
import subprocess
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Flask, redirect, url_for

from .utils import system_timezone_name

# Bump on each release (semantic versioning). Shown in the header next to the
# git commit, so it's always clear exactly which code is being served.
__version__ = "1.0.0"


def _git_commit():
    """Short commit hash of the running code: APP_BUILD env if set (for deploys
    without a .git directory), else asked from git, else None."""
    if os.environ.get("APP_BUILD"):
        return os.environ["APP_BUILD"]
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=True, text=True, timeout=2, check=True,
        )
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        # Unset -> a random key persisted in the instance folder (see security.py),
        # never a guessable default.
        SECRET_KEY=os.environ.get("SECRET_KEY"),
        MIN_PASSWORD_LENGTH=int(os.environ.get("MIN_PASSWORD_LENGTH", "8")),
        # Time zone for times shown server-side (email/SMS). Times are stored in UTC;
        # web pages convert to each viewer's own zone in the browser.
        APP_TIMEZONE=os.environ.get("APP_TIMEZONE") or system_timezone_name(),
        DATABASE=os.path.join(app.instance_path, "reservations.sqlite"),
        # Email (SMTP) notification settings — optional; logged when unset.
        MAIL_SERVER=os.environ.get("MAIL_SERVER"),
        MAIL_PORT=int(os.environ.get("MAIL_PORT", "587")),
        MAIL_USERNAME=os.environ.get("MAIL_USERNAME"),
        MAIL_PASSWORD=os.environ.get("MAIL_PASSWORD"),
        MAIL_FROM=os.environ.get("MAIL_FROM"),
        MAIL_USE_TLS=os.environ.get("MAIL_USE_TLS", "true").lower()
        in ("1", "true", "yes", "on"),
        # SMS (Twilio) notification settings — optional; logged when unset.
        TWILIO_ACCOUNT_SID=os.environ.get("TWILIO_ACCOUNT_SID"),
        TWILIO_AUTH_TOKEN=os.environ.get("TWILIO_AUTH_TOKEN"),
        TWILIO_FROM=os.environ.get("TWILIO_FROM"),
    )

    app.config["APP_VERSION"] = __version__
    app.config["APP_BUILD"] = _git_commit()

    if test_config is not None:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)

    try:
        app.config["APP_TZINFO"] = ZoneInfo(app.config["APP_TIMEZONE"])
    except (ZoneInfoNotFoundError, ValueError) as e:
        raise RuntimeError(
            f"APP_TIMEZONE={app.config['APP_TIMEZONE']!r} is not a known time zone "
            "(use an IANA name such as 'America/Chicago')"
        ) from e

    from . import db, auth, web, api, admin, security

    security.init_app(app)
    app.jinja_env.globals["app_version"] = app.config["APP_VERSION"]
    app.jinja_env.globals["app_build"] = app.config["APP_BUILD"]
    db.init_app(app)
    app.register_blueprint(auth.bp)
    app.register_blueprint(web.bp)
    app.register_blueprint(api.bp)
    app.register_blueprint(admin.bp)

    @app.route("/")
    def index():
        return redirect(url_for("web.list_widgets"))

    # Create tables on first run so the app is usable without a manual step.
    with app.app_context():
        db.init_db_if_needed()

    return app
