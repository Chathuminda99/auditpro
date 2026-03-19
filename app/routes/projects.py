"""Project management routes."""

import uuid
import os
import shutil
from pathlib import Path
from fastapi import APIRouter, Request, Depends, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse

from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Project, ProjectStatus
from app.models.project import ResponseStatus, ProjectType
from app.models.health_check import ControlInstanceStatus
from app.models.workflow import WorkflowExecutionStatus
from app.repositories import (
    ProjectRepository,
    ClientRepository,
    FrameworkRepository,
    ProjectResponseRepository,
    WorkflowExecutionRepository,
    UserRepository,
    HealthCheckRepository,
)
from app.models.project import ProjectMember
from app.models.user import UserRole
from app.services import workflow_engine

router = APIRouter(prefix="/projects", tags=["projects"])
from app.templates import templates
from app.utils.htmx import htmx_toast


def compute_review_scope_rollup(stats: dict) -> str:
    """Derive a single PASS/FAIL/IN_PROGRESS/NOT_STARTED verdict from aggregated stats.

    Rules (in priority order):
    - "fail"        — if any control instance is FAIL
    - "pass"        — if nothing is not_started or in_progress (all resolved: pass+na)
    - "in_progress" — if some are pass/in_progress but not all resolved
    - "not_started" — if no sessions exist or everything is not_started
    """
    if stats.get("fail", 0) > 0:
        return "fail"
    total = sum(stats.values())
    if total == 0:
        return "not_started"
    unresolved = stats.get("not_started", 0) + stats.get("in_progress", 0)
    if unresolved == 0:
        return "pass"
    if stats.get("pass", 0) > 0 or stats.get("in_progress", 0) > 0:
        return "in_progress"
    return "not_started"


@router.get("", response_class=HTMLResponse)
async def list_projects(
    request: Request,
    db: Session = Depends(get_db),
    status: str | None = None,
    client_id: str | None = None,
    framework_id: str | None = None,
    q: str | None = None,
):
    """List all projects for the authenticated tenant with optional filtering."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    repo = ProjectRepository(db)

    # Convert status string to enum if provided
    status_enum = None
    if status and status.strip():
        try:
            status_enum = ProjectStatus(status)
        except ValueError:
            pass

    # Use filter_projects with optional criteria (auditors see only own projects)
    projects = repo.filter_projects(
        user.tenant_id,
        status=status_enum,
        client_id=client_id if client_id and client_id.strip() else None,
        framework_id=framework_id if framework_id and framework_id.strip() else None,
        search=q,
        user=user,
    )

    # Check if this is an HTMX request (filter update)
    is_htmx = request.headers.get("HX-Request") == "true"

    if is_htmx:
        # Return just the table rows
        return templates.TemplateResponse(
            "projects/_projects_table.html",
            {
                "request": request,
                "user": user,
                "projects": projects,
            },
        )

    # Get available filters for the form
    client_repo = ClientRepository(db)
    framework_repo = FrameworkRepository(db)
    all_clients = client_repo.get_all(user.tenant_id)
    all_frameworks = framework_repo.get_all(user.tenant_id)

    # Build active_filters dict for form pre-population
    active_filters = {
        "status": status or "",
        "client_id": client_id or "",
        "framework_id": framework_id or "",
        "q": q or "",
    }

    return templates.TemplateResponse(
        "projects/list.html",
        {
            "request": request,
            "user": user,
            "projects": projects,
            "all_clients": all_clients,
            "all_frameworks": all_frameworks,
            "active_filters": active_filters,
        },
    )


@router.get("/new", response_class=HTMLResponse)
async def new_project_form(request: Request, db: Session = Depends(get_db)):
    """Show new project form modal."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    client_repo = ClientRepository(db)
    framework_repo = FrameworkRepository(db)

    clients = client_repo.get_all(user.tenant_id)
    frameworks = framework_repo.get_all(user.tenant_id)

    return templates.TemplateResponse(
        "projects/new.html",
        {
            "request": request,
            "user": user,
            "project": None,
            "clients": clients,
            "frameworks": frameworks,
        },
    )


@router.post("", response_class=HTMLResponse)
async def create_project(request: Request, db: Session = Depends(get_db)):
    """Create a new project."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    form_data = await request.form()

    # Validate required fields
    client_id = (form_data.get("client_id") or "").strip()
    framework_id = (form_data.get("framework_id") or "").strip()
    name = (form_data.get("name") or "").strip()

    if not client_id or not framework_id or not name:
        # Return to form with error (for now, just redirect)
        return RedirectResponse(url="/projects/new", status_code=302)

    status_value = form_data.get("status", ProjectStatus.DRAFT.value)
    try:
        status = ProjectStatus(status_value)
    except ValueError:
        status = ProjectStatus.DRAFT

    # Parse project type
    project_type_value = form_data.get("project_type", "standard_audit")
    try:
        project_type = ProjectType(project_type_value)
    except ValueError:
        project_type = ProjectType.STANDARD_AUDIT

    repo = ProjectRepository(db)
    project = repo.create(
        tenant_id=user.tenant_id,
        client_id=client_id,
        framework_id=framework_id,
        name=name,
        description=form_data.get("description", ""),
        status=status,
        owner_id=user.id,
        project_type=project_type,
    )

    # Refresh to get related objects
    db.refresh(project, ["client", "framework"])

    # Auto-add review scopes for PCI DSS Health Check projects
    if project_type == ProjectType.PCI_DSS_HEALTH_CHECK:
        hc_repo = HealthCheckRepository(db)
        review_scope_types = hc_repo.get_review_scope_types_for_framework(project.framework_id)
        for i, review_scope_type in enumerate(review_scope_types):
            hc_repo.add_review_scope_to_project(project.id, review_scope_type.id, sort_order=i)

    # Redirect isn't natively caught by HTMX headers, so we set a cookie or
    # use hx-redirect instead, but since we're using RedirectResponse it will be a 200 via HTMX's transparent redirect.
    return RedirectResponse(
        url=f"/projects/{project.id}",
        status_code=303,
        headers=htmx_toast("Project created successfully")
    )


@router.get("/{project_id}/edit", response_class=HTMLResponse)
async def edit_project_form(
    project_id: str, request: Request, db: Session = Depends(get_db)
):
    """Show edit project form modal."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    repo = ProjectRepository(db)
    project = repo.get_by_id_with_details(user.tenant_id, project_id)

    if not project:
        return RedirectResponse(url="/projects", status_code=302)

    client_repo = ClientRepository(db)
    framework_repo = FrameworkRepository(db)

    clients = client_repo.get_all(user.tenant_id)
    frameworks = framework_repo.get_all(user.tenant_id)

    return templates.TemplateResponse(
        "projects/_form.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "clients": clients,
            "frameworks": frameworks,
        },
    )


@router.post("/{project_id}", response_class=HTMLResponse)
async def update_project(
    project_id: str, request: Request, db: Session = Depends(get_db)
):
    """Update an existing project."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    form_data = await request.form()

    # Validate required fields
    client_id = (form_data.get("client_id") or "").strip()
    framework_id = (form_data.get("framework_id") or "").strip()
    name = (form_data.get("name") or "").strip()

    if not client_id or not framework_id or not name:
        # Return to form with error (for now, just redirect)
        return RedirectResponse(url=f"/projects/{project_id}/edit", status_code=302)

    status_value = form_data.get("status", ProjectStatus.DRAFT.value)
    try:
        status = ProjectStatus(status_value)
    except ValueError:
        status = ProjectStatus.DRAFT

    repo = ProjectRepository(db)
    project = repo.update(
        user.tenant_id,
        project_id,
        name=name,
        description=form_data.get("description", ""),
        client_id=client_id,
        framework_id=framework_id,
        status=status,
    )

    if not project:
        return RedirectResponse(url="/projects", status_code=302)

    # Refresh to get related objects
    db.refresh(project, ["client", "framework"])

    return templates.TemplateResponse(
        "projects/_row.html",
        {
            "request": request,
            "user": user,
            "project": project,
        },
        headers=htmx_toast("Project updated successfully")
    )


@router.delete("/{project_id}", response_class=HTMLResponse)
async def delete_project(
    project_id: str, request: Request, db: Session = Depends(get_db)
):
    """Delete a project."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    repo = ProjectRepository(db)
    success = repo.delete(user.tenant_id, project_id)

    if success:
        return HTMLResponse("", headers=htmx_toast("Project deleted successfully"))
    return RedirectResponse(url="/projects", status_code=302)


@router.get("/{project_id}/segments/new", response_class=HTMLResponse)
async def new_segment_form(
    project_id: str, request: Request, db: Session = Depends(get_db)
):
    """Show new segment form modal."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    repo = ProjectRepository(db)
    project = repo.get_by_id_with_details(user.tenant_id, project_id)

    if not project:
        return RedirectResponse(url="/projects", status_code=302)

    return templates.TemplateResponse(
        "projects/_segment_form.html",
        {
            "request": request,
            "user": user,
            "project": project,
        },
    )


@router.post("/{project_id}/segments", response_class=HTMLResponse)
async def create_segment(
    project_id: str, request: Request, db: Session = Depends(get_db)
):
    """Create a new segment under a project."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    repo = ProjectRepository(db)
    project = repo.get_by_id_with_details(user.tenant_id, project_id)

    if not project:
        return RedirectResponse(url="/projects", status_code=302)

    form_data = await request.form()
    name = (form_data.get("name") or "").strip()
    description = form_data.get("description", "")

    if not name:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    segment = repo.create_segment(user.tenant_id, project_id, name, description)

    return templates.TemplateResponse(
        "projects/_segment_row.html",
        {
            "request": request,
            "user": user,
            "parent_project": project,
            "segment": segment,
            "total_controls": 0,
            "responded_count": 0,
            "progress_pct": 0,
        },
        headers=htmx_toast("Segment created successfully")
    )


