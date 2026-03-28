"""Client management routes."""

from fastapi import APIRouter, Request, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse

from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Client
from app.models.user import UserRole
from app.repositories import ClientRepository

router = APIRouter(prefix="/clients", tags=["clients"])
from app.templates import templates
from app.utils.htmx import htmx_toast


def _require_admin(user) -> bool:
    """Return False (and caller should redirect) if user is not admin."""
    return user is not None and user.role == UserRole.ADMIN


@router.get("", response_class=HTMLResponse)
async def list_clients(
    request: Request, db: Session = Depends(get_db), industry: str | None = None, q: str | None = None
):
    """List all clients for the authenticated tenant with optional filtering."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    if not _require_admin(user):
        return RedirectResponse(url="/dashboard", status_code=302)

    repo = ClientRepository(db)

    # Use filter_clients with optional criteria
    clients = repo.filter_clients(user.tenant_id, industry=industry, search=q)

    # Check if this is an HTMX request (filter update)
    is_htmx = request.headers.get("HX-Request") == "true"

    if is_htmx:
        # Return just the table rows
        return templates.TemplateResponse(
            request,
            "clients/_clients_table.html",
            {
                "request": request,
                "user": user,
                "clients": clients,
            },
        )

    # Get distinct industries for filter dropdown
    distinct_industries = repo.get_distinct_industries(user.tenant_id)

    # Build active_filters dict for form pre-population
    active_filters = {
        "industry": industry or "",
        "q": q or "",
    }

    return templates.TemplateResponse(
        request,
        "clients/list.html",
        {
            "request": request,
            "user": user,
            "clients": clients,
            "distinct_industries": distinct_industries,
            "active_filters": active_filters,
        },
    )


@router.get("/new", response_class=HTMLResponse)
async def new_client_form(request: Request, db: Session = Depends(get_db)):
    """Show new client form modal."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    if not _require_admin(user):
        return RedirectResponse(url="/dashboard", status_code=302)

    return templates.TemplateResponse(
        request,
        "clients/_form.html",
        {
            "request": request,
            "user": user,
            "client": None,
        },
    )


@router.post("", response_class=HTMLResponse)
async def create_client(request: Request, db: Session = Depends(get_db)):
    """Create a new client."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    if not _require_admin(user):
        return RedirectResponse(url="/dashboard", status_code=302)

    form_data = await request.form()

    repo = ClientRepository(db)
    client = repo.create(
        tenant_id=user.tenant_id,
        name=form_data.get("name"),
        industry=form_data.get("industry"),
        contact_name=form_data.get("contact_name"),
        contact_email=form_data.get("contact_email"),
        notes=form_data.get("notes"),
    )

    return templates.TemplateResponse(
        request,
        "clients/_row.html",
        {
            "request": request,
            "user": user,
            "client": client,
        },
        headers=htmx_toast("Client created successfully")
    )


@router.post("/{client_id}", response_class=HTMLResponse)
async def update_client(
    client_id: str, request: Request, db: Session = Depends(get_db)
):
    """Update an existing client."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    if not _require_admin(user):
        return RedirectResponse(url="/dashboard", status_code=302)

    form_data = await request.form()

    repo = ClientRepository(db)
    client = repo.update(
        user.tenant_id,
        client_id,
        name=form_data.get("name"),
        industry=form_data.get("industry"),
        contact_name=form_data.get("contact_name"),
        contact_email=form_data.get("contact_email"),
        notes=form_data.get("notes"),
    )

    if not client:
        return RedirectResponse(url="/clients", status_code=302)

    return templates.TemplateResponse(
        request,
        "clients/_row.html",
        {
            "request": request,
            "user": user,
            "client": client,
        },
        headers=htmx_toast("Client updated successfully")
    )


@router.delete("/{client_id}", response_class=HTMLResponse)
async def delete_client(
    client_id: str, request: Request, db: Session = Depends(get_db)
):
    """Delete a client."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    if not _require_admin(user):
        return RedirectResponse(url="/dashboard", status_code=302)

    repo = ClientRepository(db)
    success = repo.delete(user.tenant_id, client_id)

    if success:
        return HTMLResponse("", headers=htmx_toast("Client deleted successfully"))
    return RedirectResponse(url="/clients", status_code=302)


@router.get("/search", response_class=HTMLResponse)
async def search_clients(
    request: Request, db: Session = Depends(get_db), q: str = ""
):
    """Search clients for autocomplete (HTMX endpoint)."""
    user = getattr(request.state, "user", None)
    if not user:
        return HTMLResponse("")

    repo = ClientRepository(db)
    results = repo.search(user.tenant_id, q) if q.strip() else []

    return templates.TemplateResponse(
        request,
        "clients/_search_results.html",
        {
            "request": request,
            "user": user,
            "results": results,
            "query": q,
        },
    )


@router.get("/{client_id}/edit", response_class=HTMLResponse)
async def edit_client_form_detail(
    client_id: str, request: Request, db: Session = Depends(get_db)
):
    """Show edit client form modal."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    if not _require_admin(user):
        return RedirectResponse(url="/dashboard", status_code=302)

    repo = ClientRepository(db)
    client = repo.get_by_id(user.tenant_id, client_id)

    if not client:
        return RedirectResponse(url="/clients", status_code=302)

    return templates.TemplateResponse(
        request,
        "clients/_form.html",
        {
            "request": request,
            "user": user,
            "client": client,
        },
    )


@router.get("/{client_id}", response_class=HTMLResponse)
async def detail_client(
    client_id: str, request: Request, db: Session = Depends(get_db)
):
    """Show client detail page."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    if not _require_admin(user):
        return RedirectResponse(url="/dashboard", status_code=302)

    repo = ClientRepository(db)
    client = repo.get_by_id(user.tenant_id, client_id)

    if not client:
        return RedirectResponse(url="/clients", status_code=302)

    return templates.TemplateResponse(
        request,
        "clients/detail.html",
        {
            "request": request,
            "user": user,
            "client": client,
        },
    )
