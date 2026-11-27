"""
Everything the website shows, written out by hand: no database, no admin.
To change a price, add a product or fill in your contact details, edit this file and push.

Photos come from Unsplash (free to use, https://unsplash.com/license). Swap any `photos`
entry for your own picture: put the file in public/static/img/products/ and write
"/static/img/products/your-file.jpg" instead of the Unsplash address.
"""

# ---------------------------------------------------------------- store details
# Fill these in. Anything left empty is simply not shown on the site.
STORE = {
    "name": "Best Buy 250",
    "tagline": "Electronics and photography, all in one place.",
    "currency": "RWF",          # shown before every price
    "decimals": 0,              # RWF has no cents; use 2 for CAD, USD …
    "whatsapp": "",             # digits with country code, no + or spaces, e.g. 250788123456
    "phone": "",                # as you want it shown, e.g. +250 788 123 456
    "email": "",
    "address": "",              # e.g. KN 4 Ave, Kigali
    "hours": "",                # e.g. Mon–Sat 8:00–19:00
    "map_url": "",              # a Google Maps link to the shop
    "instagram": "",            # full links to your pages
    "facebook": "",
    "tiktok": "",
}

# ---------------------------------------------------------------- categories
# key: (label, icon, SKU code)
CATEGORIES = {
    "phones": ("Phones & Tablets", "smartphone", "PHN"),
    "computers": ("Laptops & Computers", "laptop", "LAP"),
    "tv": ("TV & Home Theater", "tv", "TV"),
    "audio": ("Audio", "headphones", "AUD"),
    "cameras": ("Cameras", "camera", "CAM"),
    "lenses": ("Lenses", "aperture", "LNS"),
    "gaming": ("Gaming", "gamepad", "GAM"),
    "wearables": ("Smartwatches", "watch", "WCH"),
    "accessories": ("Accessories", "plug", "ACC"),
}


def unsplash(photo_id, width=1000):
    return f"https://images.unsplash.com/photo-{photo_id}?auto=format&fit=crop&w={width}&q=80"