@router.delete("/{project_id}/segments/{segment_id}", response_class=HTMLResponse)
async def delete_segment(
    project_id: str, segment_id: str, request: Request, db: Session = Depends(get_db)
):
    """Delete a segment (sub-project)."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    repo = ProjectRepository(db)
    success = repo.delete(user.tenant_id, segment_id)

    if success:
        return HTMLResponse("", headers=htmx_toast("Segment deleted successfully"))
    return RedirectResponse(url=f"/projects/{project_id}", status_code=302)


@router.get("/{project_id}/review-scopes/add", response_class=HTMLResponse)
async def add_review_scope_modal(
    project_id: str, request: Request, db: Session = Depends(get_db)
):
    """Get the add-review-scope modal content."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    repo = ProjectRepository(db)
    project = repo.get_by_id_with_details(user.tenant_id, project_id)

    if not project:
        return RedirectResponse(url="/projects", status_code=302)

    hc_repo = HealthCheckRepository(db)
    unadded_review_scope_types = hc_repo.get_unadded_review_scope_types(project.id, project.framework_id)

    return templates.TemplateResponse(
        "projects/health_check/_add_review_scope_modal.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "unadded_review_scope_types": unadded_review_scope_types,
        },
    )


@router.post("/{project_id}/review-scopes", response_class=HTMLResponse)
async def add_review_scope(
    project_id: str, request: Request, db: Session = Depends(get_db)
):
    """Add a review scope to a health check project."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    form_data = await request.form()
    review_scope_type_id = (form_data.get("review_scope_type_id") or "").strip()

    repo = ProjectRepository(db)
    project = repo.get_by_id_with_details(user.tenant_id, project_id)

    if not project:
        return RedirectResponse(url="/projects", status_code=302)

    hc_repo = HealthCheckRepository(db)
    hc_repo.add_review_scope_to_project(project.id, review_scope_type_id)

    # Re-render the review-scope grid
    review_scopes = hc_repo.get_review_scopes_for_project(project.id)

    # Compute review-scope stats
    review_scope_stats = {}
    for review_scope in review_scopes:
        stats = {s.value: 0 for s in ControlInstanceStatus}
        for session in review_scope.sessions:
            for inst in session.control_instances:
                stats[inst.status.value] = stats.get(inst.status.value, 0) + 1
        review_scope_stats[str(review_scope.id)] = stats

    # Review-scope rollup
    review_scope_rollup = {str(d.id): compute_review_scope_rollup(review_scope_stats[str(d.id)]) for d in review_scopes}

    return templates.TemplateResponse(
        "projects/health_check/_review_scopes_grid.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "review_scopes": review_scopes,
            "review_scope_stats": review_scope_stats,
            "review_scope_rollup": review_scope_rollup,
        },
        headers=htmx_toast("Review scope added successfully")
    )


@router.delete("/{project_id}/review-scopes/{review_scope_id}", response_class=HTMLResponse)
async def remove_review_scope(
    project_id: str, review_scope_id: str, request: Request, db: Session = Depends(get_db)
):
    """Remove a review scope from a health check project."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    repo = ProjectRepository(db)
    project = repo.get_by_id_with_details(user.tenant_id, project_id)

    if not project:
        return RedirectResponse(url="/projects", status_code=302)

    hc_repo = HealthCheckRepository(db)
    review_scope = hc_repo.get_review_scope_by_id(review_scope_id)

    # Security check: verify the review scope belongs to this project
    if not review_scope or review_scope.project_id != project.id:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    hc_repo.remove_review_scope(review_scope_id)

    # Re-render the review-scope grid
    review_scopes = hc_repo.get_review_scopes_for_project(project.id)

    # Compute review-scope stats
    review_scope_stats = {}
    for review_scope in review_scopes:
        stats = {s.value: 0 for s in ControlInstanceStatus}
        for session in review_scope.sessions:
            for inst in session.control_instances:
                stats[inst.status.value] = stats.get(inst.status.value, 0) + 1
        review_scope_stats[str(review_scope.id)] = stats

    # Review-scope rollup
    review_scope_rollup = {str(d.id): compute_review_scope_rollup(review_scope_stats[str(d.id)]) for d in review_scopes}

    return templates.TemplateResponse(
        "projects/health_check/_review_scopes_grid.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "review_scopes": review_scopes,
            "review_scope_stats": review_scope_stats,
            "review_scope_rollup": review_scope_rollup,
        },
        headers=htmx_toast("Review scope removed successfully")
    )


# === Session Management ===


@router.get("/{project_id}/download-evidence/{evidence_id}", response_class=FileResponse)
async def download_evidence(
    project_id: str, evidence_id: str, request: Request, db: Session = Depends(get_db)
):
    """Download an evidence file."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    repo = ProjectRepository(db)
    project = repo.get_by_id_with_details(user.tenant_id, uuid.UUID(project_id))

    if not project:
        return RedirectResponse(url="/projects", status_code=302)

    hc_repo = HealthCheckRepository(db)
    evidence = hc_repo.get_evidence_by_id(uuid.UUID(evidence_id))

    if not evidence or evidence.control_instance.audit_session.project_id != project.id:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    if evidence.evidence_type != "file" or not evidence.file_path:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    file_path = evidence.file_path.lstrip("/")
    if not os.path.exists(file_path):
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    return FileResponse(
        path=file_path,
        filename=evidence.filename,
        media_type="application/octet-stream",
    )


@router.get("/{project_id}/review-scopes/{review_scope_id}", response_class=HTMLResponse)
async def review_scope_detail(
    project_id: str, review_scope_id: str, request: Request, db: Session = Depends(get_db)
):
    """Show the review-scope detail page with its sessions."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    repo = ProjectRepository(db)
    project = repo.get_by_id_with_details(user.tenant_id, uuid.UUID(project_id))

    if not project:
        return RedirectResponse(url="/projects", status_code=302)

    hc_repo = HealthCheckRepository(db)
    review_scope = hc_repo.get_review_scope_with_sessions(uuid.UUID(review_scope_id))

    if not review_scope or review_scope.project_id != project.id:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    # Compute per-session stats
    session_stats = {}
    for session in review_scope.sessions:
        session_stats[str(session.id)] = hc_repo.get_session_stats(session.id)

    # Aggregate review-scope stats for the rollup
    aggregate_stats = {s.value: 0 for s in ControlInstanceStatus}
    for sess_stats in session_stats.values():
        for k, v in sess_stats.items():
            aggregate_stats[k] = aggregate_stats.get(k, 0) + v
    rollup_status = compute_review_scope_rollup(aggregate_stats)

    breadcrumbs = [
        {"label": "Projects", "url": "/projects"},
        {"label": project.name, "url": f"/projects/{project.id}"},
        {"label": review_scope.label or review_scope.review_scope_type.name, "url": None},
    ]

    return templates.TemplateResponse(
        "projects/health_check/review_scope_detail.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "review_scope": review_scope,
            "session_stats": session_stats,
            "rollup_status": rollup_status,
            "breadcrumbs": breadcrumbs,
        },
    )


@router.get("/{project_id}/review-scopes/{review_scope_id}/sessions/new", response_class=HTMLResponse)
async def add_session_modal(
    project_id: str, review_scope_id: str, request: Request, db: Session = Depends(get_db)
):
    """Get add session modal content."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    repo = ProjectRepository(db)
    project = repo.get_by_id_with_details(user.tenant_id, uuid.UUID(project_id))

    if not project:
        return RedirectResponse(url="/projects", status_code=302)

    hc_repo = HealthCheckRepository(db)
    review_scope = hc_repo.get_review_scope_by_id(uuid.UUID(review_scope_id))

    if not review_scope or review_scope.project_id != project.id:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    return templates.TemplateResponse(
        "projects/health_check/_add_session_modal.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "review_scope": review_scope,
        },
    )


@router.post("/{project_id}/review-scopes/{review_scope_id}/sessions", response_class=HTMLResponse)
async def create_session(
    project_id: str, review_scope_id: str, request: Request, db: Session = Depends(get_db)
):
    """Create a new session under a review scope."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    repo = ProjectRepository(db)
    project = repo.get_by_id_with_details(user.tenant_id, uuid.UUID(project_id))

    if not project:
        return RedirectResponse(url="/projects", status_code=302)

    hc_repo = HealthCheckRepository(db)
    review_scope = hc_repo.get_review_scope_by_id(uuid.UUID(review_scope_id))

    if not review_scope or review_scope.project_id != project.id:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    form_data = await request.form()
    name = (form_data.get("name") or "").strip()

    if not name:
        return RedirectResponse(url=f"/projects/{project_id}/review-scopes/{review_scope_id}", status_code=302)

    asset_identifier = form_data.get("asset_identifier", "").strip() or None
    description = form_data.get("description", "").strip() or None

    # Create session
    session = hc_repo.create_session(
        review_scope_id=uuid.UUID(review_scope_id),
        project_id=uuid.UUID(project_id),
        name=name,
        asset_identifier=asset_identifier,
        description=description,
    )

    # Seed control instances for this review scope's type
    control_count = hc_repo.seed_control_instances(session, review_scope.review_scope_type_id)

    # Reload the review scope and compute stats
    review_scope = hc_repo.get_review_scope_with_sessions(uuid.UUID(review_scope_id))
    session_stats = {}
    for s in review_scope.sessions:
        session_stats[str(s.id)] = hc_repo.get_session_stats(s.id)

    response = templates.TemplateResponse(
        "projects/health_check/_sessions_list.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "review_scope": review_scope,
            "session_stats": session_stats,
        },
    )
    response.headers["HX-Redirect"] = f"/projects/{project_id}/review-scopes/{review_scope_id}/sessions/{session.id}"
    response.headers.update(htmx_toast(f"Session created with {control_count} controls"))
    return response


