from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from app.models.user import UserRole


class UserCreate(BaseModel):
    full_name: str  = Field(..., min_length=2, max_length=150)
    email:     EmailStr
    phone:     Optional[str] = None
    password:  str  = Field(..., min_length=6, max_length=100)


class UserLogin(BaseModel):
    email:    EmailStr
    password: str


class UserUpdate(BaseModel):
    full_name:     Optional[str] = None
    phone:         Optional[str] = None
    profile_image: Optional[str] = None


class OAuthGoogleRequest(BaseModel):
    id_token:  str
    full_name: Optional[str] = None
    phone:     Optional[str] = None


class UserResponse(BaseModel):
    id:               int
    full_name:        str
    email:            str
    phone:            Optional[str]
    role:             UserRole
    is_active:        bool
    is_email_verified: bool
    profile_image:    Optional[str]
    date_of_birth:    Optional[str] = None
    address_line1:    Optional[str] = None
    city:             Optional[str] = None
    state:            Optional[str] = None
    pincode:          Optional[str] = None
    created_at:       datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token:  str
    refresh_token: str
    token_type:    str  = "bearer"
    user:          UserResponse
    is_new_user:   bool = False


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password:     str = Field(..., min_length=6, max_length=100)


class RequestEmailVerificationRequest(BaseModel):
    """No body needed — uses the authenticated user's email."""
    pass


class VerifyEmailRequest(BaseModel):
    otp: str = Field(..., min_length=4, max_length=10)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token:        str
    new_password: str = Field(..., min_length=6, max_length=100)
