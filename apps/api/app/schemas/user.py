from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    email: EmailStr
    display_name: str

class UserOut(BaseModel):
    id: str
    email: EmailStr
    display_name: str
    is_active: bool

    class Config:
        from_attributes = True

