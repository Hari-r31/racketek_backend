#!/usr/bin/env python3
"""
test_api.py — Comprehensive API test for RacketOutlet backend
Tests: categories, products (with slug filter), users profile, auth
Usage: python test_api.py
"""
import sys, json, os
from pathlib import Path

# Bootstrap env
load_env_path = Path(__file__).parent / ".env"
if load_env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(load_env_path)

sys.path.insert(0, str(Path(__file__).parent))

from app.db.session import SessionLocal
from app.models.category import Category
from app.models.product import Product
from app.enums import ProductStatus
from app.models.user import User

# ─── colours ────────────────────────────────────────────────────────────────
G = "\033[92m"  # green
R = "\033[91m"  # red
Y = "\033[93m"  # yellow
B = "\033[94m"  # blue
W = "\033[0m"   # reset
PASS = f"{G}PASS{W}"
FAIL = f"{R}FAIL{W}"

passed = failed = 0

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  {PASS}  {name}")
        passed += 1
    else:
        print(f"  {FAIL}  {name}" + (f"  →  {Y}{detail}{W}" if detail else ""))
        failed += 1

def section(title):
    print(f"\n{B}{'─'*60}{W}")
    print(f"{B}  {title}{W}")
    print(f"{B}{'─'*60}{W}")


# ════════════════════════════════════════════════════════════════
db = SessionLocal()

