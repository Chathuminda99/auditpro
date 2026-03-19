import logging

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse

from sqlalchemy.orm import Session

from app.database import get_db
from app.config import get_settings
from app.logging_config import bind_log_context
from app.services.auth_service import authenticate_user, create_session_token

router = APIRouter(prefix="/auth", tags=["auth"])
from app.templates import templates
from app.utils.htmx import htmx_toast
settings = get_settings()
SECURITY_LOGGER = logging.getLogger("auditpro.security")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Render login page."""
    return templates.TemplateResponse("auth/login.html", {"request": request})


@router.post("/login", response_class=HTMLResponse)
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    """Handle login form submission."""
    normalized_email = email.strip().lower()
    user = authenticate_user(email, password, db)

    if not user:
        SECURITY_LOGGER.warning("login_failed email=%s", normalized_email)
        return templates.TemplateResponse(
            "auth/login.html",
            {
                "request": request,
                "error": "Invalid email or password",
            },
            status_code=401,
            headers=htmx_toast("Invalid email or password", "error")
        )

    # Create session token
    bind_log_context(user_id=user.id, tenant_id=user.tenant_id)
    SECURITY_LOGGER.info("login_success email=%s", user.email)
    token = create_session_token(user)

    # Create redirect response
    response = RedirectResponse(url="/dashboard", status_code=302)

    # Set session cookie
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_cookie_max_age,
        httponly=settings.session_cookie_httponly,
        samesite=settings.session_cookie_samesite,
        secure=settings.session_cookie_secure,
    )

    return response


@router.post("/logout")
async def logout(request: Request):
    """Handle logout."""
    user = getattr(request.state, "user", None)
    if user:
        bind_log_context(user_id=user.id, tenant_id=user.tenant_id)
        SECURITY_LOGGER.info("logout_success")
    else:
        SECURITY_LOGGER.info("logout_without_authenticated_user")

    response = RedirectResponse(url="/auth/login", status_code=302, headers=htmx_toast("Logged out successfully"))
    response.delete_cookie(
        key=settings.session_cookie_name,
        httponly=settings.session_cookie_httponly,
        samesite=settings.session_cookie_samesite,
        secure=settings.session_cookie_secure,
    )
    return response