@router.delete("/{project_id}/review-scopes/{review_scope_id}/sessions/{session_id}", response_class=HTMLResponse)
async def delete_session(
    project_id: str, review_scope_id: str, session_id: str, request: Request, db: Session = Depends(get_db)
):
    """Delete a session from a review scope."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    repo = ProjectRepository(db)
    project = repo.get_by_id_with_details(user.tenant_id, uuid.UUID(project_id))

    if not project:
        return RedirectResponse(url="/projects", status_code=302)

    hc_repo = HealthCheckRepository(db)
    review_scope = hc_repo.get_review_scope_by_id(uuid.UUID(review_scope_id))

    if not review_scope or review_scope.project_id != project.id:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    # Verify session belongs to this review scope
    session = hc_repo.get_session_by_id(uuid.UUID(session_id))
    if not session or session.review_scope_id != review_scope.id:
        return RedirectResponse(url=f"/projects/{project_id}/review-scopes/{review_scope_id}", status_code=302)

    hc_repo.delete_session(uuid.UUID(session_id))

    # Reload the review scope and compute stats
    review_scope = hc_repo.get_review_scope_with_sessions(uuid.UUID(review_scope_id))
    session_stats = {}
    for s in review_scope.sessions:
        session_stats[str(s.id)] = hc_repo.get_session_stats(s.id)

    return templates.TemplateResponse(
        "projects/health_check/_sessions_list.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "review_scope": review_scope,
            "session_stats": session_stats,
        },
        headers=htmx_toast("Session deleted"),
    )


@router.get("/{project_id}/review-scopes/{review_scope_id}/sessions/{session_id}", response_class=HTMLResponse)
async def session_detail(
    project_id: str, review_scope_id: str, session_id: str, request: Request, db: Session = Depends(get_db)
):
    """Show session detail page with two-panel control assessment."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    repo = ProjectRepository(db)
    project = repo.get_by_id_with_details(user.tenant_id, uuid.UUID(project_id))

    if not project:
        return RedirectResponse(url="/projects", status_code=302)

    hc_repo = HealthCheckRepository(db)
    session = hc_repo.get_session_by_id(uuid.UUID(session_id))

    if not session or session.review_scope.project_id != project.id:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    review_scope = session.review_scope

    # Verify review scope belongs to this project
    if str(review_scope.id) != review_scope_id or review_scope.project_id != project.id:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    # Load control instances
    control_instances = hc_repo.get_control_instances_for_session(session_id)

    # Calculate stats
    stats = hc_repo.get_session_stats(session_id)

    breadcrumbs = [
        {"label": "Projects", "url": "/projects"},
        {"label": project.name, "url": f"/projects/{project.id}"},
        {"label": review_scope.label or review_scope.review_scope_type.name, "url": f"/projects/{project_id}/review-scopes/{review_scope_id}"},
        {"label": session.name, "url": None},
    ]

    return templates.TemplateResponse(
        "projects/health_check/session_detail.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "review_scope": review_scope,
            "session": session,
            "control_instances": control_instances,
            "stats": stats,
            "breadcrumbs": breadcrumbs,
        },
    )


@router.get("/{project_id}/review-scopes/{review_scope_id}/sessions/{session_id}/controls/{instance_id}/panel", response_class=HTMLResponse)
async def get_control_panel(
    project_id: str, review_scope_id: str, session_id: str, instance_id: str, request: Request, db: Session = Depends(get_db)
):
    """Get control assessment panel for a specific control instance."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    repo = ProjectRepository(db)
    project = repo.get_by_id_with_details(user.tenant_id, uuid.UUID(project_id))

    if not project:
        return RedirectResponse(url="/projects", status_code=302)

    hc_repo = HealthCheckRepository(db)
    instance = hc_repo.get_control_instance_with_observations(uuid.UUID(instance_id))

    if not instance or instance.audit_session.project_id != project.id:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    session = instance.audit_session
    review_scope = session.review_scope

    if str(session.id) != session_id or str(session.review_scope_id) != review_scope_id:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    return templates.TemplateResponse(
        "projects/health_check/_control_panel.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "review_scope": review_scope,
            "session": session,
            "instance": instance,
            "observations": instance.observations,
        },
    )


@router.post("/{project_id}/review-scopes/{review_scope_id}/sessions/{session_id}/controls/{instance_id}", response_class=HTMLResponse)
async def update_control(
    project_id: str, review_scope_id: str, session_id: str, instance_id: str, request: Request, db: Session = Depends(get_db)
):
    """Update control instance status and notes."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    repo = ProjectRepository(db)
    project = repo.get_by_id_with_details(user.tenant_id, uuid.UUID(project_id))

    if not project:
        return RedirectResponse(url="/auth/login", status_code=302)

    hc_repo = HealthCheckRepository(db)
    instance = hc_repo.get_control_instance_by_id(uuid.UUID(instance_id))

    if not instance or instance.audit_session.project_id != project.id:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    session = instance.audit_session

    if str(session.id) != session_id:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    form_data = await request.form()
    status_value = form_data.get("status", ControlInstanceStatus.NOT_STARTED.value)
    notes = form_data.get("notes", "").strip() or None

    try:
        status = ControlInstanceStatus(status_value)
    except ValueError:
        status = ControlInstanceStatus.NOT_STARTED

    # Update the instance
    hc_repo.update_control_instance(instance_id, status, notes, user.id)
    instance = hc_repo.get_control_instance_with_observations(uuid.UUID(instance_id))

    session = instance.audit_session
    review_scope = session.review_scope

    return templates.TemplateResponse(
        "projects/health_check/_control_panel.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "review_scope": review_scope,
            "session": session,
            "instance": instance,
            "observations": instance.observations,
        },
        headers=htmx_toast("Assessment saved"),
    )


@router.get("/{project_id}/review-scopes/{review_scope_id}/sessions/{session_id}/evidence/new", response_class=HTMLResponse)
async def add_evidence_modal(
    project_id: str,
    review_scope_id: str,
    session_id: str,
    request: Request,
    db: Session = Depends(get_db),
    instance_id: str | None = None,
    type: str | None = None,
):
    """Get add evidence modal content."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    repo = ProjectRepository(db)
    project = repo.get_by_id_with_details(user.tenant_id, uuid.UUID(project_id))

    if not project:
        return RedirectResponse(url="/projects", status_code=302)

    hc_repo = HealthCheckRepository(db)
    session = hc_repo.get_session_by_id(uuid.UUID(session_id))

    if not session or session.review_scope.project_id != project.id:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    instance = None
    if instance_id:
        instance = hc_repo.get_control_instance_by_id(uuid.UUID(instance_id))
        if not instance or instance.audit_session_id != session.id:
            return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    initial_tab = type or "text_note"

    return templates.TemplateResponse(
        "projects/health_check/_add_evidence_modal.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "session": session,
            "instance": instance,
            "initial_tab": initial_tab,
        },
    )


@router.post("/{project_id}/review-scopes/{review_scope_id}/sessions/{session_id}/evidence", response_class=HTMLResponse)
async def create_evidence(
    project_id: str,
    review_scope_id: str,
    session_id: str,
    request: Request,
    db: Session = Depends(get_db),
    instance_id: str | None = None,
):
    """Create evidence (text note or file) for a control instance."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    repo = ProjectRepository(db)
    project = repo.get_by_id_with_details(user.tenant_id, uuid.UUID(project_id))

    if not project:
        return RedirectResponse(url="/projects", status_code=302)

    hc_repo = HealthCheckRepository(db)
    session = hc_repo.get_session_by_id(uuid.UUID(session_id))

    if not session or session.review_scope.project_id != project.id:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    if not instance_id:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    instance = hc_repo.get_control_instance_by_id(uuid.UUID(instance_id))
    if not instance or instance.audit_session_id != session.id:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    form_data = await request.form()
    evidence_type = (form_data.get("evidence_type") or "").strip()

    if evidence_type == "text_note":
        content = form_data.get("content", "").strip()
        if not content:
            return RedirectResponse(url=f"/projects/{project_id}", status_code=302)
        hc_repo.add_text_evidence(instance.id, content)

    elif evidence_type == "file":
        file = form_data.get("file")
        if not file or not isinstance(file, UploadFile):
            return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

        # Validate file extension
        allowed_extensions = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf"}
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in allowed_extensions:
            return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

        # Create upload directory
        upload_dir = Path(f"static/uploads/health_check/{session_id}")
        upload_dir.mkdir(parents=True, exist_ok=True)

        # Save file
        file_id = str(uuid.uuid4())
        file_path = upload_dir / f"{file_id}{file_ext}"
        file_contents = await file.read()
        file_size = len(file_contents)

        with open(file_path, "wb") as f:
            f.write(file_contents)

        # Store as relative path with leading /
        relative_path = f"/{file_path}"
        hc_repo.add_file_evidence(instance.id, file.filename, relative_path, file_size)

    # Reload instance with updated evidence
    instance = hc_repo.get_control_instance_by_id(instance.id)

    return templates.TemplateResponse(
        "projects/health_check/_evidence_list.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "instance": instance,
        },
        headers=htmx_toast("Evidence added"),
    )


