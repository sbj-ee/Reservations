import csv
import io

from flask import (
    Blueprint, Response, abort, flash, g, redirect, render_template, request, url_for
)

from . import models
from .auth import admin_required
from .notifications import notify_reservation_event

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/")
@admin_required
def dashboard():
    return render_template("admin/dashboard.html", counts=models.counts())


# --- Users -----------------------------------------------------------------

@bp.route("/users")
@admin_required
def users():
    return render_template("admin/users.html", users=models.list_users())


@bp.route("/users/<int:user_id>/toggle-admin", methods=("POST",))
@admin_required
def toggle_admin(user_id):
    user = models.get_user(user_id)
    if user is None:
        abort(404)
    if user["id"] == g.user["id"]:
        flash("You cannot change your own admin status.")
    else:
        models.set_user_admin(user_id, not user["is_admin"])
        flash(f"Updated admin status for {user['username']}.")
    return redirect(url_for("admin.users"))


@bp.route("/users/<int:user_id>/delete", methods=("POST",))
@admin_required
def delete_user(user_id):
    user = models.get_user(user_id)
    if user is None:
        abort(404)
    if user["id"] == g.user["id"]:
        flash("You cannot delete your own account.")
    else:
        models.delete_user(user_id)
        flash(f"Deleted user {user['username']}.")
    return redirect(url_for("admin.users"))


# --- Widgets ---------------------------------------------------------------

@bp.route("/widgets")
@admin_required
def widgets():
    return render_template("admin/widgets.html", widgets=models.list_widgets())


@bp.route("/widgets/<int:widget_id>/edit", methods=("GET", "POST"))
@admin_required
def edit_widget(widget_id):
    widget = models.get_widget(widget_id)
    if widget is None:
        abort(404)
    if request.method == "POST":
        try:
            models.update_widget(
                widget_id, request.form.get("name"), request.form.get("description")
            )
        except ValueError as e:
            flash(str(e))
            return render_template("admin/widget_edit.html", widget=widget)
        flash("Widget updated.")
        return redirect(url_for("admin.widgets"))
    return render_template("admin/widget_edit.html", widget=widget)


@bp.route("/widgets/<int:widget_id>/delete", methods=("POST",))
@admin_required
def delete_widget(widget_id):
    widget = models.get_widget(widget_id)
    if widget is None:
        abort(404)
    models.delete_widget(widget_id)
    flash(f"Deleted widget {widget['name']} and its reservations.")
    return redirect(url_for("admin.widgets"))


# --- Reservations (entries) ------------------------------------------------

@bp.route("/reservations")
@admin_required
def reservations():
    return render_template(
        "admin/reservations.html", reservations=models.list_all_reservations()
    )


@bp.route("/reservations/<int:reservation_id>/delete", methods=("POST",))
@admin_required
def delete_reservation(reservation_id):
    reservation = models.get_reservation(reservation_id)
    if reservation is None:
        abort(404)
    snapshot = models.reservation_snapshot(reservation_id)
    models.delete_reservation(reservation_id)
    notify_reservation_event("cancelled", snapshot)
    flash("Reservation deleted.")
    return redirect(url_for("admin.reservations"))


@bp.route("/reports/reservations.csv")
@admin_required
def reservations_csv():
    rows = models.query_reservations(
        date_from=request.args.get("from"),
        date_to=request.args.get("to"),
        widget_id=request.args.get("widget_id", type=int),
        user_id=request.args.get("user_id", type=int),
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["reservation_id", "widget_id", "widget", "user",
         "start_time", "end_time", "note", "created_at"]
    )
    for r in rows:
        writer.writerow([
            r["id"], r["widget_id"], r["widget_name"], r["username"],
            r["start_time"], r["end_time"], r["note"], r["created_at"],
        ])
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=reservations.csv"},
    )


# --- Notifications log -----------------------------------------------------

@bp.route("/notifications")
@admin_required
def notifications():
    return render_template(
        "admin/notifications.html", notifications=models.list_notifications()
    )
