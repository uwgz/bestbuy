"""
Build every logo file — and the logo animation — from one drawing.

    python tools/brand.py      # writes public/static/img/brand/*, favicon.svg, apple-touch-icon.png,
                               # public/favicon.ico and the animated logos in app/templates/partials/

The mark: a shopping bag with a camera lens on it (the shop and the studio in one picture).
The lens is a hole cut through the bag, so the page shows through it; in its centre sits the
lens glass and a small red dot that blinks in the animation, like a camera's recording light.

SVG files need only Python; the PNG files are rendered with Playwright + Chrome (dev machines only).
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "public" / "static"
BRAND = STATIC / "img" / "brand"
PARTIALS = ROOT / "app" / "templates" / "partials"

RED = "#ff3b30"
NAME = "Best Buy 250"
BLINK_SECONDS = 2.4

# ------------------------------------------------------------------ the drawing (64 × 64 grid)
# a circle as two arcs, so it can be cut out of the bag with the even-odd rule
def _circle(cx, cy, r):
    return f"M{cx - r} {cy}a{r} {r} 0 1 0 {2 * r} 0a{r} {r} 0 1 0 {-2 * r} 0Z"

HANDLE = "M24 21v-3a8 8 0 0 1 16 0v3"                        # drawn as a 3.6-wide rounded line
BAG = "M9 21h46l-3.1 33.3A4 4 0 0 1 47.9 58H16.1a4 4 0 0 1-4-3.7Z" + _circle(32, 40, 11)
GLASS = _circle(32, 40, 6.2)
DOT = (32, 40, 2.7)

TIGHT = "8.5 7.5 47 51"                                 # just the mark
VIEW = "1 2 62 62"                                            # square, a little space around it


def mark(color="#000", dot=RED):
    return (f'<path d="{HANDLE}" fill="none" stroke="{color}" stroke-width="3.6" stroke-linecap="round"/>'
            f'<path d="{BAG}{GLASS}" fill="{color}" fill-rule="evenodd"/>'
            f'<circle cx="{DOT[0]}" cy="{DOT[1]}" r="{DOT[2]}" fill="{dot}"/>')


def svg(inner, view=VIEW, extra=""):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view}"{extra}>\n{inner}\n</svg>\n'


def round_icon(bg="#000", fg="#fff", style=""):
    """The mark in a circle (app icon, favicon)."""
    inner = (f'<circle cx="50" cy="50" r="50" fill="{bg}" class="bg"/>\n'
             f'<g transform="translate(50 52) scale(1.02) translate(-32 -32)" class="fg">{mark(fg)}</g>')
    return svg(style + inner, view="0 0 100 100")


def animated(cls, view=TIGHT, label=""):
    """The mark in the page's text colour (currentColor); the red dot in the lens blinks like a
    camera's recording light. People who turn off motion see the still mark."""
    aria = f' role="img" aria-label="{label}"' if label else ' aria-hidden="true"'
    blink = (f'<animate attributeName="opacity" dur="{BLINK_SECONDS}s" repeatCount="indefinite" '
             f'keyTimes="0;.45;.55;.9;1" values="1;1;.15;.15;1"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view}" class="{cls}"{aria}>\n'
            f'<path d="{HANDLE}" fill="none" stroke="currentColor" stroke-width="3.6" stroke-linecap="round"/>\n'
            f'<path d="{BAG}{GLASS}" fill="currentColor" fill-rule="evenodd"/>\n'
            f'<circle cx="{DOT[0]}" cy="{DOT[1]}" r="{DOT[2]}" fill="{RED}" class="rec-dot">{blink}</circle>\n</svg>\n')


# ------------------------------------------------------------------ writing files
def write_svgs():
    BRAND.mkdir(parents=True, exist_ok=True)
    (BRAND / "logo-mark.svg").write_text(svg(mark("#000")))
    (BRAND / "logo-mark-white.svg").write_text(svg(mark("#fff")))
    (BRAND / "app-icon.svg").write_text(round_icon())
    style = ("<style>.bg{fill:#000}.fg path{fill:#fff;stroke:#fff}.fg path[fill=none]{fill:none}"
             "@media (prefers-color-scheme:dark){.bg{fill:#fff}.fg path{fill:#000;stroke:#000}.fg path[fill=none]{fill:none}}</style>\n")
    (STATIC / "favicon.svg").write_text(round_icon(style=style))
    (PARTIALS / "loader_mark.svg").write_text(animated("loader-mark", VIEW))
    (PARTIALS / "logo_anim.svg").write_text(animated("logo-mark", TIGHT, NAME))
    (PARTIALS / "error_mark.svg").write_text(animated("error-mark", TIGHT))


def write_pngs():
    from playwright.sync_api import sync_playwright
    font = "'Inter Display','Inter',-apple-system,Helvetica,sans-serif"

    def page(body, w, h, bg="transparent"):
        return f'<html><body style="margin:0;width:{w}px;height:{h}px;background:{bg};overflow:hidden">{body}</body></html>'

    def sized(svg_text, w, h=None):
        return svg_text.replace("<svg ", f'<svg width="{w}" height="{h or w}" ', 1)

    def lockup(fg, bg):
        return page(f'''<div style="height:350px;display:flex;align-items:center;justify-content:center;gap:48px;color:{fg}">
{sized(svg(mark(fg), TIGHT), 230, 250)}
<div style="font:600 128px {font};letter-spacing:-.03em">{NAME}</div></div>''', 1556, 350, bg)

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
        ("apple-touch-icon.png", centered(svg(mark("#fff")), 180, "#000", 116), 180, 180, False),
    ]
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/usr/bin/google-chrome")
        for name, html, w, h, transparent in jobs:
            pg = browser.new_page(viewport={"width": w, "height": h})
            pg.set_content(html)
            pg.screenshot(path=str(STATIC / name), omit_background=transparent)
            pg.close()
        browser.close()

    from PIL import Image
    Image.open(BRAND / "icon-512.png").save(ROOT / "public" / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])


if __name__ == "__main__":
    write_svgs()
    write_pngs()
    print("Brand files written.")