@router.delete("/{project_id}/review-scopes/{review_scope_id}/sessions/{session_id}/evidence/{evidence_id}", response_class=HTMLResponse)
async def delete_evidence(
    project_id: str, review_scope_id: str, session_id: str, evidence_id: str, request: Request, db: Session = Depends(get_db)
):
    """Delete an evidence item."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    repo = ProjectRepository(db)
    project = repo.get_by_id_with_details(user.tenant_id, uuid.UUID(project_id))

    if not project:
        return RedirectResponse(url="/projects", status_code=302)

    hc_repo = HealthCheckRepository(db)
    evidence = hc_repo.get_evidence_by_id(uuid.UUID(evidence_id))

    if not evidence or str(evidence.control_instance.audit_session_id) != session_id:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    instance = evidence.control_instance

    # Delete file from disk if it's a file type
    if evidence.evidence_type == "file" and evidence.file_path:
        file_path = evidence.file_path.lstrip("/")
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass

    # Delete the evidence record
    hc_repo.delete_evidence(evidence_id)

    # Reload instance with updated evidence list
    instance = hc_repo.get_control_instance_by_id(instance.id)

    return templates.TemplateResponse(
        "projects/health_check/_evidence_list.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "instance": instance,
        },
        headers=htmx_toast("Evidence removed"),
    )


# ===== Observation Routes =====

@router.post("/{project_id}/review-scopes/{review_scope_id}/sessions/{session_id}/controls/{instance_id}/details", response_class=HTMLResponse)
async def update_control_with_observations(
    project_id: str, review_scope_id: str, session_id: str, instance_id: str, request: Request, db: Session = Depends(get_db)
):
    """Update control instance status, notes, and handle observations."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    repo = ProjectRepository(db)
    project = repo.get_by_id_with_details(user.tenant_id, uuid.UUID(project_id))

    if not project:
        return RedirectResponse(url="/auth/login", status_code=302)

    hc_repo = HealthCheckRepository(db)
    instance = hc_repo.get_control_instance_with_observations(uuid.UUID(instance_id))

    if not instance or instance.audit_session.project_id != project.id:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    session = instance.audit_session

    if str(session.id) != session_id:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    form_data = await request.form()
    status_value = form_data.get("status", ControlInstanceStatus.NOT_STARTED.value)
    notes = form_data.get("notes", "").strip() or None

    try:
        status = ControlInstanceStatus(status_value)
    except ValueError:
        status = ControlInstanceStatus.NOT_STARTED

    # Update the instance
    hc_repo.update_control_instance(instance_id, status, notes, user.id)

    # Handle observation updates and new observations
    idx = 0
    while True:
        obs_is_new = form_data.get(f"observation_{idx}_is_new")
        if obs_is_new is None:
            break
        if obs_is_new == "true":
            obs_text = form_data.get(f"observation_{idx}_text", "").strip()
            obs_rec = form_data.get(f"observation_{idx}_recommendation", "").strip() or None
            obs_note = form_data.get(f"observation_{idx}_note", "").strip() or None
            if obs_text:
                new_obs = hc_repo.create_observation(instance.id, obs_text, obs_rec)
                if obs_note:
                    hc_repo.add_observation_text_note(new_obs.id, obs_note)
        elif obs_is_new == "false":
            obs_id_str = form_data.get(f"observation_{idx}_id")
            obs_rec = form_data.get(f"observation_{idx}_recommendation", "").strip() or None
            if obs_id_str:
                hc_repo.update_observation_recommendation(uuid.UUID(obs_id_str), obs_rec)
        idx += 1

    # Reload instance with updated observations
    instance = hc_repo.get_control_instance_with_observations(instance.id)
    review_scope = hc_repo.get_review_scope_with_sessions(uuid.UUID(review_scope_id))

    return templates.TemplateResponse(
        "projects/health_check/_control_panel.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "review_scope": review_scope,
            "session": session,
            "instance": instance,
            "observations": instance.observations,
        },
        headers=htmx_toast("Assessment saved"),
    )


@router.delete("/{project_id}/review-scopes/{review_scope_id}/sessions/{session_id}/observations/{obs_id}", response_class=HTMLResponse)
async def delete_observation(
    project_id: str, review_scope_id: str, session_id: str, obs_id: str, request: Request, db: Session = Depends(get_db)
):
    """Delete an observation."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    repo = ProjectRepository(db)
    project = repo.get_by_id_with_details(user.tenant_id, uuid.UUID(project_id))

    if not project:
        return RedirectResponse(url="/projects", status_code=302)

    hc_repo = HealthCheckRepository(db)
    obs = hc_repo.get_observation_by_id(uuid.UUID(obs_id))

    if not obs or obs.control_instance.audit_session_id != uuid.UUID(session_id):
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    instance = obs.control_instance

    # Delete the observation
    hc_repo.delete_observation(uuid.UUID(obs_id))

    # Reload instance with updated observations
    instance = hc_repo.get_control_instance_with_observations(instance.id)
    review_scope = hc_repo.get_review_scope_with_sessions(instance.audit_session.review_scope_id)

    return templates.TemplateResponse(
        "projects/health_check/_control_panel.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "review_scope": review_scope,
            "session": instance.audit_session,
            "instance": instance,
            "observations": instance.observations,
        },
        headers=htmx_toast("Observation deleted"),
    )


@router.get("/{project_id}/review-scopes/{review_scope_id}/sessions/{session_id}/observations/{obs_id}/evidence", response_class=HTMLResponse)
async def get_observation_evidence(
    project_id: str, review_scope_id: str, session_id: str, obs_id: str, request: Request, db: Session = Depends(get_db)
):
    """Get observation evidence panel."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    repo = ProjectRepository(db)
    project = repo.get_by_id_with_details(user.tenant_id, uuid.UUID(project_id))

    if not project:
        return RedirectResponse(url="/projects", status_code=302)

    hc_repo = HealthCheckRepository(db)
    obs = hc_repo.get_observation_by_id(uuid.UUID(obs_id))

    if not obs or obs.control_instance.audit_session_id != uuid.UUID(session_id):
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    session = obs.control_instance.audit_session

    return templates.TemplateResponse(
        "projects/health_check/_hc_observation_evidence_panel.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "session": session,
            "observation": obs,
        },
    )


@router.post("/{project_id}/review-scopes/{review_scope_id}/sessions/{session_id}/observations/{obs_id}/evidence/text", response_class=HTMLResponse)
async def add_observation_text_evidence(
    project_id: str, review_scope_id: str, session_id: str, obs_id: str, request: Request, db: Session = Depends(get_db)
):
    """Add text evidence to an observation."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    repo = ProjectRepository(db)
    project = repo.get_by_id_with_details(user.tenant_id, uuid.UUID(project_id))

    if not project:
        return RedirectResponse(url="/projects", status_code=302)

    hc_repo = HealthCheckRepository(db)
    obs = hc_repo.get_observation_by_id(uuid.UUID(obs_id))

    if not obs or obs.control_instance.audit_session_id != uuid.UUID(session_id):
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    form_data = await request.form()
    content = form_data.get("content", "").strip()

    if not content:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    hc_repo.add_observation_text_note(uuid.UUID(obs_id), content)

    # Reload observation with updated evidence
    obs = hc_repo.get_observation_by_id(uuid.UUID(obs_id))
    session = obs.control_instance.audit_session

    return templates.TemplateResponse(
        "projects/health_check/_hc_observation_evidence_panel.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "session": session,
            "observation": obs,
        },
        headers=htmx_toast("Evidence added"),
    )


@router.post("/{project_id}/review-scopes/{review_scope_id}/sessions/{session_id}/observations/{obs_id}/evidence/image", response_class=HTMLResponse)
async def add_observation_image_evidence(
    project_id: str, review_scope_id: str, session_id: str, obs_id: str, request: Request, db: Session = Depends(get_db)
):
    """Add image evidence to an observation."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    repo = ProjectRepository(db)
    project = repo.get_by_id_with_details(user.tenant_id, uuid.UUID(project_id))

    if not project:
        return RedirectResponse(url="/projects", status_code=302)

    hc_repo = HealthCheckRepository(db)
    obs = hc_repo.get_observation_by_id(uuid.UUID(obs_id))

    if not obs or obs.control_instance.audit_session_id != uuid.UUID(session_id):
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    form_data = await request.form()
    file = form_data.get("file")

    if not file or not isinstance(file, UploadFile):
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    # Validate file extension
    allowed_extensions = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf"}
    file_ext = Path(file.filename).suffix.lower()

    if file_ext not in allowed_extensions:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    # Create upload directory
    upload_dir = Path(f"static/uploads/health_check/{session_id}")
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Save file
    file_id = str(uuid.uuid4())
    file_path = upload_dir / f"{file_id}{file_ext}"
    file_contents = await file.read()
    file_size = len(file_contents)

    with open(file_path, "wb") as f:
        f.write(file_contents)

    # Store as relative path with leading /
    relative_path = f"/{file_path}"
    hc_repo.add_observation_image(uuid.UUID(obs_id), file.filename, relative_path, file_size)

    # Reload observation with updated evidence
    obs = hc_repo.get_observation_by_id(uuid.UUID(obs_id))
    session = obs.control_instance.audit_session

    return templates.TemplateResponse(
        "projects/health_check/_hc_observation_evidence_panel.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "session": session,
            "observation": obs,
        },
        headers=htmx_toast("Evidence added"),
    )


