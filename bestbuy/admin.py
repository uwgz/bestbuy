"""
Admin pages (/admin). For now this is the DESIGN only: top bar, sidebar and page layout.
Nothing here changes data, and there is no login yet; both come in the next step.
"""
from flask import Blueprint, render_template

from .models import Category, Product

bp = Blueprint("admin", __name__, url_prefix="/admin")

LOW_STOCK = 2   # this many units or fewer counts as "running low"


@bp.context_processor
def _layout():
    """What the top bar and sidebar show on every admin page."""
    low = Product.query.filter(Product.stock <= LOW_STOCK).count()
    return {"low_stock": low, "new_orders": 0, "admin_user": "Owner"}


def _page(title, subtitle, page_icon, button=None):
    return render_template("admin/page.html", title=title, subtitle=subtitle, page_icon=page_icon, button=button)


@bp.route("/")
def dashboard():
    return _page("Dashboard", "Your store at a glance.", "layout")


@bp.route("/stock")
def stock():
    items = Product.query.order_by(Product.position, Product.id).all()
    counts = {key: sum(p.category == key for p in items) for key in Category.as_dict()}
    return render_template("admin/stock.html", items=items, counts=counts)


@bp.route("/orders")
def orders():
    return _page("Orders", "Sales made in the shop and orders sent from the website.", "receipt")


@bp.route("/giveaways")
def giveaways():
    return _page("Giveaways", "A random visitor wins a prize; check their code here.", "gift", button="Start a giveaway")


@bp.route("/settings")
def settings():
    return _page("Settings", "Store details, WhatsApp number, and your account.", "settings")
