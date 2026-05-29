import sqlite3

import click
from flask import current_app, g
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE"],
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    with current_app.open_resource("schema.sql") as f:
        db.executescript(f.read().decode("utf8"))


def init_db_if_needed():
    db = get_db()
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='user'"
    ).fetchone()
    if row is None:
        init_db()
    else:
        _migrate(db)


def _migrate(db):
    """Apply small, idempotent schema changes to a pre-existing database."""
    columns = {r["name"] for r in db.execute("PRAGMA table_info(user)").fetchall()}
    if "is_admin" not in columns:
        db.execute("ALTER TABLE user ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
        db.commit()


@click.command("init-db")
@with_appcontext
def init_db_command():
    """Clear existing data and create new tables."""
    init_db()
    click.echo("Initialized the database.")


@click.command("create-admin")
@click.argument("username")
@click.argument("password")
@with_appcontext
def create_admin_command(username, password):
    """Create a new user with admin privileges."""
    db = get_db()
    try:
        db.execute(
            "INSERT INTO user (username, password_hash, is_admin) VALUES (?, ?, 1)",
            (username, generate_password_hash(password)),
        )
        db.commit()
    except db.IntegrityError:
        raise click.ClickException(f"User {username!r} already exists.")
    click.echo(f"Created admin {username!r}.")


@click.command("set-admin")
@click.argument("username")
@click.option("--remove", is_flag=True, help="Revoke admin instead of granting it.")
@with_appcontext
def set_admin_command(username, remove):
    """Grant (or, with --remove, revoke) admin on an existing user."""
    db = get_db()
    cur = db.execute(
        "UPDATE user SET is_admin = ? WHERE username = ?",
        (0 if remove else 1, username),
    )
    db.commit()
    if cur.rowcount == 0:
        raise click.ClickException(f"No user named {username!r}.")
    verb = "Revoked admin from" if remove else "Granted admin to"
    click.echo(f"{verb} {username!r}.")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    app.cli.add_command(create_admin_command)
    app.cli.add_command(set_admin_command)