@router.delete("/{project_id}/review-scopes/{review_scope_id}/sessions/{session_id}/observations/{obs_id}/evidence/{ev_id}", response_class=HTMLResponse)
async def delete_observation_evidence(
    project_id: str, review_scope_id: str, session_id: str, obs_id: str, ev_id: str, request: Request, db: Session = Depends(get_db)
):
    """Delete evidence from an observation."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    repo = ProjectRepository(db)
    project = repo.get_by_id_with_details(user.tenant_id, uuid.UUID(project_id))

    if not project:
        return RedirectResponse(url="/projects", status_code=302)

    hc_repo = HealthCheckRepository(db)
    obs = hc_repo.get_observation_by_id(uuid.UUID(obs_id))

    if not obs or obs.control_instance.audit_session_id != uuid.UUID(session_id):
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    # Get evidence to delete
    from app.models.health_check import SessionControlObservationEvidence
    ev = db.query(SessionControlObservationEvidence).filter(
        SessionControlObservationEvidence.id == uuid.UUID(ev_id),
        SessionControlObservationEvidence.session_control_observation_id == uuid.UUID(obs_id),
    ).first()

    if not ev:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    # Delete file from disk if it's an image type
    if ev.evidence_type == "image" and ev.file_path:
        file_path = ev.file_path.lstrip("/")
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass

    # Delete the evidence record
    hc_repo.delete_observation_evidence(uuid.UUID(ev_id))

    # Reload observation with updated evidence
    obs = hc_repo.get_observation_by_id(uuid.UUID(obs_id))
    session = obs.control_instance.audit_session

    return templates.TemplateResponse(
        "projects/health_check/_hc_observation_evidence_panel.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "session": session,
            "observation": obs,
        },
        headers=htmx_toast("Evidence removed"),
    )


@router.get("/{project_id}/controls/{control_id}/row", response_class=HTMLResponse)
async def get_control_row(
    project_id: str, control_id: str, request: Request, db: Session = Depends(get_db)
):
    """Get control row (for cancel/refresh in forms)."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    repo = ProjectRepository(db)
    project = repo.get_by_id_with_details(user.tenant_id, project_id)

    if not project:
        return RedirectResponse(url="/projects", status_code=302)

    # Load framework with sections and controls
    framework_repo = FrameworkRepository(db)
    framework = framework_repo.get_by_id_with_sections(user.tenant_id, project.framework_id)

    # Find the control in the framework
    control = None
    if framework:
        for section in framework.sections:
            for ctrl in section.controls:
                if str(ctrl.id) == control_id:
                    control = ctrl
                    break
            if control:
                break

    if not control:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    # Get all responses for this project
    response_repo = ProjectResponseRepository(db)
    all_responses = response_repo.get_for_project(project.id)
    responses_dict = {str(resp.framework_control_id): resp for resp in all_responses}

    return templates.TemplateResponse(
        "projects/_control_row.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "control": control,
            "responses": responses_dict,
        },
    )


@router.get("/{project_id}/controls/{control_id}/response", response_class=HTMLResponse)
async def get_control_response_form(
    project_id: str, control_id: str, request: Request, db: Session = Depends(get_db)
):
    """Get control response form (HTMX endpoint)."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    repo = ProjectRepository(db)
    project = repo.get_by_id_with_details(user.tenant_id, project_id)

    if not project:
        return RedirectResponse(url="/projects", status_code=302)

    # Load framework with sections and controls
    framework_repo = FrameworkRepository(db)
    framework = framework_repo.get_by_id_with_sections(user.tenant_id, project.framework_id)

    # Find the control in the framework
    control = None
    if framework:
        for section in framework.sections:
            for ctrl in section.controls:
                if str(ctrl.id) == control_id:
                    control = ctrl
                    break
            if control:
                break

    if not control:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    # Get the response if it exists
    response_repo = ProjectResponseRepository(db)
    response = response_repo.get_by_control(project.id, control.id)

    return templates.TemplateResponse(
        "projects/_control_response_form.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "control": control,
            "response": response,
        },
    )


@router.post("/{project_id}/controls/{control_id}/response", response_class=HTMLResponse)
async def save_control_response(
    project_id: str, control_id: str, request: Request, db: Session = Depends(get_db)
):
    """Save control response (HTMX endpoint)."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    repo = ProjectRepository(db)
    project = repo.get_by_id_with_details(user.tenant_id, project_id)

    if not project:
        return RedirectResponse(url="/projects", status_code=302)

    form_data = await request.form()
    response_text = form_data.get("response_text")
    finding = form_data.get("finding")
    recommendation = form_data.get("recommendation")
    auditor_notes = form_data.get("auditor_notes")
    status_value = form_data.get("status", ResponseStatus.NOT_STARTED.value)

    try:
        status = ResponseStatus(status_value)
    except ValueError:
        status = ResponseStatus.NOT_STARTED

    # Upsert the response
    response_repo = ProjectResponseRepository(db)
    response_repo.upsert(
        project.id,
        control_id,
        response_text,
        status,
        finding=finding,
        recommendation=recommendation,
        auditor_notes=auditor_notes,
    )

    # Load framework with sections and controls to get the control
    framework_repo = FrameworkRepository(db)
    framework = framework_repo.get_by_id_with_sections(user.tenant_id, project.framework_id)

    # Find the control in the framework
    control = None
    if framework:
        for section in framework.sections:
            for ctrl in section.controls:
                if str(ctrl.id) == control_id:
                    control = ctrl
                    break
            if control:
                break

    if not control:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    # Return the updated row + OOB tree icon update
    return templates.TemplateResponse(
        "projects/_control_save_response.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "control": control,
            "responses": {str(control.id): response_repo.get_by_control(project.id, control.id)},
        },
        headers=htmx_toast("Response saved successfully")
    )


def _find_control(framework, control_id: str):
    """Find a control in a framework by its UUID string."""
    if not framework:
        return None
    for section in framework.sections:
        for ctrl in section.controls:
            if str(ctrl.id) == control_id:
                return ctrl
    return None


@router.get("/{project_id}/controls/{control_id}/assessment", response_class=HTMLResponse)
async def get_control_assessment(
    project_id: str, control_id: str, request: Request, db: Session = Depends(get_db)
):
    """Show the assessment checklist panel for a control."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    repo = ProjectRepository(db)
    project = repo.get_by_id_with_details(user.tenant_id, project_id)
    if not project:
        return RedirectResponse(url="/projects", status_code=302)

    framework_repo = FrameworkRepository(db)
    framework = framework_repo.get_by_id_with_sections(user.tenant_id, project.framework_id)
    control = _find_control(framework, control_id)
    if not control or not control.assessment_checklist:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    # Get existing response for the control
    response_repo = ProjectResponseRepository(db)
    response = response_repo.get_by_control(project.id, control.id)

    return templates.TemplateResponse(
        "projects/_control_assessment.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "control": control,
            "checklist": control.assessment_checklist,
            "response": response,
        },
    )


@router.post("/{project_id}/controls/{control_id}/assessment", response_class=HTMLResponse)
async def submit_assessment_choice(
    project_id: str, control_id: str, request: Request, db: Session = Depends(get_db)
):
    """Submit an assessment scenario choice and save the response."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    repo = ProjectRepository(db)
    project = repo.get_by_id_with_details(user.tenant_id, project_id)
    if not project:
        return RedirectResponse(url="/projects", status_code=302)

    framework_repo = FrameworkRepository(db)
    framework = framework_repo.get_by_id_with_sections(user.tenant_id, project.framework_id)
    control = _find_control(framework, control_id)
    if not control or not control.assessment_checklist:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    form_data = await request.form()
    scenario_id = form_data.get("scenario_id", "")

    # Find the selected scenario
    scenarios = control.assessment_checklist.get("scenarios", [])
    selected_scenario = None
    for scenario in scenarios:
        if scenario.get("id") == scenario_id:
            selected_scenario = scenario
            break

    if not selected_scenario:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    # Build response text from scenario
    response_text = f"Assessment Result: {selected_scenario.get('label')}\n\nRecommendation:\n{selected_scenario.get('recommendation')}"

    # Extract finding type to determine status
    finding_type = selected_scenario.get("finding_type", "observation")
    if finding_type == "pass":
        status = ResponseStatus.APPROVED
    elif finding_type == "fail":
        status = ResponseStatus.REJECTED
    else:  # observation
        status = ResponseStatus.SUBMITTED

    # Save the response
    response_repo = ProjectResponseRepository(db)
    response_repo.upsert(project.id, control.id, response_text, status)

    # Return the updated row
    all_responses = response_repo.get_for_project(project.id)
    responses_dict = {str(resp.framework_control_id): resp for resp in all_responses}

    return templates.TemplateResponse(
        "projects/_control_row.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "control": control,
            "responses": responses_dict,
        },
        headers=htmx_toast("Assessment completed successfully")
    )


