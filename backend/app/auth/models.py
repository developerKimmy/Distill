from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base


class User(Base, SQLAlchemyBaseUserTableUUID):
    """사용자 모델"""
    __tablename__ = "users"

    has_workspace: Mapped[bool] = mapped_column(default=False)

    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="user", uselist=False)