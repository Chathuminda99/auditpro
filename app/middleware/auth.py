import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.config import get_settings
from app.logging_config import bind_log_context
from app.services.auth_service import get_user_from_token

SECURITY_LOGGER = logging.getLogger("auditpro.security")


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware to decode session cookie and inject user into request state."""

    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        session_cookie_name = settings.session_cookie_name

        # Try to get session cookie
        session_token = request.cookies.get(session_cookie_name)
        user = None

        if session_token:
            # Decode token and load user
            user = await get_user_from_token(session_token)
            if user:
                bind_log_context(user_id=user.id, tenant_id=user.tenant_id)
            else:
                SECURITY_LOGGER.warning("invalid_or_expired_session_cookie")

        # Inject user into request state
        request.state.user = user

        return await call_next(request)