@router.get("/{project_id}/controls/{control_id}/workflow", response_class=HTMLResponse)
async def get_control_workflow(
    project_id: str, control_id: str, request: Request, db: Session = Depends(get_db)
):
    """Show the workflow panel for a control (static text + decision tree)."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    repo = ProjectRepository(db)
    project = repo.get_by_id_with_details(user.tenant_id, project_id)
    if not project:
        return RedirectResponse(url="/projects", status_code=302)

    framework_repo = FrameworkRepository(db)
    framework = framework_repo.get_by_id_with_sections(user.tenant_id, project.framework_id)
    control = _find_control(framework, control_id)
    if not control:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    workflow_def = control.workflow_definition
    if not workflow_def:
        # No workflow — fall back to plain response form
        return RedirectResponse(
            url=f"/projects/{project_id}/controls/{control_id}/response", status_code=302
        )

    # Get or create execution
    wf_repo = WorkflowExecutionRepository(db)
    execution = wf_repo.get_or_create(project.id, control.id)

    # Compute current state
    answers = execution.answers or {}
    current_node_id = workflow_engine.get_current_node_id(workflow_def, answers)
    current_node = workflow_engine.get_node(workflow_def, current_node_id)
    breadcrumbs = workflow_engine.build_breadcrumb_trail(workflow_def, answers)

    # If current node is terminal, extract finding
    finding = None
    if current_node and workflow_engine.is_terminal(current_node):
        finding = workflow_engine.get_terminal_finding(current_node)

    # Get existing response for the free-text form
    response_repo = ProjectResponseRepository(db)
    response = response_repo.get_by_control(project.id, control.id)

    return templates.TemplateResponse(
        "projects/_control_workflow.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "control": control,
            "execution": execution,
            "workflow_def": workflow_def,
            "current_node_id": current_node_id,
            "current_node": current_node,
            "breadcrumbs": breadcrumbs,
            "finding": finding,
            "response": response,
        },
    )


@router.post(
    "/{project_id}/controls/{control_id}/workflow/answer", response_class=HTMLResponse
)
async def submit_workflow_answer(
    project_id: str, control_id: str, request: Request, db: Session = Depends(get_db)
):
    """Process a workflow answer and return the next step."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    repo = ProjectRepository(db)
    project = repo.get_by_id_with_details(user.tenant_id, project_id)
    if not project:
        return RedirectResponse(url="/projects", status_code=302)

    framework_repo = FrameworkRepository(db)
    framework = framework_repo.get_by_id_with_sections(user.tenant_id, project.framework_id)
    control = _find_control(framework, control_id)
    if not control or not control.workflow_definition:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    workflow_def = control.workflow_definition
    form_data = await request.form()
    node_id = form_data.get("node_id", "")
    node = workflow_engine.get_node(workflow_def, node_id)

    if not node:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    # Extract answer based on input type
    input_type = node.get("input_type", "text")
    if input_type == "select":
        answer = form_data.get("answer", "")
    elif input_type == "group":
        answer = {}
        for field_def in node.get("fields", []):
            field_name = field_def.get("name")
            answer[field_name] = form_data.get(field_name, "")
    else:
        answer = form_data.get("answer", "")

    # Resolve next node
    next_node_id = workflow_engine.resolve_next_node(workflow_def, node_id, answer)
    next_node = workflow_engine.get_node(workflow_def, next_node_id) if next_node_id else None

    # Determine status and finding
    finding = None
    generated_finding = None
    status = WorkflowExecutionStatus.IN_PROGRESS
    if next_node and workflow_engine.is_terminal(next_node):
        status = WorkflowExecutionStatus.COMPLETED
        finding = workflow_engine.get_terminal_finding(next_node)
        generated_finding = f"[{finding['finding_type'].upper()}] {finding['title']}\n\n{finding['recommendation']}"

    # Save the answer
    wf_repo = WorkflowExecutionRepository(db)
    execution = wf_repo.upsert_answer(
        project.id,
        control.id,
        node_id,
        answer,
        current_node_id=next_node_id,
        status=status,
        generated_finding=generated_finding,
    )

    # Build updated breadcrumbs
    breadcrumbs = workflow_engine.build_breadcrumb_trail(workflow_def, execution.answers)

    # Get existing response for the free-text form
    response_repo = ProjectResponseRepository(db)
    response = response_repo.get_by_control(project.id, control.id)

    return templates.TemplateResponse(
        "projects/_workflow_step.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "control": control,
            "execution": execution,
            "workflow_def": workflow_def,
            "current_node_id": next_node_id,
            "current_node": next_node,
            "breadcrumbs": breadcrumbs,
            "finding": finding,
            "response": response,
        },
        headers=htmx_toast("Answer recorded successfully")
    )


@router.post(
    "/{project_id}/controls/{control_id}/workflow/reset", response_class=HTMLResponse
)
async def reset_workflow(
    project_id: str, control_id: str, request: Request, db: Session = Depends(get_db)
):
    """Reset a workflow execution back to the first step."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    repo = ProjectRepository(db)
    project = repo.get_by_id_with_details(user.tenant_id, project_id)
    if not project:
        return RedirectResponse(url="/projects", status_code=302)

    framework_repo = FrameworkRepository(db)
    framework = framework_repo.get_by_id_with_sections(user.tenant_id, project.framework_id)
    control = _find_control(framework, control_id)
    if not control or not control.workflow_definition:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    workflow_def = control.workflow_definition
    wf_repo = WorkflowExecutionRepository(db)
    execution = wf_repo.reset(project.id, control.id)

    root_id = workflow_engine.get_root_node_id(workflow_def)
    root_node = workflow_engine.get_node(workflow_def, root_id)

    response_repo = ProjectResponseRepository(db)
    response = response_repo.get_by_control(project.id, control.id)

    return templates.TemplateResponse(
        "projects/_workflow_step.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "control": control,
            "execution": execution,
            "workflow_def": workflow_def,
            "current_node_id": root_id,
            "current_node": root_node,
            "breadcrumbs": [],
            "finding": None,
            "response": response,
        },
        headers=htmx_toast("Workflow reset successfully")
    )


@router.get(
    "/{project_id}/controls/{control_id}/workflow/step", response_class=HTMLResponse
)
async def get_workflow_step(
    project_id: str, control_id: str, request: Request, db: Session = Depends(get_db)
):
    """Get the current workflow step (for refreshing)."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    repo = ProjectRepository(db)
    project = repo.get_by_id_with_details(user.tenant_id, project_id)
    if not project:
        return RedirectResponse(url="/projects", status_code=302)

    framework_repo = FrameworkRepository(db)
    framework = framework_repo.get_by_id_with_sections(user.tenant_id, project.framework_id)
    control = _find_control(framework, control_id)
    if not control or not control.workflow_definition:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    workflow_def = control.workflow_definition
    wf_repo = WorkflowExecutionRepository(db)
    execution = wf_repo.get_or_create(project.id, control.id)

    answers = execution.answers or {}
    current_node_id = workflow_engine.get_current_node_id(workflow_def, answers)
    current_node = workflow_engine.get_node(workflow_def, current_node_id)
    breadcrumbs = workflow_engine.build_breadcrumb_trail(workflow_def, answers)

    finding = None
    if current_node and workflow_engine.is_terminal(current_node):
        finding = workflow_engine.get_terminal_finding(current_node)

    response_repo = ProjectResponseRepository(db)
    response = response_repo.get_by_control(project.id, control.id)

    return templates.TemplateResponse(
        "projects/_workflow_step.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "control": control,
            "execution": execution,
            "workflow_def": workflow_def,
            "current_node_id": current_node_id,
            "current_node": current_node,
            "breadcrumbs": breadcrumbs,
            "finding": finding,
            "response": response,
        },
    )


