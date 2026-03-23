"""
Cloudinary upload utility — images and videos

M2 FIX: configure_cloudinary() is now a no-op. Configuration is applied
         once at application startup in main.py via cloudinary.config().
         Individual upload/delete functions no longer re-configure on every call.
"""
import cloudinary
import cloudinary.uploader


def upload_image(file_bytes: bytes, folder: str = "racketek", public_id: str = None) -> dict:
    """Upload image bytes → returns {url, public_id, width, height, bytes, resource_type}."""
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
    """Upload video bytes → returns {url, public_id, bytes, resource_type}."""
    opts: dict = {
        "folder": folder,
        "overwrite": True,
        "resource_type": "video",
        "chunk_size": 6_000_000,
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
    result = cloudinary.uploader.destroy(public_id, resource_type=resource_type)
    return result.get("result") == "ok"
