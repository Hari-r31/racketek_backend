"""
Generic upload endpoint — images AND videos
Used by: Admin Homepage, Product images, Video sections
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, get_current_user, require_admin
from app.models.user import User
from app.models.product import Product, ProductImage
from app.utils.cloudinary_util import upload_image, upload_video, delete_image

router = APIRouter()

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/avif"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/webm", "video/quicktime", "video/x-msvideo"}
MAX_IMAGE_SIZE = 10 * 1024 * 1024   # 10 MB
MAX_VIDEO_SIZE = 200 * 1024 * 1024  # 200 MB


# ── Avatar upload — any authenticated user ────────────────────────────────────

@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a profile photo for the authenticated user.
    Returns { url, public_id }. Does NOT require admin role.
    """
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Only images allowed (JPEG, PNG, WebP). Got: {file.content_type}",
        )
    contents = await file.read()
    if len(contents) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=400, detail="Image too large (max 10 MB)")

    result = upload_image(contents, folder="racketek/avatars")
    return {"url": result["url"], "public_id": result["public_id"]}


# ── Generic upload (homepage, any admin use) ──────────────────────────────────

@router.post("")
async def upload_file(
    file: UploadFile = File(...),
    folder: str = Query("racketek/general", description="Cloudinary folder"),
    _: User = Depends(require_admin),
):
    """
    Upload any image or video. Returns { url, public_id, resource_type }.
    Used by the homepage admin editor and other admin sections.
    """
    is_video = file.content_type in ALLOWED_VIDEO_TYPES
    is_image = file.content_type in ALLOWED_IMAGE_TYPES

    if not is_image and not is_video:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Allowed: JPEG, PNG, WebP, MP4, WebM",
        )

    contents = await file.read()
    max_size = MAX_VIDEO_SIZE if is_video else MAX_IMAGE_SIZE
    if len(contents) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max {'200MB for video' if is_video else '10MB for images'}",
        )

    if is_video:
        result = upload_video(contents, folder=folder)
    else:
        result = upload_image(contents, folder=folder)

    return {
        "url":           result["url"],
        "public_id":     result["public_id"],
        "resource_type": result["resource_type"],
        "bytes":         result.get("bytes"),
    }


# ── Product-specific upload (keeps existing behaviour) ───────────────────────

@router.post("/product/{product_id}")
async def upload_product_image(
    product_id: int,
    is_primary: bool = False,
    file: UploadFile = File(...),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Upload a product image and attach it to a product record."""
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Only image files are allowed for products")

    contents = await file.read()
    if len(contents) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=400, detail="Image too large (max 10MB)")

    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    result = upload_image(contents, folder="racketek/products")

    if is_primary:
        db.query(ProductImage).filter(
            ProductImage.product_id == product_id,
            ProductImage.is_primary == True,
        ).update({"is_primary": False})

    img = ProductImage(
        product_id=product_id,
        url=result["url"],
        public_id=result["public_id"],
        alt_text=product.name,
        is_primary=is_primary,
    )
    db.add(img)
    db.commit()
    db.refresh(img)
    return {"url": img.url, "image_id": img.id, "public_id": img.public_id}


@router.delete("/product/image/{image_id}", status_code=204)
def delete_product_image(
    image_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    img = db.query(ProductImage).filter(ProductImage.id == image_id).first()
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")
    if img.public_id:
        delete_image(img.public_id)
    db.delete(img)
    db.commit()