@router.get("/{project_id}", response_class=HTMLResponse)
async def detail_project(
    project_id: str, request: Request, db: Session = Depends(get_db)
):
    """Show project detail page (parent with segments or segment with controls)."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    from app.utils.access import can_access_project
    repo = ProjectRepository(db)
    project = repo.get_by_id_with_details(user.tenant_id, project_id)

    if not project:
        return RedirectResponse(url="/projects", status_code=302)

    if not can_access_project(user, project):
        return RedirectResponse(url="/projects", status_code=302)

    # Fork: PCI DSS Health Check projects show the health check overview
    if project.project_type == ProjectType.PCI_DSS_HEALTH_CHECK:
        hc_repo = HealthCheckRepository(db)
        review_scopes = hc_repo.get_review_scopes_for_project(project.id)
        total_sessions = sum(len(d.sessions) for d in review_scopes)

        # Compute review-scope stats (pass/fail/not_started counts)
        review_scope_stats = {}
        for review_scope in review_scopes:
            stats = {s.value: 0 for s in ControlInstanceStatus}
            for session in review_scope.sessions:
                for inst in session.control_instances:
                    stats[inst.status.value] = stats.get(inst.status.value, 0) + 1
            review_scope_stats[str(review_scope.id)] = stats

        # Review-scope rollup: single status per review scope
        review_scope_rollup = {str(d.id): compute_review_scope_rollup(review_scope_stats[str(d.id)]) for d in review_scopes}

        # Project-level assessed %
        total_instances = sum(sum(stats.values()) for stats in review_scope_stats.values())
        assessed_instances = sum(
            stats.get("pass", 0) + stats.get("fail", 0) + stats.get("na", 0) + stats.get("in_progress", 0)
            for stats in review_scope_stats.values()
        )
        assessed_pct = round(assessed_instances / total_instances * 100) if total_instances > 0 else 0
        review_scopes_pass = sum(1 for s in review_scope_rollup.values() if s == "pass")

        breadcrumbs = [
            {"label": "Projects", "url": "/projects"},
            {"label": project.name, "url": None},
        ]
        return templates.TemplateResponse(
            "projects/health_check/overview.html",
            {
                "request": request,
                "user": user,
                "project": project,
                "review_scopes": review_scopes,
                "review_scope_stats": review_scope_stats,
                "review_scope_rollup": review_scope_rollup,
                "assessed_pct": assessed_pct,
                "review_scopes_pass": review_scopes_pass,
                "total_sessions": total_sessions,
                "breadcrumbs": breadcrumbs,
            },
        )

    # Check if this is a parent project with segments
    if project.segments:
        # Parent project view: show segments
        segments = repo.get_children(user.tenant_id, project.id)

        # Calculate progress for each segment
        segments_with_progress = []
        response_repo = ProjectResponseRepository(db)
        framework_repo = FrameworkRepository(db)

        for segment in segments:
            framework = framework_repo.get_by_id_with_sections(
                user.tenant_id, segment.framework_id
            )
            all_responses = response_repo.get_for_project(segment.id)

            total_controls = 0
            responded_count = 0
            if framework:
                for section in framework.sections:
                    total_controls += len(section.controls)
                    for control in section.controls:
                        if any(r.framework_control_id == control.id for r in all_responses):
                            responded_count += 1

            progress_pct = (
                (responded_count / total_controls * 100)
                if total_controls > 0
                else 0
            )
            segments_with_progress.append(
                {
                    "segment": segment,
                    "total_controls": total_controls,
                    "responded_count": responded_count,
                    "progress_pct": progress_pct,
                }
            )

        return templates.TemplateResponse(
            "projects/detail_parent.html",
            {
                "request": request,
                "user": user,
                "project": project,
                "segments_with_progress": segments_with_progress,
            },
        )
    else:
        # Segment (or standalone project) view: show controls
        # Load framework with sections and controls
        framework_repo = FrameworkRepository(db)
        framework = framework_repo.get_by_id_with_sections(user.tenant_id, project.framework_id)

        # Load all responses for the project
        response_repo = ProjectResponseRepository(db)
        all_responses = response_repo.get_for_project(project.id)
        responses_dict = {str(resp.framework_control_id): resp for resp in all_responses}

        # Calculate progress
        total_controls = 0
        responded_count = 0
        if framework:
            for section in framework.sections:
                total_controls += len(section.controls)
                for control in section.controls:
                    if str(control.id) in responses_dict:
                        responded_count += 1

        progress_pct = (responded_count / total_controls * 100) if total_controls > 0 else 0

        return templates.TemplateResponse(
            "projects/detail.html",
            {
                "request": request,
                "user": user,
                "project": project,
                "framework": framework,
                "responses": responses_dict,
                "progress_pct": progress_pct,
                "responded_count": responded_count,
                "total_controls": total_controls,
            },
        )


@router.get("/{project_id}/controls/{control_id}/details", response_class=HTMLResponse)
async def get_control_details(
    project_id: str, control_id: str, request: Request, db: Session = Depends(get_db)
):
    """Show control details in the master-detail view."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    repo = ProjectRepository(db)
    project = repo.get_by_id_with_details(user.tenant_id, project_id)
    if not project:
        return HTMLResponse(content="Project not found", status_code=404)

    framework_repo = FrameworkRepository(db)
    framework = framework_repo.get_by_id_with_sections(user.tenant_id, project.framework_id)
    
    control = None
    section_name = "Section"
    if framework:
        for section in framework.sections:
            for ctrl in section.controls:
                if str(ctrl.id) == control_id:
                    control = ctrl
                    section_name = section.name
                    break
            if control:
                break

    if not control:
        return HTMLResponse(content="Control not found", status_code=404)

    response_repo = ProjectResponseRepository(db)
    response = response_repo.get_by_control(project.id, control.id)

    # Fetch observations for this control
    from app.repositories.observation import ProjectObservationRepository
    obs_repo = ProjectObservationRepository(db)
    observations = obs_repo.get_for_control(project.id, control.id)

    return templates.TemplateResponse(
        "projects/_control_detail.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "control": control,
            "section_name": section_name,
            "response": response,
            "observations": observations,
            "saved": False,
            "responses": {},
        },
    )


@router.post("/{project_id}/controls/{control_id}/details", response_class=HTMLResponse)
async def save_control_details(
    project_id: str, control_id: str, request: Request, db: Session = Depends(get_db)
):
    """Save control response details from the master-detail form."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    repo = ProjectRepository(db)
    project = repo.get_by_id_with_details(user.tenant_id, project_id)
    if not project:
        return HTMLResponse(content="Project not found", status_code=404)

    form_data = await request.form()
    response_text = form_data.get("response_text", "")
    status_value = form_data.get("status", ResponseStatus.IN_PROGRESS.value)

    try:
        status = ResponseStatus(status_value)
    except ValueError:
        status = ResponseStatus.IN_PROGRESS

    response_repo = ProjectResponseRepository(db)
    response_repo.upsert(
        project.id,
        control_id,
        response_text,  # Maps to Observation text area
        status,
    )

    # Process observations from form
    from app.repositories.observation import ProjectObservationRepository
    obs_repo = ProjectObservationRepository(db)

    # Collect all observation data from form
    import uuid
    observation_data = {}
    for key in form_data.keys():
        if key.startswith("observation_"):
            parts = key.split("_")
            if len(parts) >= 2:
                idx = parts[1]
                field = "_".join(parts[2:])
                if idx not in observation_data:
                    observation_data[idx] = {}
                observation_data[idx][field] = form_data.get(key)

    # Create new observations
    for idx, obs_data in observation_data.items():
        if obs_data.get("is_new") == "true":
            obs_repo.create_observation(
                project.id,
                uuid.UUID(control_id),
                obs_data.get("text", ""),
                obs_data.get("recommendation", ""),
            )

    framework_repo = FrameworkRepository(db)
    framework = framework_repo.get_by_id_with_sections(user.tenant_id, project.framework_id)

    control = None
    section_name = "Section"
    if framework:
        for section in framework.sections:
            for ctrl in section.controls:
                if str(ctrl.id) == control_id:
                    control = ctrl
                    section_name = section.name
                    break
            if control:
                break

    response = response_repo.get_by_control(project.id, control.id)

    # Fetch observations for this control
    observations = obs_repo.get_for_control(project.id, control.id)

    return templates.TemplateResponse(
        "projects/_control_detail_with_tree_update.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "control": control,
            "section_name": section_name,
            "response": response,
            "observations": observations,
            "saved": True,
        },
        headers=htmx_toast("Details saved successfully")
    )


@router.post("/{project_id}/controls/{control_id}/observations", response_class=HTMLResponse)
async def create_observation(
    project_id: str, control_id: str, request: Request, db: Session = Depends(get_db)
):
    """Create a new observation for a control."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    repo = ProjectRepository(db)
    project = repo.get_by_id_with_details(user.tenant_id, project_id)
    if not project:
        return HTMLResponse(content="Project not found", status_code=404)

    form_data = await request.form()
    observation_text = form_data.get("observation_text", "")
    recommendation_text = form_data.get("recommendation_text", "")

    from app.repositories.observation import ProjectObservationRepository
    obs_repo = ProjectObservationRepository(db)
    obs_repo.create_observation(
        project.id, control_id, observation_text, recommendation_text
    )

    return HTMLResponse(content="Observation created", status_code=200, headers=htmx_toast("Observation created successfully"))


