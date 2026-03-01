"""Project management routes."""

import uuid
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse

from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Project, ProjectStatus
from app.models.project import ResponseStatus
from app.models.workflow import WorkflowExecutionStatus
from app.repositories import (
    ProjectRepository,
    ClientRepository,
    FrameworkRepository,
    ProjectResponseRepository,
    WorkflowExecutionRepository,
    UserRepository,
)
from app.models.project import ProjectMember
from app.models.user import UserRole
from app.services import workflow_engine

router = APIRouter(prefix="/projects", tags=["projects"])
from app.templates import templates
from app.utils.htmx import htmx_toast


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

    repo = ProjectRepository(db)
    project = repo.create(
        tenant_id=user.tenant_id,
        client_id=client_id,
        framework_id=framework_id,
        name=name,
        description=form_data.get("description", ""),
        status=status,
        owner_id=user.id,
    )

    # Refresh to get related objects
    db.refresh(project, ["client", "framework"])

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
async def delete_observation(
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
