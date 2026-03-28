import json
import logging
import secrets

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse

from sqlalchemy.orm import Session

from app.database import get_db
from app.config import get_settings
from app.logging_config import bind_log_context
from app.services.auth_service import (
    authenticate_user,
    create_session_token,
    exchange_azure_code,
    get_or_create_azure_user,
    initiate_azure_flow,
)
from app.utils.security import session_manager

router = APIRouter(prefix="/auth", tags=["auth"])
from app.templates import templates
from app.utils.htmx import htmx_toast
settings = get_settings()
SECURITY_LOGGER = logging.getLogger("auditpro.security")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Render login page."""
    return templates.TemplateResponse(
        request,
        "auth/login.html",
        {"request": request, "azure_ad_enabled": settings.azure_ad_enabled},
    )


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
            request,
            "auth/login.html",
            {
                "request": request,
                "error": "Invalid email or password",
                "azure_ad_enabled": settings.azure_ad_enabled,
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


@router.get("/azure/login")
async def azure_login(request: Request):
    """Initiate Azure AD OAuth2 flow."""
    if not settings.azure_ad_enabled:
        return RedirectResponse(url="/auth/login", status_code=302)

    flow = initiate_azure_flow()
    signed_flow = session_manager.create_token({"flow": json.dumps(flow)})

    response = RedirectResponse(url=flow["auth_uri"], status_code=302)
    response.set_cookie(
        key="az_oauth_state",
        value=signed_flow,
        max_age=600,
        httponly=True,
        samesite="Lax",
        secure=settings.session_cookie_secure,
    )
    return response


@router.get("/azure/callback")
async def azure_callback(
    request: Request,
    db: Session = Depends(get_db),
    error: str = None,
):
    """Handle Azure AD OAuth2 callback."""
    # Always clean up state cookie in response
    def _error_redirect(msg: str):
        resp = RedirectResponse(url="/auth/login", status_code=302, headers=htmx_toast(msg, "error"))
        resp.delete_cookie("az_oauth_state")
        return resp

    if error:
        error_description = request.query_params.get("error_description", "")
        SECURITY_LOGGER.warning("azure_callback_error error=%s description=%s", error, error_description)
        return _error_redirect("Microsoft sign-in failed. Please try again.")

    # Verify state
    signed_state = request.cookies.get("az_oauth_state")
    if not signed_state:
        return _error_redirect("Session expired. Please try again.")

    flow_data = session_manager.decode_token(signed_state)
    if not flow_data or not flow_data.get("flow"):
        SECURITY_LOGGER.warning("azure_callback_invalid_flow_cookie")
        return _error_redirect("Session expired. Please try again.")

    try:
        flow = json.loads(flow_data["flow"])
    except (ValueError, KeyError):
        return _error_redirect("Session expired. Please try again.")

    # Build auth_response from all callback query params (MSAL validates state internally)
    auth_response = dict(request.query_params)

    # Exchange code for tokens
    claims = exchange_azure_code(flow, auth_response)
    if not claims:
        SECURITY_LOGGER.warning("azure_callback_token_exchange_failed")
        return _error_redirect("Failed to authenticate with Microsoft. Please try again.")

    user = get_or_create_azure_user(claims, db)

    if not user.is_active:
        resp = RedirectResponse(url="/auth/pending", status_code=302)
        resp.delete_cookie("az_oauth_state")
        return resp

    SECURITY_LOGGER.info("azure_login_success email=%s", user.email)
    token = create_session_token(user)

    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_cookie_max_age,
        httponly=settings.session_cookie_httponly,
        samesite=settings.session_cookie_samesite,
        secure=settings.session_cookie_secure,
    )
    response.delete_cookie("az_oauth_state")
    return response


@router.get("/pending", response_class=HTMLResponse)
async def pending_approval(request: Request):
    """Show pending approval page for new Azure AD users."""
    # If already authenticated and active, redirect to dashboard
    user = getattr(request.state, "user", None)
    if user and user.is_active:
        return RedirectResponse(url="/dashboard", status_code=302)

    return templates.TemplateResponse(request, "auth/pending_approval.html", {})
