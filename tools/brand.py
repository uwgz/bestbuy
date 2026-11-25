"""
Build every logo file — and the logo animation — from one drawing.

    python tools/brand.py      # writes public/static/img/brand/*, favicon.svg, apple-touch-icon.png
                               # and the animated logos in app/templates/partials/

The mark is the Vision Electronics emblem (a licensed design; keep the original purchase file and
licence outside this repository). tools/emblem.json holds it as vector outlines: the body (the
rounded E) and the two small lines on the right, which light up red one after the other in the
animation — like a signal.

SVG files need only Python; the PNG files are rendered with Playwright + Chrome (dev machines only).
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "public" / "static"
BRAND = STATIC / "img" / "brand"
PARTIALS = ROOT / "app" / "templates" / "partials"

E = json.loads((Path(__file__).with_name("emblem.json")).read_text())
W, H = E["width"], E["height"]
RED = "#ff3b30"

TIGHT = f"0 0 {W} {H}"                                # just the emblem
SIDE = round(max(W, H) * 1.12, 2)                    # a little space around the emblem
VIEW = f"{(W - SIDE) / 2:.2f} {(H - SIDE) / 2:.2f} {SIDE} {SIDE}"   # square box around it
SIGNAL_SECONDS = 2.4                                  # one cycle of the red signal


def mark(color="#000"):
    return f'<path d="{E["body"]}{E["line1"]}{E["line2"]}" fill="{color}"/>'


def svg(inner, view=VIEW, extra=""):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view}"{extra}>\n{inner}\n</svg>\n'


def round_icon(bg="#000", fg="#fff", style=""):
    """The emblem in a circle (app icon, favicon)."""
    scale = 58 / SIDE
    inner = (f'<circle cx="50" cy="50" r="50" fill="{bg}" class="bg"/>\n'
             f'<g transform="translate(50 50) scale({scale:.5f}) translate({-W / 2:.2f} {-H / 2:.2f})" class="fg">{mark(fg)}</g>')
    return svg(style + inner, view="0 0 100 100")


def animated(cls, view=TIGHT, label=""):
    """The emblem; its two small lines light up red one after the other, then fade back — a signal.
    Colour follows the page (currentColor). People who turn off motion see the still emblem."""
    def line(d, start):
        # fade to red, hold, fade back; the second line follows the first
        k = ";".join(f"{v:g}" for v in (0, start, round(start + .12, 2), round(start + .34, 2), round(start + .46, 2), 1))
        return (f'<path d="{d}" fill="currentColor"><animate attributeName="fill" dur="{SIGNAL_SECONDS}s" '
                f'repeatCount="indefinite" keyTimes="{k}" values="currentColor;currentColor;{RED};{RED};currentColor;currentColor"/></path>')
    aria = f' role="img" aria-label="{label}"' if label else ' aria-hidden="true"'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view}" class="{cls}"{aria}>\n'
            f'<path d="{E["body"]}" fill="currentColor"/>\n{line(E["line1"], .08)}\n{line(E["line2"], .26)}\n</svg>\n')


# ------------------------------------------------------------------ writing files
def write_svgs():
    BRAND.mkdir(parents=True, exist_ok=True)
    (BRAND / "logo-mark.svg").write_text(svg(mark("#000")))
    (BRAND / "logo-mark-white.svg").write_text(svg(mark("#fff")))
    (BRAND / "app-icon.svg").write_text(round_icon())
    style = "<style>.bg{fill:#000}.fg path{fill:#fff}@media (prefers-color-scheme:dark){.bg{fill:#fff}.fg path{fill:#000}}</style>\n"
    (STATIC / "favicon.svg").write_text(round_icon(style=style))
    (PARTIALS / "loader_mark.svg").write_text(animated("loader-mark", VIEW))
    (PARTIALS / "logo_anim.svg").write_text(animated("logo-mark", TIGHT, "Vision Electronics"))
    (PARTIALS / "error_mark.svg").write_text(animated("error-mark", TIGHT))


def write_pngs():
    from playwright.sync_api import sync_playwright
    font = "'Inter Display','Inter',-apple-system,Helvetica,sans-serif"

    def page(body, w, h, bg="transparent"):
        return f'<html><body style="margin:0;width:{w}px;height:{h}px;background:{bg};overflow:hidden">{body}</body></html>'

    def sized(svg_text, w, h=None):
        return svg_text.replace("<svg ", f'<svg width="{w}" height="{h or w}" ', 1)

    def lockup(fg, bg):
        return page(f'''<div style="height:350px;display:flex;align-items:center;justify-content:center;gap:56px;color:{fg}">
{sized(svg(mark(fg), TIGHT), 232, 205)}
<div style="font:500 128px {font};letter-spacing:-.025em">Vision Electronics</div></div>''', 1556, 350, bg)

    def centered(svg_text, size, bg="transparent", inner=None):
        return page(f'<div style="width:{size}px;height:{size}px;display:grid;place-items:center">{sized(svg_text, inner or size)}</div>',
                    size, size, bg)

    jobs = [
        ("img/brand/logo-on-light.png", lockup("#000", "#fff"), 1556, 350, False),
        ("img/brand/logo-on-dark.png", lockup("#fff", "#000"), 1556, 350, False),
        ("img/brand/logo-transparent.png", lockup("#000", "transparent"), 1556, 350, True),
        ("img/brand/social-profile-1080.png", centered(svg(mark("#000")), 1080, "#fff", 640), 1080, 1080, False),
        ("img/brand/icon-512.png", centered(round_icon(), 512), 512, 512, True),
        ("img/brand/icon-192.png", centered(round_icon(), 192), 192, 192, True),
        ("img/brand/favicon-32.png", centered(round_icon(), 32), 32, 32, True),
        ("apple-touch-icon.png", centered(svg(mark("#fff")), 180, "#000", 112), 180, 180, False),
    ]
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/usr/bin/google-chrome")
        for name, html, w, h, transparent in jobs:
            pg = browser.new_page(viewport={"width": w, "height": h})
            pg.set_content(html)
            pg.screenshot(path=str(STATIC / name), omit_background=transparent)
            pg.close()
        browser.close()


if __name__ == "__main__":
    write_svgs()
    write_pngs()
    print("Brand files written.")
