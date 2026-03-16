"""
Main API v1 Router - aggregates all endpoint routers
"""
from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth, users, address, products, categories,
    cart, wishlist, orders, payments, shipments,
    returns, reviews, coupons, support, upload,
    ai_assistant, homepage, bundle, settings,
)
from app.api.v1.endpoints.admin import (
    dashboard, admin_products, admin_orders, admin_users,
    admin_coupons, analytics, inventory, admin_homepage,
    admin_settings,
)

api_router = APIRouter()

# ── Customer routes ──────────────────────────────────────────────────────────
api_router.include_router(auth.router,          prefix="/auth",         tags=["Auth"])
api_router.include_router(users.router,         prefix="/users",        tags=["Users"])
api_router.include_router(address.router,       prefix="/addresses",    tags=["Addresses"])
api_router.include_router(products.router,      prefix="/products",     tags=["Products"])
api_router.include_router(categories.router,    prefix="/categories",   tags=["Categories"])
api_router.include_router(cart.router,          prefix="/cart",         tags=["Cart"])
api_router.include_router(wishlist.router,      prefix="/wishlist",     tags=["Wishlist"])
api_router.include_router(orders.router,        prefix="/orders",       tags=["Orders"])
api_router.include_router(payments.router,      prefix="/payments",     tags=["Payments"])
api_router.include_router(shipments.router,     prefix="/shipments",    tags=["Shipments"])
api_router.include_router(returns.router,       prefix="/returns",      tags=["Returns"])
api_router.include_router(reviews.router,       prefix="/reviews",      tags=["Reviews"])
api_router.include_router(coupons.router,       prefix="/coupons",      tags=["Coupons"])
api_router.include_router(support.router,       prefix="/support",      tags=["Support"])
api_router.include_router(upload.router,        prefix="/upload",       tags=["Upload"])
api_router.include_router(ai_assistant.router,  prefix="/ai",           tags=["AI Assistant"])
api_router.include_router(homepage.router,      prefix="/homepage",     tags=["Homepage"])
api_router.include_router(bundle.router,        prefix="/bundle",       tags=["Bundle"])
api_router.include_router(settings.router,      prefix="/settings",     tags=["Settings"])

# ── Admin routes ─────────────────────────────────────────────────────────────
api_router.include_router(dashboard.router,       prefix="/admin/dashboard",  tags=["Admin - Dashboard"])
api_router.include_router(admin_products.router,  prefix="/admin/products",   tags=["Admin - Products"])
api_router.include_router(admin_orders.router,    prefix="/admin/orders",     tags=["Admin - Orders"])
api_router.include_router(admin_users.router,     prefix="/admin/users",      tags=["Admin - Users"])
api_router.include_router(admin_coupons.router,   prefix="/admin/coupons",    tags=["Admin - Coupons"])
api_router.include_router(analytics.router,       prefix="/admin/analytics",  tags=["Admin - Analytics"])
api_router.include_router(inventory.router,       prefix="/admin/inventory",  tags=["Admin - Inventory"])
api_router.include_router(admin_homepage.router,  prefix="/admin/homepage",   tags=["Admin - Homepage"])
api_router.include_router(admin_settings.router,  prefix="/admin/settings",   tags=["Admin - Settings"])