# ---------------------------------------------------------------- products
# price: in RWF (whole number). discount: % off (0 = no sale).
# name: up to 20 words (product page). short: up to 4 words (cards, cart, lists).
# description: lines starting with "- " become bullet points under "About this product".
PRODUCTS = [
    # Phones & Tablets
    {"slug": "iphone-17-pro-256gb-cosmic-orange", "category": "phones",
     "name": "Apple iPhone 17 Pro 256GB - Cosmic Orange", "short": "iPhone 17 Pro",
     "price": 1950000, "discount": 0, "badge": "New", "stock": 6,
     "photos": [unsplash("1757710436034-f1d7372ec1be")],
     "description": "Apple's latest Pro iPhone in the new Cosmic Orange finish, with a bright ProMotion display and a pro camera system for photos and video.\n"
                    "- 256GB storage\n- 6.3\" Super Retina XDR display with ProMotion\n- Triple 48MP camera system\n- USB-C, all-day battery"},
    {"slug": "samsung-galaxy-a56-5g-128gb", "category": "phones",
     "name": "Samsung Galaxy A56 5G 128GB - Awesome Graphite", "short": "Galaxy A56 5G",
     "price": 620000, "discount": 8, "badge": "", "stock": 10,
     "photos": [unsplash("1596207891316-23851be3cc20")],
     "description": "A dependable 5G Android phone with a large AMOLED screen, a strong camera and a battery that lasts the day.\n"
                    "- 128GB storage, 8GB RAM\n- 6.7\" Super AMOLED, 120Hz\n- 50MP main camera\n- 5000mAh battery, 45W charging"},
    {"slug": "apple-iphone-x-64gb-silver-refurbished", "category": "phones",
     "name": "Apple iPhone X 64GB Silver (Certified Refurbished)", "short": "iPhone X Refurbished",
     "price": 260000, "discount": 0, "badge": "Refurbished", "stock": 3,
     "photos": [unsplash("1523206489230-c012c64b2b48")],
     "description": "A checked and cleaned iPhone X in excellent condition: an affordable way into iPhone.\n"
                    "- 64GB storage\n- 5.8\" OLED display, Face ID\n- Battery health 85% or more\n- 6-month shop warranty"},

    # Laptops & Computers
    {"slug": "macbook-air-13-m4-16gb-512gb", "category": "computers",
     "name": "Apple MacBook Air 13\" M4 - 16GB RAM - 512GB SSD - Silver", "short": "MacBook Air 13\" M4",
     "price": 1690000, "discount": 5, "badge": "", "stock": 4,
     "photos": [unsplash("1541807084-5c52b6b3adef"), unsplash("1499914485622-a88fac536970")],
     "description": "Thin, silent and fast: the MacBook Air with the M4 chip handles school, office work and photo editing with ease.\n"
                    "- Apple M4 chip, 16GB unified memory\n- 512GB SSD\n- 13.6\" Liquid Retina display\n- Up to 18 hours of battery"},
    {"slug": "macbook-pro-14-m4-pro-24gb-1tb", "category": "computers",
     "name": "Apple MacBook Pro 14\" M4 Pro - 24GB RAM - 1TB SSD - Space Black", "short": "MacBook Pro 14\"",
     "price": 3150000, "discount": 0, "badge": "Best seller", "stock": 2,
     "photos": [unsplash("1496181133206-80ce9b88a853"), unsplash("1525547719571-a2d4ac8945e2")],
     "description": "Power for video editors, photographers and developers, with a stunning XDR display and pro ports.\n"
                    "- Apple M4 Pro chip, 24GB unified memory\n- 1TB SSD\n- 14.2\" Liquid Retina XDR display\n- HDMI, SD card slot, 3× Thunderbolt 5"},

    # TV & Home Theater
    {"slug": "samsung-55-crystal-uhd-4k-smart-tv", "category": "tv",
     "name": "Samsung 55\" Crystal UHD 4K Smart TV", "short": "Samsung 55\" 4K TV",
     "price": 890000, "discount": 10, "badge": "Deal", "stock": 5,
     "photos": [unsplash("1560169897-fc0cdbdfa4d5")],
     "description": "Sharp 4K picture with rich colour and all your streaming apps built in.\n"
                    "- 55\" 4K UHD (3840 × 2160)\n- Crystal Processor 4K, HDR\n- Netflix, YouTube, Prime Video built in\n- 3× HDMI, 2× USB"},
    {"slug": "lg-65-4k-uhd-smart-tv", "category": "tv",
     "name": "LG 65\" 4K UHD Smart TV with webOS", "short": "LG 65\" 4K TV",
     "price": 1390000, "discount": 0, "badge": "", "stock": 3,
     "photos": [unsplash("1646861039459-fd9e3aabf3fb")],
     "description": "A big-screen 4K TV for the living room, with LG's simple webOS and the Magic Remote.\n"
                    "- 65\" 4K UHD\n- α5 AI Processor, HDR10\n- webOS with all major apps\n- Magic Remote included"},

    # Audio
    {"slug": "sony-wh-1000xm5-wireless-headphones-black", "category": "audio",
     "name": "Sony WH-1000XM5 Wireless Noise Cancelling Headphones - Black", "short": "Sony WH-1000XM5",
     "price": 520000, "discount": 12, "badge": "", "stock": 8,
     "photos": [unsplash("1618366712010-f4ae9c647dcb"), unsplash("1583394838336-acd977736f90")],
     "description": "Industry-leading noise cancelling with clear calls and up to 30 hours of listening.\n"
                    "- Adaptive noise cancelling\n- 30-hour battery, quick charge\n- Multipoint Bluetooth\n- Soft, lightweight design"},
    {"slug": "beats-studio-pro-wireless-headphones", "category": "audio",
     "name": "Beats Studio Pro Wireless Headphones - Sandstone", "short": "Beats Studio Pro",
     "price": 450000, "discount": 0, "badge": "", "stock": 5,
     "photos": [unsplash("1545127398-14699f92334b")],
     "description": "Bold Beats sound with active noise cancelling and easy pairing for iPhone and Android.\n"
                    "- Active noise cancelling and Transparency\n- Up to 40 hours of battery\n- USB-C lossless audio\n- Works with iOS and Android"},

    # Cameras
    {"slug": "sony-alpha-a7-iv-body", "category": "cameras",
     "name": "Sony Alpha a7 IV Full-Frame Mirrorless Camera (Body Only)", "short": "Sony a7 IV",
     "price": 3600000, "discount": 0, "badge": "Pro pick", "stock": 2,
     "photos": [unsplash("1516035069371-29a1b244cc32")],
     "description": "A full-frame hybrid camera for photographers and filmmakers: the one many of our studio shoots use.\n"
                    "- 33MP full-frame sensor\n- 4K 60p 10-bit video\n- Real-time Eye AF\n- 5-axis in-body stabilisation"},
    {"slug": "canon-eos-rebel-t7-18-55mm-kit", "category": "cameras",
     "name": "Canon EOS Rebel T7 DSLR Camera with EF-S 18-55mm Lens", "short": "Canon EOS Rebel T7",
     "price": 750000, "discount": 6, "badge": "", "stock": 4,
     "photos": [unsplash("1502920917128-1aa500764cbd"), unsplash("1495707902641-75cac588d2e9")],
     "description": "An easy first DSLR with a kit lens: great for learning photography, events and family pictures.\n"
                    "- 24.1MP APS-C sensor\n- 18-55mm kit lens\n- Wi-Fi and NFC\n- Full HD video"},

    # Lenses
    {"slug": "canon-ef-50mm-f1-8-stm", "category": "lenses",
     "name": "Canon EF 50mm f/1.8 STM Lens", "short": "Canon 50mm f/1.8",
     "price": 190000, "discount": 0, "badge": "", "stock": 7,
     "photos": [unsplash("1582994254571-52c62d96ebab")],
     "description": "The classic 'nifty fifty': light, sharp and perfect for portraits with a soft background.\n"
                    "- 50mm prime, f/1.8 aperture\n- Quiet STM autofocus\n- Weighs only 160g\n- Canon EF mount"},
    {"slug": "sony-fe-85mm-f1-8", "category": "lenses",
     "name": "Sony FE 85mm f/1.8 Portrait Lens", "short": "Sony FE 85mm f/1.8",
     "price": 850000, "discount": 0, "badge": "", "stock": 3,
     "photos": [unsplash("1758109683112-de123797b54a")],
     "description": "A favourite portrait lens for Sony full-frame cameras, with beautiful background blur.\n"
                    "- 85mm prime, f/1.8 aperture\n- Fast, quiet autofocus\n- Dust and moisture resistant\n- Sony E mount (full frame)"},

    # Gaming
    {"slug": "playstation-5-dualsense-controller-white", "category": "gaming",
     "name": "PlayStation 5 DualSense Wireless Controller - White", "short": "PS5 DualSense",
     "price": 110000, "discount": 0, "badge": "", "stock": 12,
     "photos": [unsplash("1768166210760-9c9a4299c436")],
     "description": "Feel every game with haptic feedback and adaptive triggers.\n"
                    "- Haptic feedback, adaptive triggers\n- Built-in microphone\n- USB-C charging\n- For PS5 and PC"},
    {"slug": "xbox-wireless-controller-carbon-black", "category": "gaming",
     "name": "Xbox Wireless Controller - Carbon Black", "short": "Xbox Controller",
     "price": 95000, "discount": 10, "badge": "", "stock": 9,
     "photos": [unsplash("1774103249154-32adc0bf71a7")],
     "description": "The comfortable Xbox controller with textured grips and a share button.\n"
                    "- Works with Xbox, PC, phones and tablets\n- Bluetooth and USB-C\n- Textured grip\n- Share button"},

    # Smartwatches
    {"slug": "apple-watch-series-10-gps-42mm", "category": "wearables",
     "name": "Apple Watch Series 10 GPS 42mm - Space Gray Sport Band", "short": "Apple Watch Series 10",
     "price": 620000, "discount": 0, "badge": "New", "stock": 5,
     "photos": [unsplash("1546868871-7041f2a55e12"), unsplash("1508685096489-7aacd43bd3b1")],
     "description": "The thinnest Apple Watch yet, with a bigger display, health tracking and fast charging.\n"
                    "- 42mm case, Always-On Retina display\n- Heart rate, sleep and fitness tracking\n- Water resistant 50m\n- Works with iPhone"},
    {"slug": "samsung-galaxy-watch-7-44mm", "category": "wearables",
     "name": "Samsung Galaxy Watch 7 44mm Bluetooth - Black", "short": "Galaxy Watch 7",
     "price": 420000, "discount": 15, "badge": "Deal", "stock": 4,
     "photos": [unsplash("1624096104992-9b4fa3a279dd")],
     "description": "A smart Android watch for health, fitness and notifications.\n"
                    "- 44mm Super AMOLED display\n- Health and sleep tracking\n- Up to 40 hours battery\n- Works with Android phones"},

    # Accessories
    {"slug": "usb-c-20w-fast-charger-with-cable", "category": "accessories",
     "name": "USB-C 20W Fast Charger with 1m USB-C Cable", "short": "20W USB-C Charger",
     "price": 35000, "discount": 0, "badge": "", "stock": 30,
     "photos": [unsplash("1677145503731-87bfe49e5c67")],
     "description": "Fast, safe charging for iPhone, Samsung and most USB-C phones.\n"
                    "- 20W USB-C power delivery\n- 1m USB-C to USB-C cable\n- Overheat protection"},
    {"slug": "phone-essentials-bundle", "category": "accessories",
     "name": "Phone Essentials Bundle: Case, Cable, Power Bank and Earbuds", "short": "Phone Essentials Bundle",
     "price": 75000, "discount": 20, "badge": "Bundle", "stock": 15,
     "photos": [unsplash("1758218096054-ef3c7b56582c")],
     "description": "Everything a new phone needs, in one box at a lower price.\n"
                    "- Protective case (tell us your phone model)\n- USB-C cable\n- 10,000mAh power bank\n- Wired earbuds"},
]

