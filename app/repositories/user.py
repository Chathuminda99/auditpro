"""User repository."""

from typing import List
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.user import User, UserRole
from app.repositories.base import BaseRepository
from app.utils.security import hash_password


class UserRepository(BaseRepository[User]):
    """Repository for User model."""

    model = User

    def __init__(self, db: Session):
        super().__init__(db)

    def get_all(self, tenant_id: UUID) -> List[User]:
        """Get all users for a tenant."""
        return (
            self.db.query(User)
            .filter(User.tenant_id == tenant_id)
            .order_by(User.full_name)
            .all()
        )

    def get_auditors(self, tenant_id: UUID) -> List[User]:
        """Get all auditor-role users for a tenant (for share modal)."""
        return (
            self.db.query(User)
            .filter(and_(User.tenant_id == tenant_id, User.role == UserRole.AUDITOR, User.is_active == True))
            .order_by(User.full_name)
            .all()
        )

    def search(self, tenant_id: UUID, q: str) -> List[User]:
        """Search auditors by name or email (for autocomplete)."""
        term = f"%{q.lower()}%"
        return (
            self.db.query(User)
            .filter(
                and_(
                    User.tenant_id == tenant_id,
                    User.role == UserRole.AUDITOR,
                    User.is_active == True,
                    (User.full_name.ilike(term) | User.email.ilike(term)),
                )
            )
            .limit(10)
            .all()
        )

    def get_by_email(self, email: str) -> User | None:
        """Get a user by email (global — email must be unique)."""
        return self.db.query(User).filter(User.email == email).first()

    def create_user(
        self,
        tenant_id: UUID,
        email: str,
        full_name: str,
        role: UserRole,
        password: str,
    ) -> User:
        """Create a new user with a hashed password."""
        user = User(
            tenant_id=tenant_id,
            email=email,
            full_name=full_name,
            role=role,
            password_hash=hash_password(password),
            is_active=True,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_user(
        self,
        tenant_id: UUID,
        user_id: UUID,
        full_name: str | None = None,
        role: UserRole | None = None,
        is_active: bool | None = None,
    ) -> User | None:
        """Update user fields."""
        user = (
            self.db.query(User)
            .filter(and_(User.id == user_id, User.tenant_id == tenant_id))
            .first()
        )
        if not user:
            return None
        if full_name is not None:
            user.full_name = full_name
        if role is not None:
            user.role = role
        if is_active is not None:
            user.is_active = is_active
        self.db.commit()
        self.db.refresh(user)
        return user
