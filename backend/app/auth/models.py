from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy.orm import Mapped, relationship

from app.core.base import Base


class User(Base, SQLAlchemyBaseUserTableUUID):
    """사용자 모델"""
    __tablename__ = "users"

    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="user", uselist=False)