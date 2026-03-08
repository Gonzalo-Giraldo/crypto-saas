from pydantic import BaseModel, EmailStr
from typing import Optional


class UserBase(BaseModel):
    email: str
    display_name: Optional[str] = None


class UserCreate(UserBase):
    email: EmailStr
    password: str


class UserOut(UserBase):
    id: str
    role: str
    risk_profile: Optional[str] = None
    risk_profile_source: Optional[str] = None

    class Config:
        from_attributes = True


class UserRoleUpdate(BaseModel):
    role: str
    reason: Optional[str] = None


class UserRiskProfileUpdate(BaseModel):
    profile_name: Optional[str] = None


class UserEmailUpdate(BaseModel):
    email: EmailStr
    reason: Optional[str] = None


class UserPasswordUpdate(BaseModel):
    new_password: str
    reason: Optional[str] = None


class User2FAResetOut(BaseModel):
    user_id: str
    email: str
    enabled: bool
    secret: str
    otpauth_uri: str
    message: str


class UserRiskSettingsOut(BaseModel):
    user_id: str
    capital_base_usd: float
    updated_at: Optional[str] = None


class UserRiskSettingsUpdate(BaseModel):
    capital_base_usd: float
