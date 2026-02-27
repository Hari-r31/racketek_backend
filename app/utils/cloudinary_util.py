"""
Cloudinary image upload utility
"""
import cloudinary
import cloudinary.uploader
from app.core.config import settings


def configure_cloudinary():
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
    )


def upload_image(file_bytes: bytes, folder: str = "racketek", public_id: str = None) -> dict:
    """Upload image bytes to Cloudinary. Returns {url, public_id}."""
    configure_cloudinary()
    opts = {"folder": folder, "overwrite": True}
    if public_id:
        opts["public_id"] = public_id
    result = cloudinary.uploader.upload(file_bytes, **opts)
    return {"url": result["secure_url"], "public_id": result["public_id"]}


def delete_image(public_id: str) -> bool:
    configure_cloudinary()
    result = cloudinary.uploader.destroy(public_id)
    return result.get("result") == "ok"
