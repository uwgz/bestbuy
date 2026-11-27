# Best Buy 250

A website for an electronics shop with a photography studio.
**Flask** serves the pages, **Flask-SQLAlchemy** keeps everything the site shows in a database
(Neon PostgreSQL online, a small SQLite file on your computer), and **Tailwind CSS** styles it.
There is no login or admin yet: that is the next step. Visitors' carts and likes stay in their browser;
orders go to your WhatsApp.

## What is where
| Folder / file | What it is |
|---|---|
| `bestbuy/models.py` | The database tables: Setting, Category, Product (+ ProductPhoto), Service, PortfolioItem, HeroSlide |
| `bestbuy/pages.py` | The pages: home, shop, product, cart, photography, contact |
| `bestbuy/seed.py` | The **starting content**, copied into an empty database once. After that the database is what counts |
| `bestbuy/config.py` | Reads `DATABASE_URL` (Neon) |
| `templates/` | The HTML pages (Tailwind classes) |
| `public/static/` | CSS, JavaScript, logo files, photos |

## Run it on your computer
```
python -m venv .venv
.venv\Scripts\activate            (Windows)   or   source .venv/bin/activate   (Mac/Linux)
pip install -r requirements.txt
flask --app app run --debug
```
Open http://127.0.0.1:5000. Without a `.env` file it uses `instance/bestbuy.db` (SQLite) and fills it
with the starting content the first time.

To use your Neon database instead, create a `.env` file next to `app.py` (see `.env.example`):
```
DATABASE_URL=postgresql://USER:PASSWORD@ep-xxxx-pooler.REGION.aws.neon.tech/neondb?sslmode=require
```
Careful: on your computer this then changes your **live** data.

Commands:
```
flask --app app create-tables   # make missing tables (the site also does this when it starts)
flask --app app load-demo       # put the starting content into empty tables
flask --app app delete-old-site # delete the earlier site's tables (asks first; Neon only)
```

## Change what the site shows
Until the admin pages exist: open your Neon project → **Tables**, and edit rows there
(prices, stock, photos, store details in `settings`: `whatsapp`, `phone`, `address`, `hours`, `email`,
`instagram`, `facebook`, `tiktok`, `currency`, `decimals`, `slide_seconds`). Set `is_active` to false to hide a row.

## Host on Vercel
1. Push to GitHub. Vercel builds it.
2. Vercel → Settings → Environment Variables: `DATABASE_URL` = your Neon connection string
   (or connect Neon in Vercel's Storage tab, which adds it for you). Redeploy.
3. The first visit creates the tables and loads the starting content.

## Styles (Tailwind CSS)
`public/static/css/app.css` is already built. Only after adding new Tailwind classes:
`npm install tailwindcss@4` then `node tailwind/build.mjs`.

## Tests
```
pip install pytest
python -m pytest
```
