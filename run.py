"""Start the development server:  python run.py   → http://127.0.0.1:5000"""
import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    # HOST=0.0.0.0 lets phones on the same Wi-Fi open the site
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", 5000)), debug=app.config.get("DEBUG", False))
