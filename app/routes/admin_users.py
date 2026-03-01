"""User management routes (admin only)."""

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse

from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import UserRole
from app.repositories.user import UserRepository
from app.templates import templates
from app.utils.htmx import htmx_toast

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


def _require_admin(user):
    """Return True only if user is admin."""
    return user is not None and user.role == UserRole.ADMIN


@router.get("", response_class=HTMLResponse)
async def list_users(request: Request, db: Session = Depends(get_db)):
    """List all users in the tenant (admin only)."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    if not _require_admin(user):
        return RedirectResponse(url="/dashboard", status_code=302)

    repo = UserRepository(db)
    users = repo.get_all(user.tenant_id)

    is_htmx = request.headers.get("HX-Request") == "true"
    if is_htmx:
        return templates.TemplateResponse(
            "admin/_users_table.html",
            {"request": request, "user": user, "users": users},
        )

    return templates.TemplateResponse(
        "admin/users.html",
        {"request": request, "user": user, "users": users},
    )


@router.get("/search", response_class=HTMLResponse)
async def search_users(request: Request, db: Session = Depends(get_db), q: str = ""):
    """Search auditor users for autocomplete (admin or project owner)."""
    user = getattr(request.state, "user", None)
    if not user:
        return HTMLResponse("")

    repo = UserRepository(db)
    results = repo.search(user.tenant_id, q) if q.strip() else []

    return templates.TemplateResponse(
        "admin/_users_search_results.html",
        {"request": request, "user": user, "results": results},
    )


@router.get("/new", response_class=HTMLResponse)
async def new_user_form(request: Request, db: Session = Depends(get_db)):
    """Show create-user form modal (admin only)."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    if not _require_admin(user):
        return RedirectResponse(url="/dashboard", status_code=302)

    return templates.TemplateResponse(
        "admin/_user_form.html",
        {"request": request, "user": user, "edit_user": None},
    )


@router.post("", response_class=HTMLResponse)
async def create_user(request: Request, db: Session = Depends(get_db)):
    """Create a new user (admin only)."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    if not _require_admin(user):
        return RedirectResponse(url="/dashboard", status_code=302)

    form = await request.form()
    email = (form.get("email") or "").strip()
    full_name = (form.get("full_name") or "").strip()
    role_value = (form.get("role") or UserRole.AUDITOR.value).strip()
    password = (form.get("password") or "").strip()

    if not email or not full_name or not password:
        return templates.TemplateResponse(
            "admin/_user_form.html",
            {
                "request": request,
                "user": user,
                "edit_user": None,
                "error": "Email, name, and password are required.",
            },
        )

    try:
        role = UserRole(role_value)
    except ValueError:
        role = UserRole.AUDITOR

    repo = UserRepository(db)

    # Check email uniqueness
    existing = repo.get_by_email(email)
    if existing:
        return templates.TemplateResponse(
            "admin/_user_form.html",
            {
                "request": request,
                "user": user,
                "edit_user": None,
                "error": "A user with that email already exists.",
            },
        )

    repo.create_user(
        tenant_id=user.tenant_id,
        email=email,
        full_name=full_name,
        role=role,
        password=password,
    )

    users = repo.get_all(user.tenant_id)
    return templates.TemplateResponse(
        "admin/_users_table.html",
        {"request": request, "user": user, "users": users},
        headers=htmx_toast("User created successfully"),
    )


@router.get("/{user_id}/edit", response_class=HTMLResponse)
async def edit_user_form(user_id: str, request: Request, db: Session = Depends(get_db)):
    """Show edit-user form modal (admin only)."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    if not _require_admin(user):
        return RedirectResponse(url="/dashboard", status_code=302)

    repo = UserRepository(db)
    edit_user = repo.get_by_id(user.tenant_id, user_id)
    if not edit_user:
        return RedirectResponse(url="/admin/users", status_code=302)

    return templates.TemplateResponse(
        "admin/_user_form.html",
        {"request": request, "user": user, "edit_user": edit_user},
    )


@router.post("/{user_id}", response_class=HTMLResponse)
async def update_user(user_id: str, request: Request, db: Session = Depends(get_db)):
    """Update a user's role, name, or active status (admin only)."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    if not _require_admin(user):
        return RedirectResponse(url="/dashboard", status_code=302)

    form = await request.form()
    full_name = (form.get("full_name") or "").strip() or None
    role_value = (form.get("role") or "").strip()
    is_active_str = form.get("is_active", "on")

    role = None
    if role_value:
        try:
            role = UserRole(role_value)
        except ValueError:
            pass

    is_active = is_active_str in ("on", "true", "1", "yes")

    repo = UserRepository(db)
    repo.update_user(
        tenant_id=user.tenant_id,
        user_id=user_id,
        full_name=full_name,
        role=role,
        is_active=is_active,
    )

    users = repo.get_all(user.tenant_id)
    return templates.TemplateResponse(
        "admin/_users_table.html",
        {"request": request, "user": user, "users": users},
        headers=htmx_toast("User updated successfully"),
    )
