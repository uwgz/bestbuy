"""
Database tables. Every page reads its content from here; nothing is hard-coded in the pages.

    Setting        store details (name, WhatsApp number, address …), one row per key
    Category       shop departments (Phones & Tablets, Cameras …)
    Product        what the shop sells; ProductPhoto holds its pictures in order
    Service        photography studio services
    PortfolioItem  photos on the Photography page
    HeroSlide      the home page slideshow
    User           people who can sign in to /admin
    Order          a sale; OrderItem holds what was sold
    StockMove      every change to stock: added, refill, sale, return, loss
    AuditLog       who did what, and when
"""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo
from decimal import ROUND_HALF_UP, Decimal

from flask import current_app, g

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
    "hours": "",              # made from the three below when they are set
    "hours_week": "",         # Monday to Friday, e.g. "08:00-19:00" ("" = closed)
    "hours_sat": "",
    "hours_sun": "",
    "map_url": "",
    "instagram": "",
    "facebook": "",
    "tiktok": "",
    "slide_seconds": "6",     # how long each home slide stays
}


def local_today() -> date:
    """Today in the shop's time zone (Kigali), not the server's."""
    return datetime.now(ZoneInfo(current_app.config.get("TIMEZONE", "Africa/Kigali"))).date()


def opening_hours_text(values):
    """ "Mon–Fri 08:00–19:00 · Sat 09:00–17:00 · Sun closed" from the three settings."""
    parts = []
    for key, label in (("hours_week", "Mon–Fri"), ("hours_sat", "Sat"), ("hours_sun", "Sun")):
        value = values.get(key) or ""
        parts.append(f"{label} {value.replace('-', '–')}" if value else f"{label} closed")
    return " · ".join(parts)


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
            if any(values.get(k) for k in ("hours_week", "hours_sat", "hours_sun")):
                values["hours"] = opening_hours_text(values)
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
    price = db.Column(db.Numeric(12, 2), nullable=False)        # selling price, before discount
    cost = db.Column(db.Numeric(12, 2), nullable=False, default=0)   # what one unit cost you (average of what you bought)
    discount = db.Column(db.Integer, nullable=False, default=0)  # % off; 0 = not on sale
    discount_until = db.Column(db.Date)                           # last day of the discount (empty = no end)
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
        """The discount counts only up to and including its last day."""
        return self.discount > 0 and (self.discount_until is None or self.discount_until >= local_today())

    @property
    def final_price(self):
        price = Decimal(self.price)
        if not self.on_sale:
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
    """A photo on the Photography page; `instagram` is the Instagram account of the person in it."""

    __tablename__ = "portfolio_items"

    id = db.Column(db.Integer, primary_key=True)
    photo = db.Column(db.String(500), nullable=False)
    title = db.Column(db.String(120), nullable=False, default="")
    instagram = db.Column(db.String(500), nullable=False, default="https://www.instagram.com/")

    @property
    def handle(self):
        """https://www.instagram.com/aline.rw/ → "@aline.rw" ("" when the link is not an account)."""
        name = self.instagram.split("instagram.com/", 1)[-1].strip("/").split("/")[0].split("?")[0]
        return f"@{name}" if name and "instagram.com/" in self.instagram else ""


class GearItem(TimestampMixin, OrderedMixin, db.Model):
    """Photography gear shown on the Photography page, priced in Canadian dollars."""

    __tablename__ = "gear_items"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    price_cad = db.Column(db.Numeric(12, 2), nullable=False)
    photo_links = db.Column(db.Text, nullable=False, default="")       # one link per line; the first is the cover

    @property
    def photos(self):
        return [line for line in self.photo_links.splitlines() if line.strip()]

    @property
    def image(self):
        return self.photos[0] if self.photos else ""


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


# ---------------------------------------------------------------- admin
ROLES = {
    "owner": ("Owner", "Everything, including employees and settings"),
    "manager": ("Manager", "Everything except employees and settings"),
    "employee": ("Employee", "Sell, refill and returns in Stock; giveaway codes"),
}


