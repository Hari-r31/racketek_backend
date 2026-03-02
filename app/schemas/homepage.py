"""
Homepage schemas — mirrors the InstaSport.club layout exactly.

Sections (in render order):
  announcement_bar      → top ticker / promo strip
  hero_banners          → full-width hero slideshow
  quick_categories      → image-card category shortcuts
  movement_section      → "More Than Just Gear, It's a Movement"
  homepage_videos       → auto-play video section(s)
  featured_product      → spotlight single product with gallery
  crafted_section       → "Crafted for Champions" dual-image reveal
  bundle_builder        → build-your-bundle product picker
  deal_of_day           → countdown-timer deal banner
  shop_the_look         → player image with hotspot products
  testimonials          → customer review carousel
  featured_collections  → tabbed product grid
  brand_spotlight       → brand feature banners (2 per row)
  about_section         → brand description + trust badges
"""
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from datetime import datetime

# ── Section key constants ─────────────────────────────────────────────────────
SECTION_ANNOUNCEMENT_BAR     = "announcement_bar"
SECTION_HERO_BANNERS         = "hero_banners"
SECTION_QUICK_CATEGORIES     = "quick_categories"
SECTION_MOVEMENT             = "movement_section"
SECTION_VIDEOS               = "homepage_videos"
SECTION_FEATURED_PRODUCT     = "featured_product"
SECTION_CRAFTED              = "crafted_section"
SECTION_BUNDLE_BUILDER       = "bundle_builder"
SECTION_DEAL_OF_DAY          = "deal_of_day"
SECTION_SHOP_THE_LOOK        = "shop_the_look"
SECTION_TESTIMONIALS         = "testimonials"
SECTION_FEATURED_COLLECTIONS = "featured_collections"
SECTION_BRAND_SPOTLIGHT      = "brand_spotlight"
SECTION_ABOUT                = "about_section"

# Ordered as they appear on the page
ALL_SECTIONS = [
    SECTION_ANNOUNCEMENT_BAR,
    SECTION_HERO_BANNERS,
    SECTION_QUICK_CATEGORIES,
    SECTION_MOVEMENT,
    SECTION_VIDEOS,
    SECTION_FEATURED_PRODUCT,
    SECTION_CRAFTED,
    SECTION_BUNDLE_BUILDER,
    SECTION_DEAL_OF_DAY,
    SECTION_SHOP_THE_LOOK,
    SECTION_TESTIMONIALS,
    SECTION_FEATURED_COLLECTIONS,
    SECTION_BRAND_SPOTLIGHT,
    SECTION_ABOUT,
]

# ── Placeholder image helper ──────────────────────────────────────────────────
def _ph(w: int, h: int, label: str = "") -> str:
    """picsum / placeholder URL for development preview."""
    seed = abs(hash(label)) % 1000
    txt = label.replace(" ", "+")
    return f"https://placehold.co/{w}x{h}/1a1a1a/ffffff?text={txt}"

