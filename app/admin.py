from flask import (
    Blueprint, abort, flash, g, redirect, render_template, request, url_for
)

from . import models
from .auth import admin_required

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
    models.delete_reservation(reservation_id)
    flash("Reservation deleted.")
    return redirect(url_for("admin.reservations"))