class User(TimestampMixin, db.Model):
    """Someone who can sign in to /admin. `role` says what they may do (see ROLES and admin.ACCESS)."""

    __tablename__ = "users"
    __table_args__ = (db.CheckConstraint("role IN ('owner', 'manager', 'employee')", name="ck_users_role"),)

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)   # stored lower-case
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(10), nullable=False, default="employee")
    is_active = db.Column(db.Boolean, nullable=False, default=True)                 # False = access removed
    last_login_at = db.Column(db.DateTime(timezone=True))
    failed_logins = db.Column(db.Integer, nullable=False, default=0)                # wrong passwords / answers in a row
    locked_until = db.Column(db.DateTime(timezone=True))                            # too many: wait until then

    questions = db.relationship("SecurityQuestion", order_by="SecurityQuestion.position",
                                cascade="all, delete-orphan", lazy="selectin")

    @property
    def role_label(self):
        return ROLES.get(self.role, ("Employee",))[0]

    def set_password(self, password):
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, password)

    @property
    def first_name(self):
        return self.name.split()[0] if self.name else "Owner"


def normal_answer(text):
    """Answers count the same whatever the capitals, spaces or end punctuation: " Kigali. " = "kigali"."""
    return " ".join((text or "").lower().split()).strip(".!?,;:'\"")


class SecurityQuestion(db.Model):
    """One of a user's five questions. The answer is kept only as a hash, like a password."""

    __tablename__ = "security_questions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    position = db.Column(db.Integer, nullable=False, default=0)
    question = db.Column(db.String(200), nullable=False)
    answer_hash = db.Column(db.String(256), nullable=False)

    def set_answer(self, answer):
        from werkzeug.security import generate_password_hash
        self.answer_hash = generate_password_hash(normal_answer(answer))

    def check_answer(self, answer):
        from werkzeug.security import check_password_hash
        return check_password_hash(self.answer_hash, normal_answer(answer))


class Order(TimestampMixin, db.Model):
    """A sale. Made with "Sell" in Stock (paid in the shop), or later from the website's cart (waiting)."""

    __tablename__ = "orders"
    __table_args__ = (db.CheckConstraint("status IN ('waiting', 'paid', 'cancelled')", name="ck_orders_status"),)

    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(16), nullable=False, default="paid", index=True)
    source = db.Column(db.String(16), nullable=False, default="shop")      # shop | website
    sold_on = db.Column(db.Date, nullable=False, index=True)               # the day of the sale
    customer = db.Column(db.String(120), nullable=False, default="")
    note = db.Column(db.String(300), nullable=False, default="")
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), index=True)

    items = db.relationship("OrderItem", back_populates="order", cascade="all, delete-orphan", lazy="selectin")

    @property
    def number(self):
        return f"#{self.id:05d}"

    @property
    def total(self):
        return sum((i.line_total for i in self.items), Decimal(0))


class OrderItem(db.Model):
    """One product in an order. Name, SKU and price are copied, so history stays right if the product changes."""

    __tablename__ = "order_items"
    __table_args__ = (db.CheckConstraint("qty > 0", name="ck_order_items_qty"),
                      db.CheckConstraint("unit_price >= 0", name="ck_order_items_price"))

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="SET NULL"), index=True)
    product_name = db.Column(db.String(40), nullable=False)    # the short name at the time
    sku = db.Column(db.String(16), nullable=False, default="")
    qty = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(12, 2), nullable=False)
    unit_cost = db.Column(db.Numeric(12, 2), nullable=False, default=0)   # what it cost you: for profit

    order = db.relationship("Order", back_populates="items")

    @property
    def line_total(self):
        return Decimal(self.unit_price) * self.qty

    @property
    def line_cost(self):
        return Decimal(self.unit_cost or 0) * self.qty


class StockMove(db.Model):
    """Every change to a product's units, so stock can be followed and counted:
         added   a new product's first units (stock bought)      qty > 0, amount = what you paid
         refill  more units bought                               qty > 0, amount = what you paid
         sale    sold with "Sell"                                qty < 0, amount = money received
         return  a customer brought it back (back on the shelf)  qty > 0, amount = money given back
         loss    damaged, lost or stolen (written off)           qty < 0, amount = what it had cost you"""

    __tablename__ = "stock_moves"
    __table_args__ = (db.CheckConstraint("kind IN ('added', 'refill', 'sale', 'return', 'loss', 'giveaway')", name="ck_stock_moves_kind"),)

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="SET NULL"), index=True)
    product_name = db.Column(db.String(40), nullable=False)       # short name at the time
    sku = db.Column(db.String(16), nullable=False, default="")
    kind = db.Column(db.String(10), nullable=False, index=True)
    qty = db.Column(db.Integer, nullable=False)                    # + into stock, - out of stock
    unit_cost = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    reason = db.Column(db.String(300), nullable=False, default="")
    happened_on = db.Column(db.Date, nullable=False, index=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id", ondelete="SET NULL"))
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)


