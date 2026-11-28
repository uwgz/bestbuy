# Best Buy 250

A website for an electronics shop with a photography studio.
**Flask** serves the pages, **Flask-SQLAlchemy** keeps everything the site shows in a database
(Neon PostgreSQL online, a small SQLite file on your computer), and **Tailwind CSS** styles it.
The admin is at **/admin**: the first visit creates the owner's account, then you sign in.
Visitors' carts and likes stay in their browser; orders go to your WhatsApp.

## What is where
| Folder / file | What it is |
|---|---|
| `bestbuy/models.py` | The database tables: Setting, Category, Product (+ ProductPhoto), StockMove, Order (+ OrderItem), Service, PortfolioItem, GearItem, HeroSlide, Giveaway (+ GiveawayCode), User (+ SecurityQuestion), AuditLog |
| `bestbuy/pages.py` | The website: home, shop, product, cart, photography, contact, the giveaway draw |
| `bestbuy/admin.py` | The admin (/admin): signing in, roles, inactivity sign-out, shared helpers |
| `bestbuy/admin_*.py` | One file per admin page: dashboard, stock, orders, photography, giveaways, employees, settings, account, upload |
| `bestbuy/blob.py` | Uploads photos to Vercel Blob |
| `bestbuy/seed.py` | The **starting content**, copied into an empty database once. After that the database is what counts |
| `bestbuy/config.py` | Settings read from the environment (`DATABASE_URL`, `SECRET_KEY`, …) |
| `templates/` | The HTML pages (Tailwind classes); `templates/admin/` for the admin |
| `public/static/` | CSS, JavaScript, logo files |

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

## The admin (/admin)
The first visit creates the **owner**. The owner adds the other people in **Employees** and gives each a role:

| Role | May use |
|---|---|
| Owner | Everything, including Employees and Settings |
| Manager | Everything except Employees and Settings |
| Employee | Stock (Sell, Refill, Return / loss) and Giveaways (check a code, give the prize) |

Security:
- **15 minutes without activity** signs you out (a minute before, a pop-up asks if you're still there).
  Change it with the `ADMIN_IDLE_MINUTES` environment variable.
- **Five wrong tries** in a row (password or security answers) lock the account for 15 minutes.
  The owner can end a lock by setting a new password in Employees.
- **Security questions:** everyone can set five questions and answers in **My account** (click your name).
  "Forgot your password?" on the sign-in page then lets them sign in by answering all five, and choose a new password.
  Answers are stored as hashes, like passwords; capitals and spaces don't matter.
- Every action is written to the `audit_logs` table (who, what, when, from where).

Photos are uploaded from the admin pop-ups to **Vercel Blob** (folders `products/`, `gear/`, `services/`,
`portfolio/`). Connecting the Blob store to the project adds `BLOB_STORE_ID`; the deployed site then signs uploads
with the token Vercel gives every request (OIDC), so nothing else is needed. Older connections add
`BLOB_READ_WRITE_TOKEN` instead, which also works. To upload while running the site on your computer, run
`vercel env pull .env` (adds a 12-hour `VERCEL_OIDC_TOKEN`) or put a `BLOB_READ_WRITE_TOKEN` in `.env`.

## Host on Vercel
1. Push to GitHub. Vercel builds it.
2. Vercel → Settings → Environment Variables: `DATABASE_URL` = your Neon connection string
   (or connect Neon in Vercel's Storage tab, which adds it for you), and `SECRET_KEY` = a long random text
   (`python -c "import secrets; print(secrets.token_hex(32))"`), type **Secret**. Connect your Blob store to the
   project (Storage → your store → Projects) so `BLOB_STORE_ID` is there for photo uploads. Redeploy.
3. The first visit creates the tables and loads the starting content.

## Styles (Tailwind CSS)
`public/static/css/app.css` is already built. Only after adding new Tailwind classes:
`npm install tailwindcss@4` then `node tailwind/build.mjs`.

## Tests
```
pip install pytest
python -m pytest
```
