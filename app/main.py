from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from app.config import get_settings
from app.middleware.auth import AuthMiddleware
from app.middleware.tenant import TenantMiddleware
from app.routes import auth, dashboard, clients, frameworks, projects, admin
from app.routes import admin_users


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
    )

    # Mount static files
    app.mount("/static", StaticFiles(directory="static"), name="static")

    # Add middleware (order matters - add in reverse)
    app.add_middleware(TenantMiddleware)
    app.add_middleware(AuthMiddleware)

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

    return app


app = create_app()
