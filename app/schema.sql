-- Best Buy 250 database schema (SQLite)
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name          TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    last_login_at TEXT
);

CREATE TABLE IF NOT EXISTS products (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    slug             TEXT NOT NULL UNIQUE,
    name             TEXT NOT NULL,
    short_name       TEXT NOT NULL DEFAULT '',
    category         TEXT NOT NULL,
    description      TEXT NOT NULL DEFAULT '',
    tagline          TEXT NOT NULL DEFAULT '',        -- one line used on the home page
    price_cents      INTEGER NOT NULL CHECK (price_cents >= 0),
    discount_percent INTEGER NOT NULL DEFAULT 0 CHECK (discount_percent BETWEEN 0 AND 90),
    discount_ends    TEXT,                            -- YYYY-MM-DD, empty = no end date
    badge            TEXT NOT NULL DEFAULT '',        -- e.g. "New", "Best seller"
    icon             TEXT NOT NULL DEFAULT 'package', -- shown when there is no photo
    studio_gear      INTEGER NOT NULL DEFAULT 0,      -- shown on the Photography page
    gear_role        TEXT NOT NULL DEFAULT '',        -- e.g. "Main camera"
    home_position    INTEGER NOT NULL DEFAULT 0,      -- 0 = not on home page, 1 = first ...
    in_stock         INTEGER NOT NULL DEFAULT 1,      -- kept in step with stock_qty (0 units = Sold out)
    stock_qty        INTEGER NOT NULL DEFAULT 0,      -- units on hand; recorded sales take units off
    is_active        INTEGER NOT NULL DEFAULT 1,      -- hidden from the shop when 0
    position         INTEGER NOT NULL DEFAULT 0,
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Sales the owner records in the admin (orders are paid on WhatsApp or in the shop, so the site
-- only knows a sale once it is recorded). Name and category are copied so history survives
-- a product being deleted.
CREATE TABLE IF NOT EXISTS sales (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id   INTEGER REFERENCES products(id) ON DELETE SET NULL,
    product_name TEXT NOT NULL,
    category     TEXT NOT NULL DEFAULT '',
    qty          INTEGER NOT NULL CHECK (qty > 0),
    unit_cents   INTEGER NOT NULL CHECK (unit_cents >= 0),
    total_cents  INTEGER NOT NULL CHECK (total_cents >= 0),
    sold_on      TEXT NOT NULL,                   -- YYYY-MM-DD
    note         TEXT NOT NULL DEFAULT '',
    created_by   INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_sales_sold_on ON sales (sold_on);

CREATE TABLE IF NOT EXISTS product_images (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    filename   TEXT NOT NULL,
    position   INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_product_images ON product_images(product_id, position);

CREATE TABLE IF NOT EXISTS services (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    slug        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    icon        TEXT NOT NULL DEFAULT 'camera',
    tagline     TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    includes    TEXT NOT NULL DEFAULT '',            -- one item per line
    price_label TEXT NOT NULL DEFAULT '',            -- older versions only (free text such as "from $149")
    price_prefix TEXT NOT NULL DEFAULT 'from',       -- "from" in "from RWF 149,000 / session"
    price_cents  INTEGER,                            -- amount in the store currency; NULL = no amount shown
    price_suffix TEXT NOT NULL DEFAULT '',           -- "/ session"
    is_active   INTEGER NOT NULL DEFAULT 1,
    position    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS service_images (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    service_id INTEGER NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    filename   TEXT NOT NULL,
    alt        TEXT NOT NULL DEFAULT '',
    position   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS portfolio (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL DEFAULT '',
    category   TEXT NOT NULL DEFAULT 'Portrait',
    filename   TEXT NOT NULL,
    instagram  TEXT NOT NULL DEFAULT '',   -- e.g. "eric" — the person in the photo
    position   INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS bookings (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    email      TEXT NOT NULL,
    phone      TEXT NOT NULL DEFAULT '',
    service    TEXT NOT NULL,
    date       TEXT NOT NULL,
    notes      TEXT NOT NULL DEFAULT '',
    is_read    INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    email      TEXT NOT NULL,
    subject    TEXT NOT NULL DEFAULT '',
    message    TEXT NOT NULL,
    is_read    INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Equipment the studio uses (not for sale) — shown on the Photography page
CREATE TABLE IF NOT EXISTS studio_gear (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    slug        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    role        TEXT NOT NULL DEFAULT '',          -- e.g. "Main camera"
    description TEXT NOT NULL DEFAULT '',
    filename    TEXT NOT NULL DEFAULT '',          -- photo in uploads/
    is_active   INTEGER NOT NULL DEFAULT 1,
    position    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Giveaways: the owner starts one from the admin; for each prize a secret random moment inside the
-- period is chosen, and the first visitor after that moment wins it.
CREATE TABLE IF NOT EXISTS giveaways (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    prize       TEXT NOT NULL,                  -- as shown to the winner, e.g. "Canon RF 50mm lens" or "RWF 50,000"
    prize_kind  TEXT NOT NULL DEFAULT 'device',     -- 'device' (from the shop) or 'money'
    product_id  INTEGER,                        -- the shop device, for prize_kind 'device'
    amount_cents INTEGER,                       -- the amount, for prize_kind 'money'
    prizes      INTEGER NOT NULL DEFAULT 1,     -- how many winners
    starts_at   TEXT NOT NULL,                  -- UTC, ISO 8601
    ends_at     TEXT NOT NULL,
    stopped_at  TEXT,                           -- set when stopped early from the admin
    is_test     INTEGER NOT NULL DEFAULT 0,     -- a test from "Try it yourself": only its link can win
    test_token  TEXT,                           -- secret part of the test link
    created_by  INTEGER,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS giveaway_wins (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    giveaway_id     INTEGER NOT NULL REFERENCES giveaways(id) ON DELETE CASCADE,
    win_at          TEXT NOT NULL,              -- the secret moment; first visitor after it wins
    code            TEXT UNIQUE,                -- given to the winner (NULL until someone wins)
    visitor         TEXT,                       -- the winner's browser (random id, not personal data)
    won_at          TEXT,
    claim_by        TEXT,                       -- won_at + 3 days
    collected_at    TEXT,
    collected_name  TEXT,
    collected_phone TEXT,
    collected_by    INTEGER
);
CREATE INDEX IF NOT EXISTS giveaway_wins_open ON giveaway_wins (giveaway_id, code, win_at);
