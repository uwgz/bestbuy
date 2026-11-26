"""Sample shop content for the tests only — the real website starts empty.

Images are drawn on the fly (plain coloured squares), so no photos are stored in the project.
"""
import io

from PIL import Image

PRODUCTS = [
    dict(name="Noise-Cancelling Headphones", category="audio", price_cents=29900, icon="headphones", home_position=1,
         description="30-hour battery, adaptive noise cancelling and studio-tuned sound."),
    dict(name="Bluetooth Speaker Pulse", category="audio", price_cents=12900, icon="speaker", home_position=2,
         description="Waterproof, rich bass and 20 hours of playtime."),
    dict(name="Smartphone S", category="phones", price_cents=89900, icon="smartphone",
         description="Triple camera system with night mode and 5G connectivity."),
    dict(name='Tablet Pro 11"', category="phones", price_cents=74900, icon="tablet",
         description="Bright display and stylus support for retouching on the go."),
    dict(name="Studio LED Light Kit", category="accessories", price_cents=24900, icon="lightbulb",
         description="Two bi-colour panels with stands and soft boxes."),
]

SERVICES = [
    dict(name="Portrait Sessions", icon="user", price_cents=14900, tagline="Headshots, families and personal portraits.",
         description="Individual, family and professional headshots.", includes="1-hour session\n15 edited photos"),
    dict(name="Weddings & Events", icon="heart", price_cents=120000, tagline="Your day, beautifully remembered.",
         description="Full-day coverage of weddings and events.", includes="Up to 8 hours\n400+ edited photos"),
    dict(name="Product Photography", icon="package", price_cents=2500, price_suffix="/ item", tagline="Images that sell.",
         description="Clean images for online stores.", includes="Web-ready files"),
]

GEAR = [
    dict(name="EOS R6 Mark III", role="Main camera", description="Full-frame body for stills and video."),
    dict(name="Joby RangePod Smart", role="Tripod", description="Light travel tripod."),
]

SETTINGS = {"phone": "(555) 123-4567", "email": "hello@example.com", "address": "123 Main Street",
            "hours": "Mon – Fri | 10:00 – 19:00", "whatsapp": "https://wa.me/15551234567", "whatsapp_orders": "15551234567",
            "instagram": "https://instagram.com/example"}


def _picture(color):
    buf = io.BytesIO()
    Image.new("RGB", (480, 360), color).save(buf, "JPEG")
    return buf.getvalue()


def load():
    """Fill the database (inside an app context) with the sample content above."""
    from app import images
    from app.models import gear, products, services, settings
    for n, item in enumerate(PRODUCTS, start=1):
        products.create(dict(item, position=n))
    for n, item in enumerate(SERVICES, start=1):
        sid = services.create(dict(item, position=n))
        services.add_image(sid, images._store(images._new_name("services", "jpg"), _picture((60 + 40 * n, 80, 120))), item["name"])
    for n, item in enumerate(GEAR, start=1):
        gear.create(dict(item, position=n, is_active=1),
                    images._store(images._new_name("gear", "jpg"), _picture((30, 30, 30 + 50 * n))))
    settings.save(SETTINGS)
