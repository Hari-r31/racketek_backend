"""
Racketek Seed Script - Creates admin/staff users + full sport category tree

Run:
    cd E:\Work\racketek\backend
    .venv\Scripts\python -m app.scripts.seed
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.models.cart import Cart
from app.models.category import Category
from app.core.security import get_password_hash

db = SessionLocal()

def upsert_user(full_name, email, phone, password, role):
    if db.query(User).filter(User.email == email).first():
        print(f"  ⏭  Already exists: {email}")
        return
    u = User(full_name=full_name, email=email, phone=phone,
             hashed_password=get_password_hash(password),
             role=role, is_active=True, is_email_verified=True)
    db.add(u); db.flush()
    db.add(Cart(user_id=u.id))
    db.commit()
    print(f"  ✅  {role.value:<13} {email:<32} pw: {password}")

def upsert_cat(name, slug, desc, parent_id=None, sort=0):
    c = db.query(Category).filter(Category.slug == slug).first()
    if c: return c.id
    c = Category(name=name, slug=slug, description=desc,
                 parent_id=parent_id, is_active=True, sort_order=sort)
    db.add(c); db.commit(); db.refresh(c)
    pad = "  └─ " if parent_id else ""
    print(f"  ✅  {pad}{name}")
    return c.id

# ── USERS ─────────────────────────────────────────────────────────────────────
print("\n👥  Default users")
upsert_user("Super Admin",   "admin@racketek.com",     "9000000001", "Admin@123",    UserRole.SUPER_ADMIN)
upsert_user("Admin User",    "admin2@racketek.com",    "9000000002", "Admin@123",    UserRole.ADMIN)
upsert_user("Staff Member",  "staff@racketek.com",     "9000000003", "Staff@123",    UserRole.STAFF)
upsert_user("Test Customer", "customer@racketek.com",  "9000000004", "Customer@123", UserRole.CUSTOMER)

# ── CATEGORIES ────────────────────────────────────────────────────────────────
print("\n🏷️  Sport categories")

b = upsert_cat("Badminton","badminton","Badminton rackets, shuttles & court gear",sort=1)
upsert_cat("Badminton Rackets","badminton-rackets","Pro & recreational rackets",b,1)
upsert_cat("Shuttlecocks","shuttlecocks","Feather & nylon shuttlecocks",b,2)
upsert_cat("Badminton Shoes","badminton-shoes","Court shoes for badminton",b,3)
upsert_cat("Strings & Grips","badminton-strings","Strings, overgrips & accessories",b,4)
upsert_cat("Badminton Bags","badminton-bags","Racket bags & backpacks",b,5)
upsert_cat("Badminton Nets","badminton-nets","Portable & tournament nets",b,6)

c = upsert_cat("Cricket","cricket","Bats, balls, helmets & protective gear",sort=2)
upsert_cat("Cricket Bats","cricket-bats","English & Kashmir willow",c,1)
upsert_cat("Cricket Balls","cricket-balls","Leather, rubber & tennis balls",c,2)
upsert_cat("Batting Gloves","batting-gloves","Professional batting gloves",c,3)
upsert_cat("Batting Pads","batting-pads","Leg guards & pads",c,4)
upsert_cat("Cricket Helmets","cricket-helmets","Safety helmets for batting",c,5)
upsert_cat("Cricket Shoes","cricket-shoes","Spiked & rubber-soled shoes",c,6)
upsert_cat("Protective Gear","cricket-protective","Thigh guards, arm guards & more",c,7)
upsert_cat("Cricket Bags","cricket-bags","Kit bags & duffle bags",c,8)

r = upsert_cat("Running","running","Shoes, apparel & running accessories",sort=3)
upsert_cat("Running Shoes","running-shoes","Road, trail & track shoes",r,1)
upsert_cat("Running Apparel","running-apparel","Shorts, tights & dry-fit tops",r,2)
upsert_cat("GPS Watches","gps-watches","Smart GPS & fitness watches",r,3)
upsert_cat("Running Accessories","running-accessories","Belts, caps, armbands & socks",r,4)

f = upsert_cat("Football","football","Boots, balls & goalkeeper gear",sort=4)
upsert_cat("Footballs","footballs","Match & training footballs",f,1)
upsert_cat("Football Boots","football-boots","Firm ground & turf boots",f,2)
upsert_cat("Goalkeeper Gloves","goalkeeper-gloves","Pro & training goalkeeper gloves",f,3)
upsert_cat("Shin Guards","shin-guards","Ankle & slip-in shin guards",f,4)
upsert_cat("Football Kits","football-kits","Jerseys, shorts & socks",f,5)

t = upsert_cat("Tennis","tennis","Rackets, balls, shoes & accessories",sort=5)
upsert_cat("Tennis Rackets","tennis-rackets","Adult & junior tennis rackets",t,1)
upsert_cat("Tennis Balls","tennis-balls","Match & practice tennis balls",t,2)
upsert_cat("Tennis Shoes","tennis-shoes","Hard court & clay court shoes",t,3)
upsert_cat("Tennis Bags","tennis-bags","Racket bags & backpacks",t,4)

g = upsert_cat("Fitness & Gym","fitness","Gym equipment & training accessories",sort=6)
upsert_cat("Yoga Mats","yoga-mats","Non-slip exercise & yoga mats",g,1)
upsert_cat("Dumbbells & Weights","dumbbells","Adjustable & fixed dumbbells",g,2)
upsert_cat("Resistance Bands","resistance-bands","Fabric & latex resistance bands",g,3)
upsert_cat("Skipping Ropes","skipping-ropes","Speed & weighted ropes",g,4)
upsert_cat("Gym Accessories","gym-accessories","Gloves, belts & wraps",g,5)

s = upsert_cat("Sportswear","sportswear","Multi-sport apparel & gym clothing",sort=7)
upsert_cat("T-Shirts & Tops","sports-tshirts","Dry-fit & compression tops",s,1)
upsert_cat("Track Pants & Shorts","sports-bottoms","Training pants, shorts & tights",s,2)
upsert_cat("Jackets & Hoodies","sports-jackets","Windcheaters & warm-ups",s,3)
upsert_cat("Compression Wear","compression-wear","Compression tights & base layers",s,4)

db.close()
print("""
✅  Seed complete!

┌──────────────────────────────────────────────────────────────┐
│  DEFAULT CREDENTIALS                                         │
│                                                              │
│  Role          Email                    Password             │
│  ─────────     ──────────────────────   ──────────           │
│  super_admin   admin@racketek.com       Admin@123            │
│  admin         admin2@racketek.com      Admin@123            │
│  staff         staff@racketek.com       Staff@123            │
│  customer      customer@racketek.com    Customer@123         │
└──────────────────────────────────────────────────────────────┘
""")