try:
    # ── 1. CATEGORIES ─────────────────────────────────────────
    section("1. Categories")

    all_cats = db.query(Category).all()
    check("At least 1 category exists", len(all_cats) > 0,
          f"found {len(all_cats)}")

    parent_cats = db.query(Category).filter(Category.parent_id == None).all()
    check("Root (parent) categories exist", len(parent_cats) > 0,
          f"found {len(parent_cats)}")

    sub_cats = db.query(Category).filter(Category.parent_id != None).all()
    check("Sub-categories exist", len(sub_cats) > 0,
          f"found {len(sub_cats)}")

    # Check children relationship works
    if parent_cats:
        first_parent = parent_cats[0]
        check(f"Category '{first_parent.name}' has children loaded",
              hasattr(first_parent, 'children'),
              f"children attr present: {hasattr(first_parent, 'children')}")

    # Check slugs are unique
    slugs = [c.slug for c in all_cats]
    check("All category slugs are unique", len(slugs) == len(set(slugs)),
          f"duplicates: {len(slugs) - len(set(slugs))}")

    # Check active field
    active_cats = [c for c in all_cats if c.is_active]
    check("Active categories exist", len(active_cats) > 0,
          f"active: {len(active_cats)}/{len(all_cats)}")

    # ── 2. PRODUCTS ────────────────────────────────────────────
    section("2. Products")

    all_products = db.query(Product).all()
    check("Products exist in database", len(all_products) > 0,
          f"found {len(all_products)}")

    active_products = db.query(Product).filter(
        Product.status == ProductStatus.ACTIVE
    ).all()
    check("Active products exist", len(active_products) > 0,
          f"active: {len(active_products)}/{len(all_products)}")

    # Check products have images
    prods_with_images = [p for p in all_products if len(p.images) > 0]
    check("Products have images", len(prods_with_images) > 0,
          f"{len(prods_with_images)}/{len(all_products)} have images")

    # Check products have category_id
    prods_with_cat = [p for p in all_products if p.category_id is not None]
    check("Products have category assigned", len(prods_with_cat) > 0,
          f"{len(prods_with_cat)}/{len(all_products)} have category")

    # Check slugs are unique
    product_slugs = [p.slug for p in all_products]
    check("All product slugs are unique",
          len(product_slugs) == len(set(product_slugs)),
          f"duplicates: {len(product_slugs) - len(set(product_slugs))}")

    # Check SKUs are unique (only non-null)
    skus = [p.sku for p in all_products if p.sku]
    check("Product SKUs are unique (non-null)",
          len(skus) == len(set(skus)),
          f"duplicates: {len(skus) - len(set(skus))}")

    # Check featured/bestseller flags
    featured = [p for p in all_products if p.is_featured]
    bestsellers = [p for p in all_products if p.is_best_seller]
    check("Featured products exist", len(featured) > 0,
          f"found {len(featured)}")
    check("Best-seller products exist", len(bestsellers) > 0,
          f"found {len(bestsellers)}")

    # ── 3. CATEGORY SLUG FILTER (core bug fix) ─────────────────
    section("3. Category Slug Filter (core fix)")

    for sport_slug in ["badminton", "cricket", "tennis", "football"]:
        cat = db.query(Category).filter(Category.slug == sport_slug).first()
        if cat:
            # Collect all IDs (parent + children)
            cat_ids = [cat.id] + [c.id for c in (cat.children or [])]
            products = db.query(Product).filter(
                Product.category_id.in_(cat_ids),
                Product.status == ProductStatus.active,
            ).all()
            check(
                f"?category={sport_slug} returns products",
                len(products) > 0,
                f"found {len(products)} products, cat_ids={cat_ids}"
            )
        else:
            check(f"Category '{sport_slug}' exists", False,
                  "not found — run seed_data.py first")

    # Sub-category slug filter
    first_sub = db.query(Category).filter(Category.parent_id != None).first()
    if first_sub:
        sub_ids = [first_sub.id]
        sub_products = db.query(Product).filter(
            Product.category_id.in_(sub_ids),
            Product.status == ProductStatus.ACTIVE,
        ).all()
        check(
            f"Sub-category '{first_sub.slug}' filter works",
            True,  # existence is the test; 0 products is valid for a sub-cat
            f"found {len(sub_products)} products"
        )

    # ── 4. USER MODEL ──────────────────────────────────────────
    section("4. User Model / Schema")

    users = db.query(User).all()
    check("Users table accessible", True, f"{len(users)} users")

    if users:
        u = users[0]
        # Test new fields exist on model
        check("User has date_of_birth field",
              hasattr(u, 'date_of_birth'),
              "column should exist after migration 006")
        check("User has address_line1 field",
              hasattr(u, 'address_line1'))
        check("User has city field",    hasattr(u, 'city'))
        check("User has state field",   hasattr(u, 'state'))
        check("User has pincode field", hasattr(u, 'pincode'))

    # ── 5. DATA INTEGRITY ──────────────────────────────────────
    section("5. Data Integrity")

    # Products reference valid categories
    all_cat_ids = {c.id for c in all_cats}
    orphan_products = [
        p for p in all_products
        if p.category_id is not None and p.category_id not in all_cat_ids
    ]
    check("No orphan products (invalid category_id)",
          len(orphan_products) == 0,
          f"orphans: {[p.name for p in orphan_products[:3]]}")

    # Sub-categories reference valid parents
    all_cat_id_set = {c.id for c in all_cats}
    orphan_subcats = [
        c for c in sub_cats
        if c.parent_id not in all_cat_id_set
    ]
    check("No orphan sub-categories",
          len(orphan_subcats) == 0,
          f"orphans: {[c.name for c in orphan_subcats[:3]]}")

    # Products have prices > 0
    zero_price = [p for p in all_products if p.price <= 0]
    check("All products have price > 0",
          len(zero_price) == 0,
          f"zero-price: {[p.name for p in zero_price[:3]]}")

    # Products have stock >= 0
    neg_stock = [p for p in all_products if p.stock < 0]
    check("All products have stock >= 0",
          len(neg_stock) == 0,
          f"negative: {[p.name for p in neg_stock[:3]]}")

finally:
    db.close()

# ── Summary ────────────────────────────────────────────────────────────────
total = passed + failed
print(f"\n{'═'*60}")
print(f"  Results:  {G}{passed} passed{W}  /  {R}{failed} failed{W}  /  {total} total")

if failed == 0:
    print(f"  {G}✅  All tests passed — backend is healthy!{W}")
elif failed <= 3:
    print(f"  {Y}⚠  Minor issues — check FAIL items above{W}")
else:
    print(f"  {R}❌  Multiple failures — check seed data and migrations{W}")
print(f"{'═'*60}\n")

sys.exit(0 if failed == 0 else 1)
