#!/usr/bin/env python3
"""
Production Grade Seed Script
Creates:
- 10 sports
- 10 subcategories per sport
- 5 products per subcategory (500 total)
- 3 images per product
"""

import random
import re
import hashlib
import urllib.request
import sys
from pathlib import Path
from dotenv import load_dotenv

# ─────────────────────────────────────────────
# ENV LOAD
# ─────────────────────────────────────────────
load_dotenv(Path(__file__).parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))

from app.db.session import SessionLocal
from app.models.category import Category
from app.models.product import Product, ProductImage
from app.enums import ProductStatus
from app.utils.cloudinary_util import upload_image, configure_cloudinary


# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

PRODUCTS_PER_SUB = 5
IMAGES_PER_PRODUCT = 3

SPORTS = [
    "badminton","cricket","tennis","football","swimming",
    "running","fitness","table-tennis","basketball","cycling"
]

SUBS = {
    "badminton": ["Rackets","Shuttlecocks","Shoes","Bags","Strings","Grips","Apparel","Nets","Court Mats","Accessories"],
    "cricket": ["Bats","Pads","Gloves","Helmets","Balls","Shoes","Bags","Apparel","Training Aids","Accessories"],
    "tennis": ["Rackets","Balls","Shoes","Bags","Strings","Grips","Apparel","Overgrips","Court Accessories","Accessories"],
    "football": ["Boots","Balls","Jerseys","Shorts","Goalkeeper Gear","Shin Guards","Bags","Training Cones","Socks","Accessories"],
    "swimming": ["Goggles","Swimwear","Caps","Kickboards","Pull Buoys","Training Fins","Earplugs","Bags","Towels","Accessories"],
    "running": ["Shoes","Socks","Shorts","Compression Tights","Tops","Jackets","GPS Watches","Hydration","Headbands","Accessories"],
    "fitness": ["Dumbbells","Resistance Bands","Yoga Mats","Kettlebells","Pull-up Bars","Foam Rollers","Jump Ropes","Benches","Gloves","Accessories"],
    "table-tennis": ["Blades","Rubbers","Balls","Tables","Nets","Shoes","Bags","Apparel","Robot Trainers","Accessories"],
    "basketball": ["Balls","Shoes","Jerseys","Shorts","Compression","Ankle Braces","Bags","Training Hoops","Socks","Accessories"],
    "cycling": ["Helmets","Jerseys","Shorts","Gloves","Shoes","Lights","Bags","Water Bottles","GPS Computers","Accessories"],
}

BRANDS = {
    "badminton": ["Yonex", "Victor", "Li-Ning", "Ashaway"],
    "cricket": ["SG", "SS", "Kookaburra", "GM", "Masuri"],
    "tennis": ["Wilson", "Babolat", "Head", "Solinco"],
    "football": ["Nike", "Adidas", "Puma", "Under Armour"],
    "swimming": ["Speedo", "Arena", "TYR", "Zoggs"],
    "running": ["Nike", "ASICS", "Brooks", "On", "Garmin"],
    "fitness": ["Decathlon", "Boldfit", "RIMSports", "Adidas"],
    "table-tennis": ["Butterfly", "DHS", "Stiga", "Yasaka", "Tibhar"],
    "basketball": ["Spalding", "Wilson", "Nike", "Adidas", "Under Armour"],
    "cycling": ["Giro", "Bell", "Shimano", "Garmin", "Castelli"],
}

BASE_IMAGES = [
    "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=900&q=85",
    "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?w=900&q=85",
    "https://images.unsplash.com/photo-1517836357463-d25dfeac3438?w=900&q=85",
    "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=900&q=85",
] * 25  # expanded pool


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def slugify(text):
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"\s+", "-", text)
    return text.strip("-")


def make_sku(sport, sub, idx):
    h = hashlib.md5(f"{sport}{sub}{idx}".encode()).hexdigest()[:4]
    return f"{sport[:3].upper()}-{idx+1:03d}-{h}"


def download_bytes(url):
    req = urllib.request.Request(url, headers={"User-Agent": "SeedBot/1.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read()


IMAGE_CACHE = {}

def upload_cached(url, folder):
    if url in IMAGE_CACHE:
        return IMAGE_CACHE[url]

    data = download_bytes(url)
    res = upload_image(data, folder=folder)
    IMAGE_CACHE[url] = res["url"]
    return IMAGE_CACHE[url]


# ─────────────────────────────────────────────
# SEED FUNCTION
# ─────────────────────────────────────────────

def seed():
    configure_cloudinary()
    db = SessionLocal()

    print("🚀 Seeding 500 Products (High Performance Mode)")

    category_map = {}

    # 1️⃣ Create categories safely (idempotent)
    for sport in SPORTS:
        parent = db.query(Category).filter_by(slug=sport).first()
        if not parent:
            parent = Category(
                name=sport.title(),
                slug=sport,
                description=f"{sport.title()} equipment",
                is_active=True
            )
            db.add(parent)
            db.commit()

        for sub in SUBS[sport]:
            sub_slug = f"{sport}-{slugify(sub)}"
            sub_cat = db.query(Category).filter_by(slug=sub_slug).first()
            if not sub_cat:
                sub_cat = Category(
                    name=sub,
                    slug=sub_slug,
                    parent_id=parent.id,
                    is_active=True
                )
                db.add(sub_cat)
                db.commit()

            category_map[(sport, sub)] = sub_cat.id

    # 2️⃣ Generate products in memory
    products = []

    for sport in SPORTS:
        for sub in SUBS[sport]:
            for i in range(PRODUCTS_PER_SUB):

                brand = random.choice(BRANDS[sport])
                name = f"{brand} {sub} {i+1}"
                slug = slugify(f"{name}-{sport}-{i}")

                if db.query(Product).filter_by(slug=slug).first():
                    continue

                price = random.randint(999, 19999)

                products.append(Product(
                    name=name,
                    slug=slug,
                    brand=brand,
                    sku=make_sku(sport, sub, i),
                    price=price,
                    compare_price=int(price * 1.25),
                    cost_price=int(price * 0.55),
                    stock=random.randint(20, 150),
                    status=ProductStatus.active,
                    category_id=category_map[(sport, sub)]
                ))

    # 3️⃣ Bulk insert products
    db.bulk_save_objects(products)
    db.commit()

    # 4️⃣ Attach images
    inserted_products = db.query(Product).all()
    images = []

    for product in inserted_products:
        random.shuffle(BASE_IMAGES)
        selected = BASE_IMAGES[:IMAGES_PER_PRODUCT]

        for idx, img in enumerate(selected):
            cdn = upload_cached(
                img,
                folder=f"racketek/products/{product.slug}"
            )

            images.append(ProductImage(
                product_id=product.id,
                url=cdn,
                is_primary=(idx == 0),
                sort_order=idx
            ))

    db.bulk_save_objects(images)
    db.commit()

    print("══════════════════════════════")
    print(f"✅ Products Created: {len(products)}")
    print(f"🖼 Images Created:   {len(images)}")
    print("══════════════════════════════")

    db.close()


if __name__ == "__main__":
    seed()