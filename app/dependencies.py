from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.models.user import UserRole


async def get_current_user(request) -> User:
    """Get the current authenticated user from request state."""
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user


async def require_auth(request):
    """Dependency for routes that require authentication."""
    user = getattr(request.state, "user", None)
    if user is None:
        # Will be handled by middleware to redirect to login
        raise HTTPException(
            status_code=status.HTTP_302_FOUND,
            headers={"Location": "/auth/login"},
        )
    return user


def require_roles(*roles):
    """Dependency factory to require specific roles."""
    async def check_roles(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user
    return check_roles


require_admin = require_roles(UserRole.ADMIN)
require_auditor_or_admin = require_roles(UserRole.ADMIN, UserRole.AUDITOR)
