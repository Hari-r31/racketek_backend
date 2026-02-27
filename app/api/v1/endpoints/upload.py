"""
Image upload endpoint – Cloudinary
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, get_current_user, require_admin
from app.models.user import User
from app.models.product import Product, ProductImage
from app.utils.cloudinary_util import upload_image, delete_image

router = APIRouter()

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_SIZE = 5 * 1024 * 1024  # 5 MB


@router.post("/product/{product_id}")
async def upload_product_image(
    product_id: int,
    is_primary: bool = False,
    file: UploadFile = File(...),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Upload a product image to Cloudinary."""
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Only JPEG/PNG/WebP images are allowed")

    contents = await file.read()
    if len(contents) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")

    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    result = upload_image(contents, folder="racketek/products")

    if is_primary:
        # Unset existing primary
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
    return {"url": img.url, "image_id": img.id}


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
