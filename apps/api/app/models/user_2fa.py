from sqlalchemy import Boolean, Column, String

from apps.api.app.db.session import Base


class UserTwoFactor(Base):
    __tablename__ = "user_two_factor"

    user_id = Column(String, primary_key=True, index=True)
    secret = Column(String, nullable=False)
    enabled = Column(Boolean, nullable=False, default=False)
