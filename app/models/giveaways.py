"""Giveaways: random winners among visitors during a period the owner starts from the admin.

How a winner is chosen: when a giveaway starts, one secret moment is picked at random inside the
period for each prize. The first visitor who opens a page after that moment wins it. The server
decides; a winner gets a unique code that staff check in the admin before handing over the prize.
"""
import secrets
from datetime import datetime, timedelta, timezone

from ..db import execute, get_db, query
from . import settings

CLAIM_DAYS = 3
DURATIONS = [(30, "30 minutes"), (60, "1 hour"), (180, "3 hours"), (360, "6 hours"), (720, "12 hours"),
             (1440, "24 hours"), (4320, "3 days"), (10080, "7 days")]
MAX_PRIZES = 20
_CODE_CHARS = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"   # no 0/O, 1/I/L: easy to read out on the phone


def now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse(text):
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) if text else None


def new_code():
    pick = lambda n: "".join(secrets.choice(_CODE_CHARS) for _ in range(n))
    return f"VE-{pick(4)}-{pick(4)}"


def normalise_code(text):
    raw = "".join(ch for ch in (text or "").upper() if ch.isalnum())
    if raw.startswith("VE"):
        raw = raw[2:]
    return f"VE-{raw[:4]}-{raw[4:8]}" if len(raw) == 8 else None


# ---------------------------------------------------------------- the running giveaway
def running():
    """The giveaway happening now, or None. Uses the store settings (already read for every page),
    so pages cost no extra database work when nothing is running."""
    until = settings.business().get("giveaway_until")
    if not until or parse(until) <= now():
        return None
    return query("SELECT * FROM giveaways WHERE ends_at > ? AND stopped_at IS NULL AND is_test = 0 ORDER BY id DESC LIMIT 1",
                 (iso(now()),), one=True)


# ---------------------------------------------------------------- testing ("Try it yourself")
TEST_MINUTES = 30


def start_test(user_id=None):
    """A private test: one prize, winnable straight away, only by whoever opens its link. Real
    visitors never see it and it doesn't touch a real giveaway that may be running."""
    token = secrets.token_urlsafe(16)
    t = now()
    gid = execute("INSERT INTO giveaways (prize, prize_kind, prizes, starts_at, ends_at, created_by, is_test, test_token) "
                  "VALUES (?, 'test', 1, ?, ?, ?, 1, ?)",
                  ("Test prize", iso(t), iso(t + timedelta(minutes=TEST_MINUTES)), user_id, token))
    execute("INSERT INTO giveaway_wins (giveaway_id, win_at) VALUES (?, ?)", (gid, iso(t)))
    return token


def test_giveaway(token):
    """The open test giveaway for a link, or None (unknown or older than 30 minutes)."""
    if not token:
        return None
    return query("SELECT * FROM giveaways WHERE is_test = 1 AND test_token = ? AND ends_at > ?",
                 (token, iso(now())), one=True)


def prize_for(kind, product_id=None, amount=None):
    """Check the chosen prize and return (text shown to winners, product_id, amount_cents).
    Only devices sold in the shop, or an amount of money in the store currency."""
    from ..helpers import money
    from . import products
    if kind == "device":
        p = products.get(product_id) if product_id else None
        if not p:
            raise ValueError("Choose a device from the shop.")
        return p["name"], p["id"], None
    if kind == "money":
        if not amount or amount <= 0:
            raise ValueError("Enter the amount of money to give.")
        return money(amount / 100), None, amount
    raise ValueError("Choose a device or money as the prize.")


