from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy.orm import Mapped, relationship

from app.core.base import Base


class User(Base, SQLAlchemyBaseUserTableUUID):
    """사용자 모델"""
    __tablename__ = "users"

    # Relationships
    settings: Mapped["UserSettings"] = relationship("UserSettings", back_populates="user", uselist=False)
    followed_issues = relationship("IssueFollow", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")