# ---------------------------------------------------------------- photography studio
SERVICES = [
    {"name": "Portrait session", "icon": "user", "price_from": 40000, "duration": "1 hour",
     "photo": unsplash("1627161683077-e34782c24d81", 900),
     "description": "Studio portraits for individuals, couples or families, with 10 edited photos."},
    {"name": "Passport & ID photos", "icon": "camera", "price_from": 5000, "duration": "10 minutes",
     "photo": unsplash("1765005204058-10418f5123c5", 900),
     "description": "Official-size photos printed while you wait."},
    {"name": "Events & weddings", "icon": "calendar", "price_from": 300000, "duration": "Half or full day",
     "photo": unsplash("1608009232260-9b527a5bb9bd", 900),
     "description": "Weddings, introductions (gusaba), graduations and parties, edited and delivered online."},
    {"name": "Product photography", "icon": "package", "price_from": 8000, "duration": "Per product",
     "photo": unsplash("1763970586854-62e14f07ae35", 900),
     "description": "Clean photos of your products for online shops and social media."},
]

# instagram: where the Instagram button on the photo goes; replace with the link to that post on your page
INSTAGRAM = "https://www.instagram.com/"
PORTFOLIO = [
    {"photo": unsplash("1506863530036-1efeddceb993", 900), "title": "Black and white portrait", "instagram": INSTAGRAM},
    {"photo": unsplash("1517462964-21fdcec3f25b", 900), "title": "Outdoor portrait", "instagram": INSTAGRAM},
    {"photo": unsplash("1532170579297-281918c8ae72", 900), "title": "Studio portrait", "instagram": INSTAGRAM},
    {"photo": unsplash("1581841064838-a470c740e8ee", 900), "title": "Fashion portrait", "instagram": INSTAGRAM},
    {"photo": unsplash("1606143412458-acc5f86de897", 900), "title": "Beauty portrait", "instagram": INSTAGRAM},
    {"photo": unsplash("1654765437547-6b572f52ee1a", 900), "title": "Evening dress", "instagram": INSTAGRAM},
]

# The home page photo is public/static/img/hero/desk-electronics.jpg: replace that file to change it.