# ── Default content ───────────────────────────────────────────────────────────
DEFAULT_CONTENT: Dict[str, Any] = {

    # ── 1. Announcement bar ───────────────────────────────────────────────────
    SECTION_ANNOUNCEMENT_BAR: {
        "messages": [
            {"text": "⚡ 2M+ Deliveries across India", "link": "/about"},
            {"text": "🚚 Free shipping above ₹1000", "link": "/shipping"},
            {"text": "✅ 100% Authentic Products Guaranteed", "link": "/about"},
            {"text": "🏆 India's Biggest Sports E-Commerce Store", "link": "/"},
        ],
        "bg_color": "#111111",
        "text_color": "#ffffff",
        "speed": 40,          # marquee scroll speed
    },

    # ── 2. Hero banners (slideshow) ───────────────────────────────────────────
    SECTION_HERO_BANNERS: {
        "auto_play": True,
        "interval": 4000,
        "banners": [
            {
                "id": 1,
                "title": "Play Like a Champion",
                "subtitle": "Premium badminton rackets for every level",
                "image_url": _ph(1440, 600, "Badminton+Banner"),
                "mobile_image_url": _ph(600, 800, "Badminton+Mobile"),
                "link": "/products?category=badminton",
                "cta": "Shop Now",
                "cta_link": "/products?category=badminton",
                "badge": "New Arrivals",
                "text_position": "center",   # left | center | right
                "gradient": "from-orange-900/70 to-black/50",
            },
            {
                "id": 2,
                "title": "Cricket Season is Here",
                "subtitle": "Professional bats, balls & protective gear",
                "image_url": _ph(1440, 600, "Cricket+Banner"),
                "mobile_image_url": _ph(600, 800, "Cricket+Mobile"),
                "link": "/products?category=cricket",
                "cta": "Explore Now",
                "cta_link": "/products?category=cricket",
                "badge": "Hot Deals",
                "text_position": "left",
                "gradient": "from-green-900/70 to-black/50",
            },
            {
                "id": 3,
                "title": "Dominate the Tennis Court",
                "subtitle": "Pro racquets, shoes & accessories",
                "image_url": _ph(1440, 600, "Tennis+Banner"),
                "mobile_image_url": _ph(600, 800, "Tennis+Mobile"),
                "link": "/products?category=tennis",
                "cta": "Shop Tennis",
                "cta_link": "/products?category=tennis",
                "badge": "Best Sellers",
                "text_position": "right",
                "gradient": "from-blue-900/70 to-black/50",
            },
            {
                "id": 4,
                "title": "Pickleball – The New Game in Town",
                "subtitle": "Paddles, balls & everything you need",
                "image_url": _ph(1440, 600, "Pickleball+Banner"),
                "mobile_image_url": _ph(600, 800, "Pickleball+Mobile"),
                "link": "/products?category=pickleball",
                "cta": "Discover Pickleball",
                "cta_link": "/products?category=pickleball",
                "badge": "Trending",
                "text_position": "center",
                "gradient": "from-purple-900/70 to-black/50",
            },
        ],
    },

    # ── 3. Quick category cards ───────────────────────────────────────────────
    SECTION_QUICK_CATEGORIES: {
        "heading": "Shop by Sport",
        "categories": [
            {
                "id": 1,
                "label": "Running Shoes",
                "subtitle": "Asics, Nike, Sketchers & more",
                "image_url": _ph(400, 400, "Running+Shoes"),
                "link": "/products?category=running",
                "color_accent": "#f97316",
            },
            {
                "id": 2,
                "label": "Badminton",
                "subtitle": "Racket, Shoes & more",
                "image_url": _ph(400, 400, "Badminton"),
                "link": "/products?category=badminton",
                "color_accent": "#eab308",
            },
            {
                "id": 3,
                "label": "Cricket",
                "subtitle": "Bat, Ball, Kit & more",
                "image_url": _ph(400, 400, "Cricket"),
                "link": "/products?category=cricket",
                "color_accent": "#22c55e",
            },
            {
                "id": 4,
                "label": "Tennis",
                "subtitle": "Racquet, Ball & more",
                "image_url": _ph(400, 400, "Tennis"),
                "link": "/products?category=tennis",
                "color_accent": "#3b82f6",
            },
            {
                "id": 5,
                "label": "Pickleball",
                "subtitle": "Paddle, Accessories & more",
                "image_url": _ph(400, 400, "Pickleball"),
                "link": "/products?category=pickleball",
                "color_accent": "#a855f7",
            },
        ],
    },

    # ── 4. Movement section ───────────────────────────────────────────────────
    SECTION_MOVEMENT: {
        "heading": "More Than Just",
        "heading_italic": "Gear",
        "heading_suffix": ", It's a",
        "heading_italic_2": "Movement",
        "paragraph": "At Racketek Outlet, we believe in empowering sports enthusiasts and athletes of all levels, fostering a vibrant sporting community. We provide top-tier gear, expert advice, and curated experiences to help you elevate your game. Join us in celebrating the passion and joy of sport.",
        "cta_text": "Our Story",
        "cta_link": "/about",
    },

    # ── 5. Homepage videos ────────────────────────────────────────────────────
    SECTION_VIDEOS: {
        "videos": [
            {
                "id": 1,
                "video_url": "",
                "poster_url": _ph(1920, 1080, "Video+Poster+1"),
                "title": "Badminton – Feel the Power",
                "subtitle": "Premium rackets for every court",
                "cta": "Shop Badminton",
                "cta_link": "/products?category=badminton",
            },
            {
                "id": 2,
                "video_url": "",
                "poster_url": _ph(1920, 1080, "Video+Poster+2"),
                "title": "Cricket – Own the Crease",
                "subtitle": "Professional cricket gear",
                "cta": "Shop Cricket",
                "cta_link": "/products?category=cricket",
            },
        ],
    },

    # ── 6. Featured product spotlight ────────────────────────────────────────
    SECTION_FEATURED_PRODUCT: {
        "product_id": None,
        "badge": "Speed · Comfort · Precision",
        "tag": "Featured Pick",
        "override_title": None,
        "override_description": None,
        # Shown when product_id is None (placeholder preview)
        "placeholder": {
            "title": "Featured Badminton Shoe",
            "description": "Top-of-the-line badminton shoes crafted for speed, comfort and precision. Available in multiple colours and sizes.",
            "images": [_ph(600, 600, f"Shoe+{i}") for i in range(1, 6)],
            "price": 6349,
            "compare_price": 7999,
        },
    },

    # ── 7. Crafted for champions (dual-image reveal) ──────────────────────────
    SECTION_CRAFTED: {
        "headline": "Crafted for",
        "headline_italic": "Champions",
        "subtext": "Every product handpicked for performance, durability and style.",
        "slides": [
            {
                "id": 1,
                "image_url": _ph(1440, 600, "Crafted+1"),
                "label": "Performance",
            },
            {
                "id": 2,
                "image_url": _ph(1440, 600, "Crafted+2"),
                "label": "Style",
            },
        ],
        "featured_product_id": None,    # optional separate product for this block
        "featured_product_label": "AIRAVAT THOR 7406",
    },

    # ── 8. Bundle builder ─────────────────────────────────────────────────────
    SECTION_BUNDLE_BUILDER: {
        "heading": "Build your",
        "heading_italic": "Bundle",
        "subtext": "The choice is yours. Select any combination from our range of products. The easiest way to keep everyone happy.",
        "trust_badges": [
            "Fast Shipping",
            "Authentic Products",
            "Best Prices",
        ],
        # product_ids available in the bundle picker (admin selects)
        "product_ids": [],
        # min products to unlock bundle discount
        "min_items": 2,
        "discount_label": "Save Extra",
    },

    # ── 9. Deal of the day ────────────────────────────────────────────────────
    SECTION_DEAL_OF_DAY: {
        "heading": "Exclusive Deals on Your Favourite Sport",
        "image_url": _ph(1440, 300, "Deal+Banner"),
        "cta": "Shop Now",
        "cta_link": "/collections/deal-of-the-day",
        "bg_color": "#0f172a",
        # ISO datetime string — admin sets this; frontend shows countdown
        "ends_at": "2026-12-31T23:59:59",
        # product_ids to feature in the deal section
        "product_ids": [],
    },

    # ── 10. Shop the look ─────────────────────────────────────────────────────
    SECTION_SHOP_THE_LOOK: {
        "heading": "Player's Choice",
        "subheading": "Shop the",
        "subheading_italic": "look",
        "player_image": _ph(600, 800, "Player+Image"),
        "products": [
            {
                "id": 1,
                "product_id": None,
                "label": "Racket",
                "hotspot_x": 45,     # % from left
                "hotspot_y": 30,     # % from top
                "side": "right",     # card appears on left/right of dot
                "placeholder_image": _ph(200, 200, "Racket"),
                "placeholder_name": "Featured Racket",
                "placeholder_price": 0,
            },
            {
                "id": 2,
                "product_id": None,
                "label": "Shoes",
                "hotspot_x": 50,
                "hotspot_y": 75,
                "side": "right",
                "placeholder_image": _ph(200, 200, "Shoes"),
                "placeholder_name": "Featured Shoes",
                "placeholder_price": 0,
            },
        ],
    },

    # ── 11. Testimonials ──────────────────────────────────────────────────────
    SECTION_TESTIMONIALS: {
        "heading": "What Our Athletes Say",
        "testimonials": [
            {
                "id": 1,
                "quote": "I had an amazing time shopping with Racketek Outlet!",
                "author": "Nikhil G.",
                "role": "Badminton Enthusiast",
                "avatar": _ph(80, 80, "Avatar+1"),
                "rating": 5,
            },
            {
                "id": 2,
                "quote": "Very happy with the product — fits perfectly, looks super!",
                "author": "Narasimha G.",
                "role": "Recreational Player",
                "avatar": _ph(80, 80, "Avatar+2"),
                "rating": 5,
            },
            {
                "id": 3,
                "quote": "Bought a pair of shoes and my experience was wonderful.",
                "author": "Bharath M.",
                "role": "Club-Level Tennis Player",
                "avatar": _ph(80, 80, "Avatar+3"),
                "rating": 5,
            },
            {
                "id": 4,
                "quote": "Price was competitive, product was genuine. Highly recommend!",
                "author": "Vamsi Krishna",
                "role": "Squash Player",
                "avatar": _ph(80, 80, "Avatar+4"),
                "rating": 5,
            },
        ],
    },

    # ── 12. Featured collections (tabbed grid) ────────────────────────────────
    SECTION_FEATURED_COLLECTIONS: {
        "heading": "Featured Collections",
        "tabs": [
            {"id": "swimming",     "label": "Swimming Goggles",  "product_ids": []},
            {"id": "backpacks",    "label": "Backpacks",         "product_ids": []},
            {"id": "boxing",       "label": "Boxing Gloves",     "product_ids": []},
            {"id": "sunglasses",   "label": "Sports Sunglasses", "product_ids": []},
            {"id": "table_tennis", "label": "Table Tennis",      "product_ids": []},
            {"id": "golf",         "label": "Golf Balls",        "product_ids": []},
        ],
        # Fallback: auto-pick featured products when a tab's product_ids is empty
        "fallback_featured": True,
    },

    # ── 13. Brand spotlight banners ───────────────────────────────────────────
    SECTION_BRAND_SPOTLIGHT: {
        "heading": "Top Brands",
        "banners": [
            {
                "id": 1,
                "brand_name": "Yonex",
                "image_url": _ph(540, 300, "Yonex+Banner"),
                "link": "/products?brand=yonex",
                "label": "Yonex Gear",
            },
            {
                "id": 2,
                "brand_name": "Apacs",
                "image_url": _ph(540, 300, "Apacs+Banner"),
                "link": "/products?brand=apacs",
                "label": "Apacs Gear",
            },
            {
                "id": 3,
                "brand_name": "SG Cricket",
                "image_url": _ph(540, 300, "SG+Cricket+Banner"),
                "link": "/products?brand=sg",
                "label": "SG Gear",
            },
            {
                "id": 4,
                "brand_name": "DSC",
                "image_url": _ph(540, 300, "DSC+Banner"),
                "link": "/products?brand=dsc",
                "label": "DSC Gear",
            },
        ],
    },

    # ── 14. About / footer trust section ─────────────────────────────────────
    SECTION_ABOUT: {
        "tagline": "India's Biggest Sports E-Commerce Store",
        "description": "At Racketek Outlet, we're committed to bringing you authentic, top-quality sports equipment at the best prices. From beginners to professionals — we've got your game covered.",
        "stats": [
            {"label": "Happy Athletes",    "value": "10,000+"},
            {"label": "Brands",            "value": "50+"},
            {"label": "Products",          "value": "5,000+"},
            {"label": "Cities Served",     "value": "100+"},
        ],
        "trust_badges": [
            {"icon": "truck",     "text": "Free Shipping above ₹1000"},
            {"icon": "shield",    "text": "100% Authentic Products"},
            {"icon": "refresh",   "text": "Easy Returns"},
            {"icon": "headphone", "text": "24/7 Support"},
        ],
        "top_categories": [
            "Badminton", "Cricket", "Tennis", "Pickleball",
            "Fitness", "Swimming", "Cycling",
        ],
        "social_links": {
            "facebook":  "https://facebook.com",
            "instagram": "https://instagram.com",
            "youtube":   "https://youtube.com",
        },
    },
}

# ── Pydantic schemas ──────────────────────────────────────────────────────────
class HomepageSectionResponse(BaseModel):
    section_key: str
    content: Dict[str, Any]
    is_active: bool
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class HomepageResponse(BaseModel):
    sections: Dict[str, Any]


class UpdateSectionRequest(BaseModel):
    content: Dict[str, Any]
    is_active: bool = True


class BulkUpdateRequest(BaseModel):
    """Update multiple sections in one call."""
    sections: Dict[str, Dict[str, Any]]  # { section_key: { content: {}, is_active: bool } }
