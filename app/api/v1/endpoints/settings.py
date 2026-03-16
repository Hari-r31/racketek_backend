"""
Public store settings endpoint — no auth required.
Frontend components (Footer, Contact page, etc.) use this to read
the current contact info, social links, and store details.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.models.homepage import HomepageContent

router = APIRouter()

SETTINGS_KEY = "store_settings"

DEFAULT_SETTINGS: dict = {
    "store_name":    "Racketek Outlet",
    "tagline":       "India's Biggest Sports E-Commerce Store",
    "email":         "support@racketek.com",
    "phone":         "+91 94911 47433",
    "address":       "Hyderabad, Telangana, India",
    "address_line1": "",
    "address_line2": "",
    "city":          "Hyderabad",
    "state":         "Telangana",
    "country":       "India",
    "pincode":       "",
    "whatsapp":      "+91 94911 47433",
    "instagram":     "",
    "facebook":      "",
    "youtube":       "",
    "twitter":       "",
    "map_embed_url": "",
    "support_hours": "Mon–Sat, 10 AM – 7 PM IST",
}


@router.get("/")
@router.get("")
def get_public_settings(db: Session = Depends(get_db)):
    """Public — no auth. Returns current store contact/settings."""
    row = db.query(HomepageContent).filter(
        HomepageContent.section_key == SETTINGS_KEY
    ).first()
    if row and row.content:
        return {**DEFAULT_SETTINGS, **row.content}
    return dict(DEFAULT_SETTINGS)
