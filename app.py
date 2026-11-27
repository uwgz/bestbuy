"""Entry point for Vercel and for `flask --app app run`. The site itself lives in the bestbuy/ folder."""
from bestbuy import create_app

app = create_app()
