# Best Buy 250

A simple website for an electronics shop with a photography studio.
Flask only serves the pages; there is **no login, no admin and no database**.
The cart and "likes" are kept in each visitor's browser, and orders go to your WhatsApp.

## Change what the site shows
Everything is in **`data.py`**:
- `STORE`: name, WhatsApp number, phone, email, address, opening hours, social links. Empty fields are hidden.
- `PRODUCTS`: name (up to 20 words), short name (up to 4 words), category, price, discount %, label, units in stock, photos, description (`- ` lines become bullet points).
- `SERVICES` and `PORTFOLIO`: the photography page.

Save, then push to GitHub: Vercel publishes it in about a minute.

## Run it on your computer
```
pip install -r requirements.txt
flask --app app run --debug
```
Open http://127.0.0.1:5000

## Styles (Tailwind CSS)
The pages use Tailwind classes. `public/static/css/app.css` is already built and committed,
so the live site needs nothing else. Only if you **add new Tailwind classes** to a page, rebuild it:
```
npm install tailwindcss@4
node tailwind/build.mjs
```

## Host on Vercel
1. Push this folder to GitHub.
2. In Vercel, import the repository (no settings or environment variables needed).
3. Done. Old variables from the previous version (DATABASE_URL, SECRET_KEY, BLOB_…) are no longer used and can be deleted.

## Tests
```
pip install pytest
python -m pytest
```
