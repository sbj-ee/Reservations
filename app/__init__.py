import os

from flask import Flask, redirect, url_for


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-change-me"),
        DATABASE=os.path.join(app.instance_path, "reservations.sqlite"),
    )

    if test_config is not None:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)

    from . import db, auth, web, api

    db.init_app(app)
    app.register_blueprint(auth.bp)
    app.register_blueprint(web.bp)
    app.register_blueprint(api.bp)

    @app.route("/")
    def index():
        return redirect(url_for("web.list_widgets"))

    # Create tables on first run so the app is usable without a manual step.
    with app.app_context():
        db.init_db_if_needed()

    return app
