import uuid
from enum import Enum
from sqlalchemy import String, Boolean, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel, TimestampMixin


class UserRole(str, Enum):
    """User role enumeration."""

    ADMIN = "admin"
    AUDITOR = "auditor"


class User(BaseModel, TimestampMixin):
    """User account model."""

    __tablename__ = "users"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=UserRole.AUDITOR,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
