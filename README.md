# Best Buy 250

Website for Best Buy 250 — an electronics shop with a photography studio.
Built with Flask (Python). The site starts **empty**: you add everything from the admin panel.

---

## Put it online (GitHub + Vercel)

You need free accounts on **GitHub**, **Vercel** and **Neon** (Neon keeps your data; you can create it from inside Vercel).

**1. Upload to GitHub**
Create an empty repository on github.com, then in this folder:

```bash
git remote add origin https://github.com/YOUR-NAME/best-buy-250.git
git push -u origin main
```

**2. Import into Vercel**
vercel.com → **Add New… → Project** → pick the repository → **Deploy**. Nothing to configure: Vercel finds the app by itself.

**3. Add a secret key**
Project → **Settings → Environment Variables** → add `SECRET_KEY` with a long random value
(for example from `python -c "import secrets; print(secrets.token_hex(32))"`).

**4. Connect the Neon database (keeps your products, settings and messages)**
Either Project → **Storage** → **Neon** → connect it to the project (Vercel then adds `DATABASE_URL` by itself),
or add it yourself: Project → **Settings → Environment Variables** → `DATABASE_URL` = your Neon connection
string (Neon → **Connect**; it starts with `postgresql://`). The tables are created automatically on the first visit.

**5. Connect photo storage (keeps the photos you upload)**
Project → **Storage → Create → Blob** → choose **Public** → connect it to the project.

**6. Redeploy** (Deployments → ⋯ → Redeploy), then open `https://your-site.vercel.app/altar`
and create your owner account. That's it — start adding products.

> Why steps 4 and 5? On Vercel the website can't keep files of its own between visits, so data and
> photos must live in these two services. Until they're connected, the admin dashboard shows a red warning.

---

## Using the site

The admin panel is at **/altar** (also linked as "Admin" at the bottom of every page).

| Admin page | What you do there |
|---|---|
| **Products** | Add devices with photos, prices, discounts; choose what shows on the home page |
| **Studio** | Photography services and the studio gear you use |
| **Portfolio** | Photos of your work (with the person's Instagram) — shown on the home and Photography pages |
| **Inbox** | Booking requests and contact messages |
| **Giveaway** | Give a device or money to random visitors; check winners' codes. **Try it yourself** shows you what winners see |
| **Store details** | Name, phone, email, address, hours, WhatsApp number, social links, **currency** |
| **Account** | Your password and team members |

**First things to fill in (Store details):** phone, email, address, opening hours, and the **WhatsApp
number** — it receives cart orders, contact messages and giveaway claims, and turns on the green
WhatsApp button. Parts of the site with nothing filled in stay hidden.

---

## Run it on your own computer (optional)

```bash
pip install -r requirements.txt
python run.py
```

Open http://127.0.0.1:5000. Without `DATABASE_URL`, data is kept in a file in the `instance/` folder
(not uploaded to GitHub). With your Neon `DATABASE_URL` in `.env`, your computer uses the same online
database as the live site — careful, changes are real.

---

## For developers

- `app/` — the website (pages in `templates/`, data in `models/`, admin in `blueprints/admin/`)
- `public/static/` — styles, scripts, logo and images (served directly by Vercel)
- `tools/brand.py` — redraws every logo file and the logo animation from `tools/emblem.json`
- `tests/` — automated checks: `pip install -r requirements-dev.txt && python -m pytest`
  (add `TEST_POSTGRES_URL=postgresql://…` for a throw-away PostgreSQL server to run them on PostgreSQL too)
- Database: SQLite file locally, PostgreSQL (Neon) when `DATABASE_URL` is set — `app/db.py`, `app/postgres.py`
- Settings come from environment variables; see `.env.example`

The logo is a licensed design — keep the original purchase file and licence somewhere safe, outside this project.
