"""
Database tables. Every page reads its content from here; nothing is hard-coded in the pages.

    Setting        store details (name, WhatsApp number, address …), one row per key
    Category       shop departments (Phones & Tablets, Cameras …)
    Product        what the shop sells; ProductPhoto holds its pictures in order
    Service        photography studio services
    PortfolioItem  photos on the Photography page
    HeroSlide      the home page slideshow
"""
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from flask import g

from .extensions import db


def utcnow():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- shared columns
class TimestampMixin:
    """When a row was created and last changed."""

    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class OrderedMixin:
    """Rows shown in a chosen order, and hidden without being deleted."""

    position = db.Column(db.Integer, nullable=False, default=0, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)


# ---------------------------------------------------------------- store details
STORE_DEFAULTS = {
    "name": "Best Buy 250",
    "tagline": "Electronics and photography, all in one place.",
    "currency": "RWF",        # shown before every price
    "decimals": "0",          # RWF has no cents; 2 for CAD, USD …
    "whatsapp": "",           # digits with country code, e.g. 250788123456
    "phone": "",
    "email": "",
    "address": "",
    "hours": "",
    "map_url": "",
    "instagram": "",
    "facebook": "",
    "tiktok": "",
    "slide_seconds": "6",     # how long each home slide stays
}


class Setting(db.Model):
    """One store detail, e.g. key="whatsapp", value="250788123456". Empty values are hidden on the site."""

    __tablename__ = "settings"

    key = db.Column(db.String(64), primary_key=True)
    value = db.Column(db.Text, nullable=False, default="")
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    @staticmethod
    def store():
        """All store details as a dict (defaults filled in), read once per request."""
        if "store" not in g:
            values: dict = dict(STORE_DEFAULTS)
            values.update({s.key: s.value for s in Setting.query.all()})
            values["decimals"] = int(values.get("decimals") or 0)
            values["slide_seconds"] = int(values.get("slide_seconds") or 6)
            g.store = values
        return g.store


# ---------------------------------------------------------------- shop
class Category(db.Model):
    """A shop department. `key` appears in addresses: /shop?category=cameras."""

    __tablename__ = "categories"

    key = db.Column(db.String(32), primary_key=True)
    label = db.Column(db.String(64), nullable=False)
    icon = db.Column(db.String(32), nullable=False, default="package")
    sku_code = db.Column(db.String(8), nullable=False)          # LAP → SKU LAP-0007
    position = db.Column(db.Integer, nullable=False, default=0)

    products = db.relationship("Product", back_populates="category_info")

    @staticmethod
    def as_dict():
        """{key: (label, icon, sku_code)} in display order, read once per request."""
        if "categories" not in g:
            g.categories = {c.key: (c.label, c.icon, c.sku_code)
                            for c in Category.query.order_by(Category.position, Category.label)}
        return g.categories


class Product(TimestampMixin, OrderedMixin, db.Model):
    """Something the shop sells. name: up to 20 words (product page); short: up to 4 words (cards, cart)."""

    __tablename__ = "products"
    __table_args__ = (
        db.CheckConstraint("price >= 0", name="ck_products_price"),
        db.CheckConstraint("discount >= 0 AND discount <= 90", name="ck_products_discount"),
        db.CheckConstraint("stock >= 0", name="ck_products_stock"),
    )

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160), unique=True, nullable=False, index=True)
    category = db.Column(db.String(32), db.ForeignKey("categories.key", ondelete="RESTRICT"), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    short = db.Column(db.String(40), nullable=False)
    price = db.Column(db.Numeric(12, 2), nullable=False)        # before discount
    discount = db.Column(db.Integer, nullable=False, default=0)  # % off; 0 = not on sale
    badge = db.Column(db.String(32), nullable=False, default="")  # New, Best seller, Deal …
    stock = db.Column(db.Integer, nullable=False, default=0)      # units in the shop
    description = db.Column(db.Text, nullable=False, default="")  # "- " lines become bullet points

    category_info = db.relationship("Category", back_populates="products", lazy="joined")
    photo_rows = db.relationship("ProductPhoto", back_populates="product", order_by="ProductPhoto.position",
                                 cascade="all, delete-orphan", lazy="selectin")

    # ---- what the pages show
    @property
    def sku(self):
        return f"{self.category_info.sku_code}-{self.id:04d}"

    @property
    def category_label(self):
        return self.category_info.label

    @property
    def icon(self):
        return self.category_info.icon

    @property
    def photos(self):
        return [p.url for p in self.photo_rows]

    @property
    def image(self):
        return self.photo_rows[0].url if self.photo_rows else ""

    @property
    def on_sale(self):
        return self.discount > 0

    @property
    def final_price(self):
        price = Decimal(self.price)
        if not self.discount:
            return price
        return (price * (100 - self.discount) / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def save(self):
        return Decimal(self.price) - self.final_price

    def __repr__(self):
        return f"<Product {self.slug}>"


class ProductPhoto(db.Model):
    """One picture of a product; the lowest position is the cover."""

    __tablename__ = "product_photos"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    url = db.Column(db.String(500), nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0)

    product = db.relationship("Product", back_populates="photo_rows")


# ---------------------------------------------------------------- photography
class Service(TimestampMixin, OrderedMixin, db.Model):
    """A studio service with its "from" price."""

    __tablename__ = "services"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    icon = db.Column(db.String(32), nullable=False, default="camera")
    price_from = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    duration = db.Column(db.String(40), nullable=False, default="")
    description = db.Column(db.Text, nullable=False, default="")
    photo = db.Column(db.String(500), nullable=False, default="")


class PortfolioItem(TimestampMixin, OrderedMixin, db.Model):
    """A photo on the Photography page; `instagram` is where its Instagram button goes."""

    __tablename__ = "portfolio_items"

    id = db.Column(db.Integer, primary_key=True)
    photo = db.Column(db.String(500), nullable=False)
    title = db.Column(db.String(120), nullable=False, default="")
    instagram = db.Column(db.String(500), nullable=False, default="https://www.instagram.com/")


# ---------------------------------------------------------------- home page
class HeroSlide(TimestampMixin, OrderedMixin, db.Model):
    """One photo of the home slideshow. link: a page ("/shop?category=phones") or "whatsapp" for a booking chat."""

    __tablename__ = "hero_slides"

    id = db.Column(db.Integer, primary_key=True)
    photo = db.Column(db.String(500), nullable=False)
    label = db.Column(db.String(40), nullable=False)        # bold word: "Phones"
    text = db.Column(db.String(160), nullable=False)        # "The new iPhone 17 Pro is here."
    button = db.Column(db.String(24), nullable=False, default="Shop now")
    link = db.Column(db.String(300), nullable=False, default="/shop")
