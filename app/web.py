from flask import (
    Blueprint, abort, flash, g, redirect, render_template, request, url_for
)

from . import models
from .auth import login_required

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
        models.create_reservation(
            widget_id,
            g.user["id"],
            request.form.get("start_time"),
            request.form.get("end_time"),
            request.form.get("note"),
        )
        flash("Reservation confirmed.")
    except (ValueError, models.OverlapError) as e:
        flash(str(e))
    return redirect(url_for("web.widget_detail", widget_id=widget_id))


@bp.route("/reservations")
@login_required
def my_reservations():
    reservations = models.list_reservations_for_user(g.user["id"])
    return render_template("reservations/list.html", reservations=reservations)


@bp.route("/reservations/<int:reservation_id>/cancel", methods=("POST",))
@login_required
def cancel_reservation(reservation_id):
    reservation = models.get_reservation(reservation_id)
    if reservation is None:
        abort(404)
    if reservation["user_id"] != g.user["id"]:
        abort(403)
    models.delete_reservation(reservation_id)
    flash("Reservation cancelled.")
    return redirect(url_for("web.my_reservations"))
