"""
Admin store settings endpoint
Manages static contact info: email, phone, address, store name etc.
Stored as a single JSON row in homepage_content with key = "store_settings".

Routes:
  GET  /admin/settings        → get current settings
  PUT  /admin/settings        → update settings

Public route (no auth) for frontend consumption:
  GET  /settings              → public read of store settings
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.core.dependencies import get_db, require_staff_or_admin
from app.models.homepage import HomepageContent
from app.models.user import User

router = APIRouter()

SETTINGS_KEY = "store_settings"

# Default contact info pre-populated
DEFAULT_SETTINGS = {
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


def _get_or_default(db: Session) -> dict:
    row = db.query(HomepageContent).filter(
        HomepageContent.section_key == SETTINGS_KEY
    ).first()
    if row:
        # Merge with defaults so new keys are always present
        merged = {**DEFAULT_SETTINGS, **row.content}
        return merged
    return dict(DEFAULT_SETTINGS)


class StoreSettingsUpdate(BaseModel):
    store_name:    Optional[str] = None
    tagline:       Optional[str] = None
    email:         Optional[str] = None
    phone:         Optional[str] = None
    address:       Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city:          Optional[str] = None
    state:         Optional[str] = None
    country:       Optional[str] = None
    pincode:       Optional[str] = None
    whatsapp:      Optional[str] = None
    instagram:     Optional[str] = None
    facebook:      Optional[str] = None
    youtube:       Optional[str] = None
    twitter:       Optional[str] = None
    map_embed_url: Optional[str] = None
    support_hours: Optional[str] = None


# ── Admin: GET settings ───────────────────────────────────────────────────────
@router.get("")
def get_settings(
    db: Session = Depends(get_db),
    _: User = Depends(require_staff_or_admin),
):
    return _get_or_default(db)


# ── Admin: PUT settings ───────────────────────────────────────────────────────
@router.put("")
def update_settings(
    payload: StoreSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
):
    current = _get_or_default(db)
    # Merge — only update fields that were explicitly provided
    updates = payload.model_dump(exclude_none=True)
    merged  = {**current, **updates}

    row = db.query(HomepageContent).filter(
        HomepageContent.section_key == SETTINGS_KEY
    ).first()

    if row:
        row.content    = merged
        row.updated_by = current_user.id
    else:
        row = HomepageContent(
            section_key = SETTINGS_KEY,
            content     = merged,
            is_active   = True,
            updated_by  = current_user.id,
        )
        db.add(row)

    db.commit()
    db.refresh(row)
    return {**row.content, "message": "Settings saved successfully."}