@router.delete("/{project_id}/observations/{observation_id}", response_class=HTMLResponse)
async def delete_project_observation(
    project_id: str, observation_id: str, request: Request, db: Session = Depends(get_db)
):
    """Delete an observation and its evidence files."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    repo = ProjectRepository(db)
    project = repo.get_by_id_with_details(user.tenant_id, project_id)
    if not project:
        return HTMLResponse(content="Project not found", status_code=404)

    from app.repositories.observation import ProjectObservationRepository
    obs_repo = ProjectObservationRepository(db)
    success = obs_repo.delete_observation(observation_id)

    if success:
        return HTMLResponse(content="Observation deleted", status_code=200, headers=htmx_toast("Observation deleted successfully"))
    else:
        return HTMLResponse(content="Observation not found", status_code=404, headers=htmx_toast("Observation not found", "error"))


# ── Evidence routes ────────────────────────────────────────────────────────────

@router.get("/{project_id}/observations/{observation_id}/evidence", response_class=HTMLResponse)
async def get_evidence_panel(
    project_id: str, observation_id: str, request: Request, db: Session = Depends(get_db)
):
    """Return the evidence panel partial for a given observation."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    from app.repositories.observation import ProjectObservationRepository
    obs_repo = ProjectObservationRepository(db)
    observation = obs_repo.get_observation(observation_id)
    if not observation:
        return HTMLResponse(content="Observation not found", status_code=404)

    return templates.TemplateResponse(
        "projects/_evidence_panel.html",
        {"request": request, "observation": observation, "project_id": project_id},
    )


@router.post("/{project_id}/observations/{observation_id}/evidence/text", response_class=HTMLResponse)
async def add_text_evidence(
    project_id: str, observation_id: str, request: Request, db: Session = Depends(get_db)
):
    """Add a text note to an observation."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    form_data = await request.form()
    content = form_data.get("content", "").strip()
    if not content:
        return HTMLResponse(content="Content required", status_code=400)

    from app.repositories.observation import ProjectObservationRepository
    obs_repo = ProjectObservationRepository(db)
    obs_repo.add_text_note(observation_id, content)
    observation = obs_repo.get_observation(observation_id)

    return templates.TemplateResponse(
        "projects/_evidence_panel.html",
        {"request": request, "observation": observation, "project_id": project_id},
        headers=htmx_toast("Note added successfully")
    )


@router.post("/{project_id}/observations/{observation_id}/evidence/image", response_class=HTMLResponse)
async def add_image_evidence(
    project_id: str, observation_id: str, request: Request, db: Session = Depends(get_db)
):
    """Upload an image as evidence for an observation."""
    import os, shutil
    from fastapi import UploadFile
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    form_data = await request.form()
    file: UploadFile = form_data.get("file")
    if not file or not file.filename:
        return HTMLResponse(content="File required", status_code=400)

    allowed = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed:
        return HTMLResponse(content="Unsupported file type", status_code=400)

    upload_dir = "static/uploads/evidence"
    os.makedirs(upload_dir, exist_ok=True)
    safe_name = f"{uuid.uuid4()}{ext}"
    dest = os.path.join(upload_dir, safe_name)

    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    file_size = os.path.getsize(dest)
    file_path = f"/static/uploads/evidence/{safe_name}"

    from app.repositories.observation import ProjectObservationRepository
    obs_repo = ProjectObservationRepository(db)
    obs_repo.add_image(observation_id, file.filename, file_path, file_size)
    observation = obs_repo.get_observation(observation_id)

    return templates.TemplateResponse(
        "projects/_evidence_panel.html",
        {"request": request, "observation": observation, "project_id": project_id},
        headers=htmx_toast("File uploaded successfully")
    )


@router.delete("/{project_id}/observations/{observation_id}/evidence/{evidence_id}", response_class=HTMLResponse)
async def delete_evidence(
    project_id: str, observation_id: str, evidence_id: str,
    request: Request, db: Session = Depends(get_db)
):
    """Delete a single evidence item."""
    import os
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    from app.repositories.observation import ProjectObservationRepository
    from app.models.project import ProjectEvidenceFile
    obs_repo = ProjectObservationRepository(db)

    # Delete file from disk if image
    evidence = db.query(ProjectEvidenceFile).filter(ProjectEvidenceFile.id == evidence_id).first()
    if evidence and evidence.evidence_type == "image" and evidence.file_path:
        disk_path = evidence.file_path.lstrip("/")
        if os.path.exists(disk_path):
            os.remove(disk_path)

    obs_repo.delete_evidence(evidence_id)
    observation = obs_repo.get_observation(observation_id)

    return templates.TemplateResponse(
        "projects/_evidence_panel.html",
        {"request": request, "observation": observation, "project_id": project_id},
    )



# ---------------------------------------------------------------------------
# Project sharing / membership endpoints
# ---------------------------------------------------------------------------

@router.get("/{project_id}/members", response_class=HTMLResponse)
async def get_project_members(project_id: str, request: Request, db: Session = Depends(get_db)):
    """Return share modal partial (list of members + auditor search)."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    from app.utils.access import can_access_project
    repo = ProjectRepository(db)
    project = repo.get_by_id_with_details(user.tenant_id, project_id)
    if not project or not can_access_project(user, project):
        return RedirectResponse(url="/projects", status_code=302)

    # Only owner or admin may share
    is_owner = str(project.owner_id) == str(user.id) or user.role == UserRole.ADMIN

    user_repo = UserRepository(db)
    auditors = user_repo.get_auditors(user.tenant_id)

    return templates.TemplateResponse(
        "projects/_share_modal.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "is_owner": is_owner,
            "auditors": auditors,
        },
    )


@router.post("/{project_id}/members", response_class=HTMLResponse)
async def add_project_member(project_id: str, request: Request, db: Session = Depends(get_db)):
    """Add a member to a project (owner or admin only)."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    from app.utils.access import can_access_project
    repo = ProjectRepository(db)
    project = repo.get_by_id_with_details(user.tenant_id, project_id)
    if not project or not can_access_project(user, project):
        return RedirectResponse(url="/projects", status_code=302)

    is_owner = str(project.owner_id) == str(user.id) or user.role == UserRole.ADMIN
    if not is_owner:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    form = await request.form()
    member_user_id = (form.get("user_id") or "").strip()
    if not member_user_id:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    # Add member if not already present
    existing = db.query(ProjectMember).filter(
        ProjectMember.project_id == project.id,
        ProjectMember.user_id == member_user_id,
    ).first()
    if not existing:
        member = ProjectMember(
            project_id=project.id,
            user_id=member_user_id,
            role="auditor",
        )
        db.add(member)
        db.commit()

    # Re-fetch and return updated modal
    db.refresh(project)
    user_repo = UserRepository(db)
    auditors = user_repo.get_auditors(user.tenant_id)

    return templates.TemplateResponse(
        "projects/_share_modal.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "is_owner": True,
            "auditors": auditors,
            "success": "Member added.",
        },
        headers=htmx_toast("Member added successfully"),
    )


@router.delete("/{project_id}/members/{member_user_id}", response_class=HTMLResponse)
async def remove_project_member(
    project_id: str, member_user_id: str, request: Request, db: Session = Depends(get_db)
):
    """Remove a member from a project (owner or admin only)."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    from app.utils.access import can_access_project
    repo = ProjectRepository(db)
    project = repo.get_by_id_with_details(user.tenant_id, project_id)
    if not project or not can_access_project(user, project):
        return RedirectResponse(url="/projects", status_code=302)

    is_owner = str(project.owner_id) == str(user.id) or user.role == UserRole.ADMIN
    if not is_owner:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

    db.query(ProjectMember).filter(
        ProjectMember.project_id == project.id,
        ProjectMember.user_id == member_user_id,
    ).delete()
    db.commit()

    db.refresh(project)
    user_repo = UserRepository(db)
    auditors = user_repo.get_auditors(user.tenant_id)

    return templates.TemplateResponse(
        "projects/_share_modal.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "is_owner": True,
            "auditors": auditors,
        },
        headers=htmx_toast("Member removed"),
    )


@router.post("/{project_id}/transfer", response_class=HTMLResponse)
async def transfer_project_ownership(
    project_id: str, request: Request, db: Session = Depends(get_db)
):
    """Transfer project ownership to another user (admin only)."""
    user = getattr(request.state, "user", None)
    if not user or user.role != UserRole.ADMIN:
        return RedirectResponse(url="/projects", status_code=302)

    from app.utils.access import can_access_project
    repo = ProjectRepository(db)
    project = repo.get_by_id_with_details(user.tenant_id, project_id)
    if not project:
        return RedirectResponse(url="/projects", status_code=302)

    form = await request.form()
    new_owner_id_str = (form.get("new_owner_id") or "").strip()

    if new_owner_id_str:
        try:
            project.owner_id = uuid.UUID(new_owner_id_str)
            db.commit()
            db.refresh(project)
            transferred = True
        except ValueError:
            transferred = False
    else:
        transferred = False

    # Re-render the modal with updated data
    user_repo = UserRepository(db)
    auditors = user_repo.get_auditors(user.tenant_id)

    return templates.TemplateResponse(
        "projects/_share_modal.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "is_owner": True,
            "auditors": auditors,
            "success": "Ownership transferred successfully." if transferred else None,
        },
        headers=htmx_toast("Ownership transferred") if transferred else None,
    )
