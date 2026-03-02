"""
Admin homepage content management.
Mirrors the InstaSport.club layout — every section is editable.

Routes:
  GET    /admin/homepage                → list all sections (with defaults)
  GET    /admin/homepage/{key}          → get single section
  PUT    /admin/homepage/{key}          → create / update single section
  PATCH  /admin/homepage/{key}/toggle   → toggle is_active
  DELETE /admin/homepage/{key}          → reset to default (delete DB row)
  POST   /admin/homepage/seed           → seed ALL sections with DEFAULT_CONTENT
  PUT    /admin/homepage/bulk           → update multiple sections in one call
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Any, Dict

from app.core.dependencies import get_db, require_staff_or_admin
from app.models.homepage import HomepageContent
from app.models.user import User
from app.schemas.homepage import (
    UpdateSectionRequest,
    BulkUpdateRequest,
    ALL_SECTIONS,
    DEFAULT_CONTENT,
)

router = APIRouter()


# ── helpers ───────────────────────────────────────────────────────────────────

def _row_to_dict(row: HomepageContent) -> Dict[str, Any]:
    return {
        "section_key": row.section_key,
        "content":     row.content,
        "is_active":   row.is_active,
        "updated_by":  row.updated_by,
        "updated_at":  row.updated_at.isoformat() if row.updated_at else None,
        "created_at":  row.created_at.isoformat() if row.created_at else None,
    }


def _default_row(key: str) -> Dict[str, Any]:
    return {
        "section_key": key,
        "content":     DEFAULT_CONTENT.get(key, {}),
        "is_active":   True,
        "updated_by":  None,
        "updated_at":  None,
        "created_at":  None,
    }


# ── GET all sections ──────────────────────────────────────────────────────────

@router.get("")
def get_all_sections(
    db: Session = Depends(get_db),
    _: User = Depends(require_staff_or_admin),
):
    """Return ALL sections (including inactive) for the admin editor.
    Missing DB rows are filled with DEFAULT_CONTENT so the editor can show them."""
    rows = db.query(HomepageContent).all()
    db_map = {row.section_key: row for row in rows}

    result = {}
    for key in ALL_SECTIONS:
        if key in db_map:
            result[key] = _row_to_dict(db_map[key])
        else:
            result[key] = _default_row(key)

    return {
        "sections": result,
        "all_section_keys": ALL_SECTIONS,
    }


# ── GET single section ────────────────────────────────────────────────────────

@router.get("/{section_key}")
def get_section(
    section_key: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_staff_or_admin),
):
    if section_key not in ALL_SECTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown section key '{section_key}'. Valid keys: {ALL_SECTIONS}",
        )
    row = db.query(HomepageContent).filter(
        HomepageContent.section_key == section_key
    ).first()
    if row:
        return _row_to_dict(row)
    return _default_row(section_key)


# ── PUT single section (create or update) ────────────────────────────────────

@router.put("/{section_key}")
def update_section(
    section_key: str,
    payload: UpdateSectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
):
    """Create or update a single homepage section."""
    if section_key not in ALL_SECTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown section key '{section_key}'. Valid keys: {ALL_SECTIONS}",
        )

    row = db.query(HomepageContent).filter(
        HomepageContent.section_key == section_key
    ).first()

    if row:
        row.content    = payload.content
        row.is_active  = payload.is_active
        row.updated_by = current_user.id
    else:
        row = HomepageContent(
            section_key = section_key,
            content     = payload.content,
            is_active   = payload.is_active,
            updated_by  = current_user.id,
        )
        db.add(row)

    db.commit()
    db.refresh(row)
    return {
        **_row_to_dict(row),
        "message": f"Section '{section_key}' saved successfully.",
    }


# ── PATCH toggle active ───────────────────────────────────────────────────────

@router.patch("/{section_key}/toggle")
def toggle_section(
    section_key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
):
    """Toggle is_active for a section. Creates the row if it doesn't exist yet."""
    if section_key not in ALL_SECTIONS:
        raise HTTPException(status_code=400, detail="Unknown section key")

    row = db.query(HomepageContent).filter(
        HomepageContent.section_key == section_key
    ).first()

    if row:
        row.is_active  = not row.is_active
        row.updated_by = current_user.id
    else:
        # Create with defaults but inactive
        row = HomepageContent(
            section_key = section_key,
            content     = DEFAULT_CONTENT.get(section_key, {}),
            is_active   = False,
            updated_by  = current_user.id,
        )
        db.add(row)

    db.commit()
    db.refresh(row)
    return {"section_key": section_key, "is_active": row.is_active}


# ── DELETE (reset to default) ─────────────────────────────────────────────────

@router.delete("/{section_key}")
def reset_section(
    section_key: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_staff_or_admin),
):
    """Delete the DB row — the public endpoint will fall back to DEFAULT_CONTENT."""
    if section_key not in ALL_SECTIONS:
        raise HTTPException(status_code=400, detail="Unknown section key")

    row = db.query(HomepageContent).filter(
        HomepageContent.section_key == section_key
    ).first()
    if row:
        db.delete(row)
        db.commit()

    return {"message": f"Section '{section_key}' reset to default content."}


# ── POST /seed — one-click seed all sections with DEFAULT_CONTENT ─────────────

@router.post("/seed")
def seed_all_sections(
    overwrite: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
):
    """
    Seed every section with DEFAULT_CONTENT.
    - overwrite=false (default): only inserts sections that don't exist yet.
    - overwrite=true            : replaces ALL section content with defaults.
    Returns a summary of what was created/updated/skipped.
    """
    rows = db.query(HomepageContent).all()
    existing = {r.section_key: r for r in rows}

    created, updated, skipped = [], [], []

    for key in ALL_SECTIONS:
        default = DEFAULT_CONTENT.get(key, {})
        if key in existing:
            if overwrite:
                existing[key].content    = default
                existing[key].is_active  = True
                existing[key].updated_by = current_user.id
                updated.append(key)
            else:
                skipped.append(key)
        else:
            db.add(HomepageContent(
                section_key = key,
                content     = default,
                is_active   = True,
                updated_by  = current_user.id,
            ))
            created.append(key)

    db.commit()
    return {
        "message": "Seed complete.",
        "created": created,
        "updated": updated,
        "skipped": skipped,
    }


# ── PUT /bulk — update multiple sections in one request ──────────────────────

@router.put("/bulk")
def bulk_update_sections(
    payload: BulkUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
):
    """
    Update multiple sections in a single API call.
    Body: { "sections": { "<key>": { "content": {...}, "is_active": true } } }
    Unknown keys are rejected.
    """
    unknown = [k for k in payload.sections if k not in ALL_SECTIONS]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown section keys: {unknown}. Valid keys: {ALL_SECTIONS}",
        )

    rows = db.query(HomepageContent).filter(
        HomepageContent.section_key.in_(list(payload.sections.keys()))
    ).all()
    row_map = {r.section_key: r for r in rows}

    saved = []
    for key, data in payload.sections.items():
        content   = data.get("content", {})
        is_active = data.get("is_active", True)

        if key in row_map:
            row = row_map[key]
            row.content    = content
            row.is_active  = is_active
            row.updated_by = current_user.id
        else:
            row = HomepageContent(
                section_key = key,
                content     = content,
                is_active   = is_active,
                updated_by  = current_user.id,
            )
            db.add(row)
        saved.append(key)

    db.commit()
    return {"message": "Bulk update complete.", "saved": saved}
