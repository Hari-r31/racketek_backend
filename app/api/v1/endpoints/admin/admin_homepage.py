"""
Admin homepage content management.

ROUTE ORDER FIX: Static path segments (/seed, /bulk) MUST be declared
BEFORE the dynamic catch-all (/{section_key}), otherwise FastAPI matches
"bulk" and "seed" as section_key values.

Routes:
  GET    /admin/homepage                → list all sections (with defaults)
  POST   /admin/homepage/seed           → seed ALL sections with DEFAULT_CONTENT
  PUT    /admin/homepage/bulk           → update multiple sections in one call
  GET    /admin/homepage/{key}          → get single section
  PUT    /admin/homepage/{key}          → create / update single section
  PATCH  /admin/homepage/{key}/toggle   → toggle is_active
  DELETE /admin/homepage/{key}          → reset to default (delete DB row)
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
# (declared first so it isn't matched by /{section_key})

@router.get("")
def get_all_sections(
    db: Session = Depends(get_db),
    _: User = Depends(require_staff_or_admin),
):
    rows   = db.query(HomepageContent).all()
    db_map = {row.section_key: row for row in rows}
    result = {}
    for key in ALL_SECTIONS:
        result[key] = _row_to_dict(db_map[key]) if key in db_map else _default_row(key)
    return {"sections": result, "all_section_keys": ALL_SECTIONS}


# ── POST /seed  (STATIC — must be before /{section_key}) ─────────────────────

@router.post("/seed")
def seed_all_sections(
    overwrite: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
):
    rows     = db.query(HomepageContent).all()
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
                section_key=key, content=default,
                is_active=True, updated_by=current_user.id,
            ))
            created.append(key)

    db.commit()
    return {"message": "Seed complete.", "created": created, "updated": updated, "skipped": skipped}


# ── PUT /bulk  (STATIC — must be before /{section_key}) ──────────────────────

@router.put("/bulk")
def bulk_update_sections(
    payload: BulkUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
):
    unknown = [k for k in payload.sections if k not in ALL_SECTIONS]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown section keys: {unknown}. Valid keys: {ALL_SECTIONS}",
        )

    rows    = db.query(HomepageContent).filter(
        HomepageContent.section_key.in_(list(payload.sections.keys()))
    ).all()
    row_map = {r.section_key: r for r in rows}
    saved   = []

    for key, data in payload.sections.items():
        content   = data.get("content", {})
        is_active = data.get("is_active", True)
        if key in row_map:
            row_map[key].content    = content
            row_map[key].is_active  = is_active
            row_map[key].updated_by = current_user.id
        else:
            db.add(HomepageContent(
                section_key=key, content=content,
                is_active=is_active, updated_by=current_user.id,
            ))
        saved.append(key)

    db.commit()
    return {"message": "Bulk update complete.", "saved": saved}


# ── GET /{section_key}  (DYNAMIC — after all static routes) ──────────────────

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
    return _row_to_dict(row) if row else _default_row(section_key)


# ── PUT /{section_key}  (DYNAMIC) ────────────────────────────────────────────

@router.put("/{section_key}")
def update_section(
    section_key: str,
    payload: UpdateSectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
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
        row.content    = payload.content
        row.is_active  = payload.is_active
        row.updated_by = current_user.id
    else:
        row = HomepageContent(
            section_key=section_key, content=payload.content,
            is_active=payload.is_active, updated_by=current_user.id,
        )
        db.add(row)

    db.commit()
    db.refresh(row)
    return {**_row_to_dict(row), "message": f"Section '{section_key}' saved successfully."}


# ── PATCH /{section_key}/toggle  (DYNAMIC) ───────────────────────────────────

@router.patch("/{section_key}/toggle")
def toggle_section(
    section_key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
):
    if section_key not in ALL_SECTIONS:
        raise HTTPException(status_code=400, detail="Unknown section key")

    row = db.query(HomepageContent).filter(
        HomepageContent.section_key == section_key
    ).first()

    if row:
        row.is_active  = not row.is_active
        row.updated_by = current_user.id
    else:
        row = HomepageContent(
            section_key=section_key,
            content=DEFAULT_CONTENT.get(section_key, {}),
            is_active=False, updated_by=current_user.id,
        )
        db.add(row)

    db.commit()
    db.refresh(row)
    return {"section_key": section_key, "is_active": row.is_active}


# ── DELETE /{section_key}  (DYNAMIC) ─────────────────────────────────────────

@router.delete("/{section_key}")
def reset_section(
    section_key: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_staff_or_admin),
):
    if section_key not in ALL_SECTIONS:
        raise HTTPException(status_code=400, detail="Unknown section key")

    row = db.query(HomepageContent).filter(
        HomepageContent.section_key == section_key
    ).first()
    if row:
        db.delete(row)
        db.commit()

    return {"message": f"Section '{section_key}' reset to default content."}
