"""Admin routes for template management."""
from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import UserRole
from app.repositories.framework import FrameworkRepository

from app.templates import templates

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/components/hub", response_class=HTMLResponse)
async def components_hub(request: Request, db: Session = Depends(get_db)):
    """Display components hub with navigation."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    return templates.TemplateResponse(
        "components_hub.html",
        {
            "request": request,
            "user": user,
        },
    )


@router.get("/components/demo", response_class=HTMLResponse)
async def components_demo(request: Request, db: Session = Depends(get_db)):
    """Display working component demo (all in one page)."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    return templates.TemplateResponse(
        "components_demo.html",
        {
            "request": request,
            "user": user,
        },
    )


@router.get("/components", response_class=HTMLResponse)
async def components_showcase(request: Request, db: Session = Depends(get_db)):
    """Display component showcase for Phase 1 shadcn components."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    return templates.TemplateResponse(
        "components_showcase.html",
        {
            "request": request,
            "user": user,
        },
    )


@router.get("/components/phase2", response_class=HTMLResponse)
async def components_showcase_phase2(request: Request, db: Session = Depends(get_db)):
    """Display component showcase for Phase 2 shadcn components."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    return templates.TemplateResponse(
        "components_showcase_phase2.html",
        {
            "request": request,
            "user": user,
        },
    )


@router.get("/components/phase3", response_class=HTMLResponse)
async def components_showcase_phase3(request: Request, db: Session = Depends(get_db)):
    """Display component showcase for Phase 3 shadcn components."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    return templates.TemplateResponse(
        "components_showcase_phase3.html",
        {
            "request": request,
            "user": user,
        },
    )


@router.get("/controls", response_class=HTMLResponse)
async def list_controls(request: Request, db: Session = Depends(get_db)):
    """List all framework controls for editing."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    if user.role != UserRole.ADMIN:
        return RedirectResponse(url="/dashboard", status_code=302)

    # Fetch all frameworks with controls
    framework_repo = FrameworkRepository(db)
    frameworks = framework_repo.get_all_with_sections(user.tenant_id)

    # Flatten controls with section info
    controls_list = []
    for framework in frameworks:
        for section in framework.sections:
            for control in section.controls:
                controls_list.append({
                    "control": control,
                    "section": section,
                    "framework": framework,
                })

    return templates.TemplateResponse(
        "admin/controls_list.html",
        {
            "request": request,
            "user": user,
            "controls": controls_list,
        },
    )


@router.get("/controls/{control_id}/edit", response_class=HTMLResponse)
async def edit_control(control_id: str, request: Request, db: Session = Depends(get_db)):
    """Edit control template (requirements, procedures, check points)."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    if user.role != UserRole.ADMIN:
        return RedirectResponse(url="/dashboard", status_code=302)

    # Find the control
    framework_repo = FrameworkRepository(db)
    frameworks = framework_repo.get_all_with_sections(user.tenant_id)

    control = None
    section = None
    framework = None

    for fw in frameworks:
        for sec in fw.sections:
            for ctrl in sec.controls:
                if str(ctrl.id) == control_id:
                    control = ctrl
                    section = sec
                    framework = fw
                    break
            if control:
                break
        if control:
            break

    if not control:
        raise HTTPException(status_code=404, detail="Control not found")

    return templates.TemplateResponse(
        "admin/control_edit.html",
        {
            "request": request,
            "user": user,
            "control": control,
            "section": section,
            "framework": framework,
        },
    )


@router.post("/controls/{control_id}/save", response_class=HTMLResponse)
async def save_control(
    control_id: str,
    request: Request,
    requirements_text: str = Form(""),
    testing_procedures_text: str = Form(""),
    check_points_text: str = Form(""),
    db: Session = Depends(get_db),
):
    """Save control template changes."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    if user.role != UserRole.ADMIN:
        return RedirectResponse(url="/dashboard", status_code=302)

    # Find and update the control
    framework_repo = FrameworkRepository(db)
    frameworks = framework_repo.get_all_with_sections(user.tenant_id)

    control = None
    section = None
    framework = None

    for fw in frameworks:
        for sec in fw.sections:
            for ctrl in sec.controls:
                if str(ctrl.id) == control_id:
                    control = ctrl
                    section = sec
                    framework = fw
                    break
            if control:
                break
        if control:
            break

    if not control:
        raise HTTPException(status_code=404, detail="Control not found")

    # Update control
    control.requirements_text = requirements_text if requirements_text.strip() else None
    control.testing_procedures_text = testing_procedures_text if testing_procedures_text.strip() else None
    control.check_points_text = check_points_text if check_points_text.strip() else None

    db.commit()

    # Redirect back to edit page with success message
    import json
    headers = {
        "HX-Trigger": json.dumps({
            "showMessage": {
                "type": "success",
                "message": "Template saved successfully!"
            }
        })
    }
    return templates.TemplateResponse(
        "admin/control_edit.html",
        {
            "request": request,
            "user": user,
            "control": control,
            "section": section,
            "framework": framework,
            "saved": True,
        },
        headers=headers
    )
