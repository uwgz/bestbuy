"""Photography: services, portfolio and booking."""
from flask import flash, redirect, render_template, request, url_for

from . import bp
from ...models import gear, inbox, portfolio, services


@bp.route("/photography")
def services_page():
    svc = services.list_services()
    work = portfolio.recent_work(12)
    return render_template("studio/services.html", services=svc, gear=gear.list_gear(),
                           work=work, work_cats=sorted({w["category"] for w in work}))


@bp.route("/portfolio")
def portfolio_page():
    items = portfolio.list_items()
    cats = sorted({i["category"] for i in items})
    return render_template("studio/portfolio.html", portfolio=items, cats=cats)


@bp.route("/book", methods=["GET", "POST"])
def book():
    options = services.list_services()
    if request.method == "POST":
        f = request.form
        fields = {k: f.get(k, "").strip() for k in ("name", "email", "phone", "service", "date", "notes")}
        if not all(fields[k] for k in ("name", "email", "service", "date")):
            flash("Please fill in your name, email, service and preferred date.", "error")
            return render_template("studio/book.html", services=options, form=f)
        inbox.add_booking(**fields)
        flash("Booking request sent! We'll confirm your appointment within 24 hours.", "success")
        return redirect(url_for("studio.book"))
    return render_template("studio/book.html", services=options, form={"service": request.args.get("service", "")})
