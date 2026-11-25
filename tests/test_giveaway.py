"""Giveaway: random winners, unique codes, checking and handing over in the admin."""
from datetime import timedelta

import pytest

from app.models import giveaways


DEVICE = "Noise-Cancelling Headphones"     # a starter product sold in the shop


def _device_id(owner):
    with owner.application.app_context():
        from app.db import query
        return str(query("SELECT id FROM products WHERE name = ?", (DEVICE,), one=True)["id"])


def _start(owner, prize=DEVICE, prizes="1", minutes="60", amount=None):
    """Start a giveaway: a shop device (default) or, with amount, money."""
    data = {"prizes": prizes, "minutes": minutes}
    if amount:
        data.update(prize_kind="money", amount=amount)
    else:
        data.update(prize_kind="device", product_id=_device_id(owner))
    return owner.post("/altar/giveaway", data=data, follow_redirects=True)


def _due_now(app):
    """Move every winning moment into the past, so the next visitor wins."""
    with app.app_context():
        from app.db import execute
        execute("UPDATE giveaway_wins SET win_at = ? WHERE code IS NULL", (giveaways.iso(giveaways.now() - timedelta(seconds=5)),))


def _visitor(app):
    return app.test_client()


def test_admin_starts_giveaway_and_page_asks(app, owner):
    page = _start(owner).get_data(as_text=True)
    assert "Running now" in page and f"1 × {DEVICE}" in page
    home = _visitor(app).get("/").get_data(as_text=True)
    assert 'data-giveaway="/giveaway/check"' in home
    # a second start is refused while one runs
    assert "already running" in _start(owner).get_data(as_text=True)


def test_nobody_wins_before_the_secret_moment(app, owner):
    _start(owner, minutes="1440")
    with app.app_context():
        from app.db import execute
        execute("UPDATE giveaway_wins SET win_at = ?", (giveaways.iso(giveaways.now() + timedelta(hours=2)),))
    r = _visitor(app).post("/giveaway/check").get_json()
    assert r == {"won": False, "live": True}


def test_first_visitor_after_the_moment_wins_once(app, owner):
    _start(owner)
    _due_now(app)
    first, second = _visitor(app), _visitor(app)
    win = first.post("/giveaway/check").get_json()
    assert win["won"] and win["prize"] == DEVICE and win["code"].startswith("VE-") and len(win["code"]) == 12
    assert win["link"] == "/shop?q=Noise-Cancelling+Headphones"           # the shop, searching for the device
    shop = first.get(win["link"]).get_data(as_text=True)
    assert 'value="Noise-Cancelling Headphones"' in shop                   # name already in the search bar
    assert shop.index("Noise-Cancelling Headphones</") < shop.index("<footer")  # and the device is listed
    assert "wa.me" in win["whatsapp"] and win["code"] in win["whatsapp"]
    assert second.post("/giveaway/check").get_json()["won"] is False      # only one prize
    again = first.post("/giveaway/check").get_json()                      # the winner sees the same win again
    assert again["code"] == win["code"]


def test_robots_and_signed_in_staff_never_win(app, owner):
    _start(owner)
    _due_now(app)
    bot = _visitor(app).post("/giveaway/check", headers={"User-Agent": "Googlebot/2.1"}).get_json()
    assert bot["won"] is False
    assert owner.post("/giveaway/check").get_json()["won"] is False
    assert _visitor(app).post("/giveaway/check").get_json()["won"] is True   # the prize was still there


def test_check_and_hand_over_once(app, owner):
    _start(owner, amount="50")
    _due_now(app)
    code = _visitor(app).post("/giveaway/check").get_json()["code"]
    page = owner.get(f"/altar/giveaway?code={code.lower().replace('-', ' ')}").get_data(as_text=True)   # typed loosely
    assert "Valid — $50.00" in page
    done = owner.post("/altar/giveaway/collect", data={"code": code, "name": "Eric M", "phone": "0788"}, follow_redirects=True)
    assert "handed over to Eric M" in done.get_data(as_text=True)
    page = owner.get(f"/altar/giveaway?code={code}").get_data(as_text=True)
    assert "Already collected" in page and "Eric M" in page
    twice = owner.post("/altar/giveaway/collect", data={"code": code, "name": "Someone else"}, follow_redirects=True)
    assert "already been collected" in twice.get_data(as_text=True)


def test_unknown_and_expired_codes(app, owner):
    assert "Not a valid code" in owner.get("/altar/giveaway?code=VE-AAAA-BBBB").get_data(as_text=True)
    _start(owner)
    _due_now(app)
    code = _visitor(app).post("/giveaway/check").get_json()["code"]
    with app.app_context():
        from app.db import execute
        execute("UPDATE giveaway_wins SET claim_by = ?", (giveaways.iso(giveaways.now() - timedelta(minutes=1)),))
    assert "Expired" in owner.get(f"/altar/giveaway?code={code}").get_data(as_text=True)
    r = owner.post("/altar/giveaway/collect", data={"code": code, "name": "Late"}, follow_redirects=True)
    assert "expired" in r.get_data(as_text=True)