def start(prize, prizes, minutes, user_id=None, kind="device", product_id=None, amount_cents=None):
    if running():
        raise ValueError("A giveaway is already running. Stop it first.")
    start_at, end_at = now(), now() + timedelta(minutes=minutes)
    gid = execute("INSERT INTO giveaways (prize, prize_kind, product_id, amount_cents, prizes, starts_at, ends_at, created_by) "
                  "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                  (prize, kind, product_id, amount_cents, prizes, iso(start_at), iso(end_at), user_id))
    rng = secrets.SystemRandom()
    span = int((end_at - start_at).total_seconds())
    for s in sorted(rng.randrange(0, max(span, 1)) for _ in range(prizes)):
        execute("INSERT INTO giveaway_wins (giveaway_id, win_at) VALUES (?, ?)", (gid, iso(start_at + timedelta(seconds=s))))
    settings.save({"giveaway_until": iso(end_at)})
    return gid


def stop():
    g = running()
    if g:
        execute("UPDATE giveaways SET stopped_at = ? WHERE id = ?", (iso(now()), g["id"]))
    settings.save({"giveaway_until": ""})


def try_win(visitor, test_token=None):
    """Called when a visitor opens a page during a giveaway. Returns their win (new or earlier) or None.
    With test_token: the private test giveaway from "Try it yourself" instead of the real one."""
    g = test_giveaway(test_token) if test_token else running()
    if not g or not visitor:
        return None
    mine = query("SELECT * FROM giveaway_wins WHERE giveaway_id = ? AND visitor = ?", (g["id"], visitor), one=True)
    if mine:
        return describe(mine, g)
    t = now()
    code = new_code()
    # one statement, so two visitors arriving together can never both take the same prize
    cur = get_db().execute(
        "UPDATE giveaway_wins SET code = ?, visitor = ?, won_at = ?, claim_by = ? "
        "WHERE id = (SELECT id FROM giveaway_wins WHERE giveaway_id = ? AND code IS NULL AND win_at <= ? "
        "ORDER BY win_at LIMIT 1) AND code IS NULL",
        (code, visitor, iso(t), iso(t + timedelta(days=CLAIM_DAYS)), g["id"], iso(t)))
    get_db().commit()
    if not cur.rowcount:
        return None
    return describe(find(code), g)


def find(code):
    code = normalise_code(code)
    return query("SELECT * FROM giveaway_wins WHERE code = ?", (code,), one=True) if code else None


def describe(win, giveaway=None):
    """A win shaped for pages: prize, status and dates."""
    giveaway = giveaway or query("SELECT * FROM giveaways WHERE id = ?", (win["giveaway_id"],), one=True)
    w = dict(win)
    w["prize"] = giveaway["prize"]
    w["prize_kind"] = giveaway["prize_kind"]
    w["product_id"] = giveaway["product_id"]
    w["is_test"] = bool(giveaway["is_test"])
    if w["collected_at"]:
        w["status"] = "collected"
    elif w["claim_by"] and parse(w["claim_by"]) < now():
        w["status"] = "expired"
    elif w["code"]:
        w["status"] = "waiting"
    else:
        w["status"] = "not won"
    return w


def mark_collected(code, name, phone, user_id):
    win = find(code)
    if not win:
        raise ValueError("That code doesn't exist.")
    w = describe(win)
    if w["status"] == "collected":
        raise ValueError("This prize has already been collected.")
    if w["status"] == "expired":
        raise ValueError("This code expired — the 3 days to collect have passed.")
    cur = get_db().execute(
        "UPDATE giveaway_wins SET collected_at = ?, collected_name = ?, collected_phone = ?, collected_by = ? "
        "WHERE id = ? AND collected_at IS NULL", (iso(now()), name, phone, user_id, win["id"]))
    get_db().commit()
    if not cur.rowcount:
        raise ValueError("This prize has already been collected.")


def history(limit=30):
    """Recent giveaways with their prizes, newest first."""
    out = []
    for g in query("SELECT * FROM giveaways ORDER BY id DESC LIMIT ?", (limit,)):
        wins = [describe(w, g) for w in query("SELECT * FROM giveaway_wins WHERE giveaway_id = ? ORDER BY win_at", (g["id"],))]
        g = dict(g)
        g["wins"] = wins
        g["is_test"] = bool(g["is_test"])
        g["ended"] = bool(g["stopped_at"]) or parse(g["ends_at"]) <= now()
        out.append(g)
    return out
