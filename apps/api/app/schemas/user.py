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


class UserRiskProfileUpdate(BaseModel):
    profile_name: Optional[str] = None
