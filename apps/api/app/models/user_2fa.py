from sqlalchemy import Boolean, Column, String

from apps.api.app.db.session import Base


class UserTwoFactor(Base):
    __tablename__ = "user_two_factor"

    user_id = Column(String, primary_key=True, index=True)
    secret = Column(String, nullable=False)
    key_version = Column(String, nullable=False, default="v1", server_default="v1")
    enabled = Column(Boolean, nullable=False, default=False)
