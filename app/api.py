from flask import Blueprint, g, jsonify, request

from . import models
from .auth import api_auth_required

bp = Blueprint("api", __name__, url_prefix="/api")


def widget_json(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
    }


def reservation_json(row):
    keys = row.keys()
    data = {
        "id": row["id"],
        "widget_id": row["widget_id"],
        "user_id": row["user_id"],
        "start_time": row["start_time"],
        "end_time": row["end_time"],
        "note": row["note"],
        "created_at": row["created_at"],
    }
    if "username" in keys:
        data["username"] = row["username"]
    if "widget_name" in keys:
        data["widget_name"] = row["widget_name"]
    return data


def error(message, status):
    resp = jsonify(error=message)
    resp.status_code = status
    return resp


@bp.route("/widgets", methods=("GET",))
def list_widgets():
    return jsonify([widget_json(w) for w in models.list_widgets()])


@bp.route("/widgets", methods=("POST",))
@api_auth_required
def create_widget():
    data = request.get_json(silent=True) or {}
    try:
        widget_id = models.create_widget(
            data.get("name"), data.get("description", ""), g.user["id"]
        )
    except ValueError as e:
        return error(str(e), 400)
    return jsonify(widget_json(models.get_widget(widget_id))), 201


@bp.route("/widgets/<int:widget_id>", methods=("GET",))
def get_widget(widget_id):
    widget = models.get_widget(widget_id)
    if widget is None:
        return error("widget not found", 404)
    data = widget_json(widget)
    data["reservations"] = [
        reservation_json(r) for r in models.list_reservations_for_widget(widget_id)
    ]
    return jsonify(data)


@bp.route("/widgets/<int:widget_id>/reservations", methods=("GET",))
def widget_reservations(widget_id):
    if models.get_widget(widget_id) is None:
        return error("widget not found", 404)
    return jsonify(
        [reservation_json(r) for r in models.list_reservations_for_widget(widget_id)]
    )


@bp.route("/widgets/<int:widget_id>/reservations", methods=("POST",))
@api_auth_required
def create_reservation(widget_id):
    data = request.get_json(silent=True) or {}
    try:
        reservation_id = models.create_reservation(
            widget_id,
            g.user["id"],
            data.get("start_time"),
            data.get("end_time"),
            data.get("note", ""),
        )
    except models.OverlapError as e:
        return error(str(e), 409)
    except ValueError as e:
        return error(str(e), 400)
    return jsonify(reservation_json(models.get_reservation(reservation_id))), 201


@bp.route("/reservations", methods=("GET",))
@api_auth_required
def my_reservations():
    return jsonify(
        [reservation_json(r) for r in models.list_reservations_for_user(g.user["id"])]
    )


@bp.route("/reservations/<int:reservation_id>", methods=("DELETE",))
@api_auth_required
def cancel_reservation(reservation_id):
    reservation = models.get_reservation(reservation_id)
    if reservation is None:
        return error("reservation not found", 404)
    if reservation["user_id"] != g.user["id"]:
        return error("forbidden", 403)
    models.delete_reservation(reservation_id)
    return "", 204