def test_stop_ends_it_and_store_details_cannot_restart_it(app, owner):
    _start(owner)
    owner.post("/altar/giveaway/stop")
    assert 'data-giveaway' not in _visitor(app).get("/").get_data(as_text=True)
    assert _visitor(app).post("/giveaway/check").get_json()["won"] is False
    # the hidden end time can't be set through the Store details form
    owner.post("/altar/settings", data={"name": "Vision Electronics", "giveaway_until": "2999-01-01T00:00:00Z"})
    assert 'data-giveaway' not in _visitor(app).get("/").get_data(as_text=True)


def test_codes_are_readable_and_unique():
    codes = {giveaways.new_code() for _ in range(2000)}
    assert len(codes) == 2000
    assert not any(ch in "".join(codes) for ch in "01OIL")
    assert giveaways.normalise_code(" ve 7kq4 92mx ") == "VE-7KQ4-92MX"


def test_rules_page(client):
    html = client.get("/giveaway-rules").get_data(as_text=True)
    assert "3 days" in html and "No purchase needed" in html


def test_giveaway_on_turso(tmp_path):
    from app import create_app
    from fakes import FakeBlob, FakeTurso
    turso = FakeTurso(tmp_path / "remote.db")
    app = create_app("testing", INSTANCE_DIR=tmp_path / "inst", TURSO_DATABASE_URL=turso.url,
                     TURSO_AUTH_TOKEN=FakeTurso.TOKEN, MEDIA_STORAGE="blob", BLOB_CLIENT=FakeBlob())
    try:
        with app.test_request_context():
            giveaways.start("Speaker", 2, 60, kind="money", amount_cents=5000)
            from app.db import execute
            execute("UPDATE giveaway_wins SET win_at = ?", (giveaways.iso(giveaways.now() - timedelta(seconds=1)),))
            a, b, c = giveaways.try_win("a"), giveaways.try_win("b"), giveaways.try_win("c")
            assert a and b and a["code"] != b["code"] and c is None
    finally:
        turso.stop()


# ---------- "Try it yourself" ----------
def _test_link(owner):
    r = owner.post("/altar/giveaway/test")
    page = owner.get(r.headers["Location"]).get_data(as_text=True)
    import re
    return re.search(r'value="(http://localhost/giveaway/try/[^"]+)"', page).group(1).replace("http://localhost", "")


def test_owner_can_try_it_and_check_the_test_code(app, owner):
    link = _test_link(owner)
    owner.get(link)                                              # the owner opens it in the same browser
    assert 'data-giveaway' in owner.get("/").get_data(as_text=True)
    win = owner.post("/giveaway/check").get_json()
    assert win["won"] and win["test"] and win["prize"] == "Test prize"
    page = owner.get(f"/altar/giveaway?code={win['code']}").get_data(as_text=True)
    assert "TEST CODE" in page and "Valid — Test prize" in page


def test_tests_are_private_and_dont_disturb_a_real_giveaway(app, owner):
    _start(owner)
    link = _test_link(owner)
    assert _visitor(app).post("/giveaway/check").get_json()["won"] is False   # a stranger can't take the test prize
    phone = _visitor(app)
    phone.get(link)
    assert phone.post("/giveaway/check").get_json()["prize"] == "Test prize"
    assert "Running now" in owner.get("/altar/giveaway").get_data(as_text=True)  # the real one still runs
    _due_now(app)
    assert _visitor(app).post("/giveaway/check").get_json()["prize"] == DEVICE


def test_old_test_links_stop_working(app, owner):
    link = _test_link(owner)
    with app.app_context():
        from app.db import execute
        execute("UPDATE giveaways SET ends_at = ? WHERE is_test = 1", (giveaways.iso(giveaways.now() - timedelta(minutes=1)),))
    assert _visitor(app).get(link).status_code == 410



def test_prize_must_be_a_shop_device_or_money(app, owner):
    r = owner.post("/altar/giveaway", data={"prize_kind": "device", "product_id": "99999", "prizes": "1", "minutes": "60"},
                   follow_redirects=True).get_data(as_text=True)
    assert "Choose a device from the shop" in r and "Running now" not in r
    r = owner.post("/altar/giveaway", data={"prize_kind": "money", "amount": "", "prizes": "1", "minutes": "60"},
                   follow_redirects=True).get_data(as_text=True)
    assert "Enter the amount" in r
    owner.post("/altar/settings", data={"currency": "RWF"})
    assert "1 × RWF 50,000" in _start(owner, amount="50000").get_data(as_text=True)


def test_rules_have_no_staff_exclusion(client):
    assert "can't take part" not in client.get("/giveaway-rules").get_data(as_text=True)


def test_no_browser_dialogs_in_admin_scripts():
    from pathlib import Path
    js = (Path(__file__).parents[1] / "public/static/js/admin.js").read_text()
    for native in ("confirm(", "alert(", "prompt("):
        assert f" {native}" not in js and f"!{native}" not in js and f"({native}" not in js
