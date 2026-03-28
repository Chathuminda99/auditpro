from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse

from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ProjectStatus
from app.repositories import (
    ProjectRepository,
    ClientRepository,
    FrameworkRepository,
    ProjectResponseRepository,
)

router = APIRouter(tags=["dashboard"])
from app.templates import templates


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """Render dashboard page."""
    # Check if user is authenticated
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    # Get real stats from repositories
    project_repo = ProjectRepository(db)
    client_repo = ClientRepository(db)
    framework_repo = FrameworkRepository(db)
    response_repo = ProjectResponseRepository(db)

    all_projects = project_repo.filter_projects(user.tenant_id, user=user)
    active_projects = project_repo.filter_projects(user.tenant_id, status=ProjectStatus.IN_PROGRESS, user=user)
    completed_projects = project_repo.filter_projects(user.tenant_id, status=ProjectStatus.COMPLETED, user=user)
    pending_responses = response_repo.count_pending_for_tenant(user.tenant_id)

    stats = {
        "total_projects": len(all_projects),
        "active_projects": len(active_projects),
        "completed_assessments": len(completed_projects),
        "pending_responses": pending_responses,
        "total_clients": len(client_repo.get_all(user.tenant_id)),
        "total_frameworks": len(framework_repo.get_all(user.tenant_id)),
    }

    # Calculate progress for each active project
    active_projects_with_progress = []
    for project in active_projects:
        framework = framework_repo.get_by_id_with_sections(
            user.tenant_id, project.framework_id
        ) if project.framework_id else None

        total_controls = 0
        responded_count = 0
        if framework:
            all_responses = response_repo.get_for_project(project.id)
            responses_dict = {str(r.framework_control_id) for r in all_responses}
            for section in framework.sections:
                total_controls += len(section.controls)
                for control in section.controls:
                    if str(control.id) in responses_dict:
                        responded_count += 1

        progress_pct = round(responded_count / total_controls * 100) if total_controls > 0 else 0
        active_projects_with_progress.append({
            "project": project,
            "total_controls": total_controls,
            "responded_count": responded_count,
            "progress_pct": progress_pct,
        })

    return templates.TemplateResponse(
        request,
        "dashboard/index.html",
        {
            "request": request,
            "user": user,
            "stats": stats,
            "active_projects": active_projects_with_progress,
        },
    )
