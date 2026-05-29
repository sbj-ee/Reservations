from flask import (
    Blueprint, abort, flash, g, redirect, render_template, request, url_for
)
from werkzeug.security import check_password_hash

from . import models
from .auth import login_required
from .notifications import notify_reservation_event

bp = Blueprint("web", __name__)


@bp.route("/widgets")
def list_widgets():
    return render_template("widgets/list.html", widgets=models.list_widgets())


@bp.route("/widgets/new", methods=("GET", "POST"))
@login_required
def new_widget():
    if request.method == "POST":
        try:
            widget_id = models.create_widget(
                request.form.get("name"),
                request.form.get("description"),
                g.user["id"],
            )
        except ValueError as e:
            flash(str(e))
            return render_template("widgets/new.html", form=request.form)
        flash("Widget created.")
        return redirect(url_for("web.widget_detail", widget_id=widget_id))
    return render_template("widgets/new.html", form={})


@bp.route("/widgets/<int:widget_id>")
def widget_detail(widget_id):
    widget = models.get_widget(widget_id)
    if widget is None:
        abort(404)
    reservations = models.list_reservations_for_widget(widget_id)
    return render_template(
        "widgets/detail.html", widget=widget, reservations=reservations
    )


@bp.route("/widgets/<int:widget_id>/reserve", methods=("POST",))
@login_required
def reserve_widget(widget_id):
    widget = models.get_widget(widget_id)
    if widget is None:
        abort(404)
    try:
        reservation_id = models.create_reservation(
            widget_id,
            g.user["id"],
            request.form.get("start_time"),
            request.form.get("end_time"),
            request.form.get("note"),
        )
        notify_reservation_event("created", models.reservation_snapshot(reservation_id))
        flash("Reservation confirmed.")
    except (ValueError, models.OverlapError) as e:
        flash(str(e))
    return redirect(url_for("web.widget_detail", widget_id=widget_id))


@bp.route("/reservations")
@login_required
def my_reservations():
    reservations = models.list_reservations_for_user(g.user["id"])
    return render_template("reservations/list.html", reservations=reservations)


@bp.route("/account", methods=("GET", "POST"))
@login_required
def account():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "profile":
            try:
                models.update_contact(
                    g.user["id"], request.form.get("email"), request.form.get("phone")
                )
                flash("Contact details updated.")
                return redirect(url_for("web.account"))
            except ValueError as e:
                flash(str(e))
        if action == "password":
            current = request.form.get("current_password") or ""
            new = request.form.get("new_password") or ""
            confirm = request.form.get("confirm_password") or ""
            if not check_password_hash(g.user["password_hash"], current):
                flash("Current password is incorrect.")
            elif not new:
                flash("New password is required.")
            elif new != confirm:
                flash("New passwords do not match.")
            else:
                models.set_password(g.user["id"], new)
                flash("Password changed.")
                return redirect(url_for("web.account"))
    return render_template("account.html")


@bp.route("/reservations/<int:reservation_id>/edit", methods=("GET", "POST"))
@login_required
def edit_reservation(reservation_id):
    reservation = models.get_reservation(reservation_id)
    if reservation is None:
        abort(404)
    if reservation["user_id"] != g.user["id"]:
        abort(403)
    if request.method == "POST":
        try:
            models.update_reservation(
                reservation_id,
                request.form.get("start_time"),
                request.form.get("end_time"),
                request.form.get("note"),
            )
            notify_reservation_event(
                "updated", models.reservation_snapshot(reservation_id)
            )
            flash("Reservation updated.")
            return redirect(url_for("web.my_reservations"))
        except (ValueError, models.OverlapError) as e:
            flash(str(e))
    return render_template("reservations/edit.html", reservation=reservation)


@bp.route("/reservations/<int:reservation_id>/cancel", methods=("POST",))
@login_required
def cancel_reservation(reservation_id):
    reservation = models.get_reservation(reservation_id)
    if reservation is None:
        abort(404)
    if reservation["user_id"] != g.user["id"]:
        abort(403)
    snapshot = models.reservation_snapshot(reservation_id)
    models.delete_reservation(reservation_id)
    notify_reservation_event("cancelled", snapshot)
    flash("Reservation cancelled.")
    return redirect(url_for("web.my_reservations"))
