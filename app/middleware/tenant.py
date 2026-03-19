import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.database import SessionLocal
from app.logging_config import bind_log_context
from app.models import Tenant

APP_LOGGER = logging.getLogger("auditpro.app")


class TenantMiddleware(BaseHTTPMiddleware):
    """Middleware to inject tenant into request state from authenticated user."""

    async def dispatch(self, request: Request, call_next):
        tenant = None

        # Get user from request state (set by AuthMiddleware)
        user = getattr(request.state, "user", None)

        if user:
            # Load tenant from database
            db = SessionLocal()
            try:
                tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
            finally:
                db.close()

            if tenant:
                bind_log_context(tenant_id=tenant.id)
            else:
                APP_LOGGER.error(
                    "authenticated_user_missing_tenant user_id=%s",
                    user.id,
                )

        # Inject tenant into request state
        request.state.tenant = tenant

        return await call_next(request)
