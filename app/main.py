import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from app.config import get_settings
from app.logging_config import configure_logging
from app.middleware.auth import AuthMiddleware
from app.middleware.request_logging import RequestLoggingMiddleware
from app.middleware.tenant import TenantMiddleware
from app.routes import auth, dashboard, clients, frameworks, projects, admin
from app.routes import admin_users
from app.templates import templates
from app.utils.htmx import htmx_toast, is_htmx_request

settings = get_settings()
configure_logging(settings)

APP_LOGGER = logging.getLogger("auditpro.app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    APP_LOGGER.info(
        "application_startup app_name=%s debug=%s",
        settings.app_name,
        settings.debug,
    )
    yield
    APP_LOGGER.info("application_shutdown")


def create_app() -> FastAPI:
    """Application factory."""
    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
    )

    # Mount static files
    app.mount("/static", StaticFiles(directory="static"), name="static")

    # Add middleware (order matters - add in reverse)
    app.add_middleware(TenantMiddleware)
    app.add_middleware(AuthMiddleware)
    app.add_middleware(RequestLoggingMiddleware)

    # Include routers
    app.include_router(auth.router)
    app.include_router(dashboard.router)
    app.include_router(clients.router)
    app.include_router(frameworks.router)
    app.include_router(projects.router)
    app.include_router(admin.router)
    app.include_router(admin_users.router)

    # Root redirect
    @app.get("/")
    def root():
        return RedirectResponse(url="/auth/login")

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        if is_htmx_request(request):
            status_to_msg = {
                401: "You must be logged in to do that.",
                403: "You don't have permission to do that.",
                404: "The requested resource was not found.",
            }
            msg = status_to_msg.get(exc.status_code, f"Error {exc.status_code}.")
            return HTMLResponse("", status_code=204, headers=htmx_toast(msg, "error"))

        template_map = {403: "errors/403.html", 404: "errors/404.html"}
        template_name = template_map.get(exc.status_code, "errors/500.html")
        return templates.TemplateResponse(
            request,
            template_name,
            {"status_code": exc.status_code, "detail": exc.detail},
            status_code=exc.status_code,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        APP_LOGGER.exception("unhandled_exception path=%s", request.url.path)
        if is_htmx_request(request):
            return HTMLResponse(
                "", status_code=204,
                headers=htmx_toast("An unexpected error occurred. Please try again.", "error"),
            )
        return templates.TemplateResponse(
            request,
            "errors/500.html",
            {"request": request, "status_code": 500, "detail": "Internal server error"},
            status_code=500,
        )

    return app


app = create_app()
