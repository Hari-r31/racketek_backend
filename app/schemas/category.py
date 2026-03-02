from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime


class CategoryCreate(BaseModel):
    name:             str
    slug:             str
    description:      Optional[str] = None
    image:            Optional[str] = None
    parent_id:        Optional[int] = None
    is_active:        bool = True
    sort_order:       int  = 0
    meta_title:       Optional[str] = None
    meta_description: Optional[str] = None


class CategoryUpdate(BaseModel):
    name:             Optional[str]  = None
    slug:             Optional[str]  = None
    description:      Optional[str]  = None
    image:            Optional[str]  = None
    parent_id:        Optional[int]  = None
    is_active:        Optional[bool] = None
    sort_order:       Optional[int]  = None
    meta_title:       Optional[str]  = None
    meta_description: Optional[str]  = None


class CategoryResponse(BaseModel):
    id:               int
    name:             str
    slug:             str
    description:      Optional[str]  = None
    image:            Optional[str]  = None          # raw DB field
    image_url:        Optional[str]  = None          # alias used by frontend
    parent_id:        Optional[int]  = None
    is_active:        bool
    sort_order:       int = 0
    meta_title:       Optional[str]  = None
    meta_description: Optional[str]  = None
    created_at:       datetime
    children:         List["CategoryResponse"] = []

    @validator("image_url", always=True, pre=False)
    def set_image_url(cls, v, values):
        """Expose `image` field also as `image_url` so frontend can use either."""
        return v or values.get("image")

    class Config:
        from_attributes = True


CategoryResponse.model_rebuild()