# ---------------------------------------------------------------- giveaways
CODE_LETTERS = "ABCDEFGHJKMNPQRSTUVWXYZ"      # no I, L, O: they look like 1 and 0
CODE_DIGITS = "23456789"                      # no 0 and 1
CODE_CHARS = CODE_LETTERS + CODE_DIGITS


def new_code():
    """12 characters, letters mixed with numbers, e.g. "K7Q4MZ9XA2PD" (shown as K7Q-4MZ-9XA-2PD)."""
    import secrets
    while True:
        code = "".join(secrets.choice(CODE_CHARS) for _ in range(12))
        if any(c in CODE_LETTERS for c in code) and sum(c in CODE_DIGITS for c in code) >= 3:
            return code


def clean_code(value):
    """What the customer reads out ("k7q 4mz-9xa 2pd") → "K7Q4MZ9XA2PD"."""
    return "".join(c for c in (value or "").upper() if c.isalnum())[:12]


def pretty_code(code):
    return "-".join(code[i:i + 3] for i in range(0, len(code), 3))


class Giveaway(TimestampMixin, db.Model):
    """A prize (one product or an amount of money) won by random visitors of the website.
    Each visitor is drawn once; one in `chance` visitors wins, until `winners` codes are given out."""

    __tablename__ = "giveaways"
    __table_args__ = (
        db.CheckConstraint("prize IN ('product', 'money')", name="ck_giveaways_prize"),
        db.CheckConstraint("winners > 0 AND chance > 0", name="ck_giveaways_numbers"),
    )

    id = db.Column(db.Integer, primary_key=True)
    prize = db.Column(db.String(8), nullable=False)                        # product | money
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="SET NULL"))
    product_name = db.Column(db.String(200), nullable=False, default="")   # the name the winner sees
    amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)       # money prize
    winners = db.Column(db.Integer, nullable=False)                        # how many codes to give out
    chance = db.Column(db.Integer, nullable=False)                         # 1 in this many visitors wins
    starts_on = db.Column(db.Date, nullable=False)
    ends_on = db.Column(db.Date, nullable=False)                           # last day
    is_active = db.Column(db.Boolean, nullable=False, default=True)        # False = stopped early
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))

    product = db.relationship("Product")
    codes = db.relationship("GiveawayCode", back_populates="giveaway", order_by="GiveawayCode.id.desc()",
                            cascade="all, delete-orphan", lazy="selectin")

    @property
    def given(self):
        return len(self.codes)

    @property
    def claimed(self):
        return sum(1 for c in self.codes if c.claimed_at)

    @property
    def status(self):
        """live, upcoming, full (every code given), ended or stopped."""
        day = local_today()
        if not self.is_active:
            return "stopped"
        if day > self.ends_on:
            return "ended"
        if self.given >= self.winners:
            return "full"
        return "upcoming" if day < self.starts_on else "live"

    @classmethod
    def live(cls):
        day = local_today()
        rows = cls.query.filter(cls.is_active.is_(True), cls.starts_on <= day, cls.ends_on >= day).order_by(cls.id).all()
        return [r for r in rows if r.given < r.winners]


class GiveawayCode(db.Model):
    """A winning code shown to one visitor. `claimed_at` is set when the prize is handed over."""

    __tablename__ = "giveaway_codes"

    id = db.Column(db.Integer, primary_key=True)
    giveaway_id = db.Column(db.Integer, db.ForeignKey("giveaways.id", ondelete="CASCADE"), nullable=False, index=True)
    code = db.Column(db.String(12), unique=True, nullable=False)
    visitor = db.Column(db.String(64), nullable=False, default="", index=True)   # hashed address: one win each
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    claimed_at = db.Column(db.DateTime(timezone=True))
    claimed_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    customer = db.Column(db.String(120), nullable=False, default="")     # who collected it
    value = db.Column(db.Numeric(12, 2), nullable=False, default=0)      # what it cost the shop

    giveaway = db.relationship("Giveaway", back_populates="codes")

    @property
    def pretty(self):
        return pretty_code(self.code)


class AuditLog(db.Model):
    """Who did what, and when. Written by bestbuy.admin.audit()."""

    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action = db.Column(db.String(64), nullable=False)
    details = db.Column(db.Text, default="")
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False, index=True)
