"""
Cloudinary upload utility — images and videos
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
    """Upload image bytes → returns {url, public_id, width, height, bytes}."""
    configure_cloudinary()
    opts: dict = {"folder": folder, "overwrite": True, "resource_type": "image"}
    if public_id:
        opts["public_id"] = public_id
    result = cloudinary.uploader.upload(file_bytes, **opts)
    return {
        "url":           result["secure_url"],
        "public_id":     result["public_id"],
        "width":         result.get("width"),
        "height":        result.get("height"),
        "bytes":         result.get("bytes"),
        "resource_type": "image",
    }


def upload_video(file_bytes: bytes, folder: str = "racketek/videos", public_id: str = None) -> dict:
    """Upload video bytes → returns {url, public_id}."""
    configure_cloudinary()
    opts: dict = {
        "folder": folder,
        "overwrite": True,
        "resource_type": "video",
        "chunk_size": 6000000,   # 6 MB chunks for large videos
    }
    if public_id:
        opts["public_id"] = public_id
    result = cloudinary.uploader.upload(file_bytes, **opts)
    return {
        "url":           result["secure_url"],
        "public_id":     result["public_id"],
        "bytes":         result.get("bytes"),
        "resource_type": "video",
    }


def delete_image(public_id: str, resource_type: str = "image") -> bool:
    configure_cloudinary()
    result = cloudinary.uploader.destroy(public_id, resource_type=resource_type)
    return result.get("result") == "ok"
