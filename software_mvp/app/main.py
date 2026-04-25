from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .api.routes import acl, pipelines, query_builder, schedules, system, views
from .config import settings
from .database import SessionLocal, init_db
from .services.scheduler_service import init_scheduler, shutdown_scheduler
from .services.auth_service import ROLE_ADMIN, ROLE_OPERATOR, ensure_default_admin
from .ui_routes import router as ui_router

app = FastAPI(title=settings.app_name, version="0.1.0")
app.mount(
    "/static",
    StaticFiles(directory=str(Path(__file__).resolve().parent / "static")),
    name="static",
)

app.include_router(system.router)
app.include_router(views.router)
app.include_router(pipelines.router)
app.include_router(schedules.router)
app.include_router(acl.router)
app.include_router(query_builder.router)
app.include_router(ui_router)


def _login_redirect(next_path: str, error: str | None = None) -> RedirectResponse:
    params = {"next": next_path}
    if error:
        params["error"] = error
    return RedirectResponse(url=f"/login?{urlencode(params)}", status_code=303)


def _api_forbidden(message: str, status_code: int = 403) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": message})


@app.middleware("http")
async def auth_middleware(request, call_next):
    path = request.url.path
    method = request.method.upper()

    is_public = (
        path.startswith("/login")
        or path.startswith("/docs")
        or path.startswith("/redoc")
        or path == "/openapi.json"
        or path == "/api/system/health"
    )
    is_protected_ui = path == "/" or path.startswith("/ui/")
    is_protected_api = path.startswith("/api/")

    request.state.current_user = None
    role = None

    if (is_protected_ui or is_protected_api) and not is_public:
        # Defensive read: avoid request.session assertion if middleware order is not ideal
        # on a deployed instance. In that case treat the request as unauthenticated.
        session = request.scope.get("session") or {}
        user_id = session.get("user_id")
        role = session.get("role")
        username = session.get("username")
        try:
            user_id = int(user_id) if user_id is not None else None
        except (TypeError, ValueError):
            if isinstance(session, dict):
                session.clear()
            user_id = None
        if not user_id:
            if is_protected_api:
                return _api_forbidden("Autenticazione richiesta.", status_code=401)
            return _login_redirect(next_path=path)
        request.state.current_user = {
            "id": user_id,
            "username": username,
            "role": role,
        }

        # Admin-only areas
        if (path.startswith("/ui/users") or path.startswith("/ui/settings")) and role != ROLE_ADMIN:
            return RedirectResponse(
                url="/?error=Permesso negato: area riservata ad admin.",
                status_code=303,
            )

        # ACL write = admin only
        if method != "GET" and path.startswith("/ui/acl/") and role != ROLE_ADMIN:
            return RedirectResponse(
                url="/ui/acl?error=Permesso negato: modifica ACL riservata ad admin.",
                status_code=303,
            )

        # Generic write operations = admin/operator
        if method != "GET" and path.startswith("/ui/"):
            if role not in {ROLE_ADMIN, ROLE_OPERATOR}:
                return RedirectResponse(
                    url="/?error=Permesso negato: operazione consentita solo ad admin/operator.",
                    status_code=303,
                )

        # API rules
        if method != "GET" and path.startswith("/api/acl") and role != ROLE_ADMIN:
            return _api_forbidden("Permesso negato: API ACL write riservata ad admin.")
        if method != "GET" and path.startswith("/api/"):
            if role not in {ROLE_ADMIN, ROLE_OPERATOR}:
                return _api_forbidden("Permesso negato: API write consentita solo ad admin/operator.")

    return await call_next(request)

# IMPORTANT: add this AFTER the function-based auth middleware registration.
# Starlette inserts newly added middleware at the beginning of the stack; adding
# SessionMiddleware here ensures session data is available in auth_middleware.
app.add_middleware(SessionMiddleware, secret_key=settings.app_session_secret)


@app.on_event("startup")
def startup() -> None:
    init_db()
    db = SessionLocal()
    try:
        ensure_default_admin(
            db,
            username=settings.app_admin_username,
            password=settings.app_admin_password,
        )
    finally:
        db.close()
    init_scheduler()


@app.on_event("shutdown")
def shutdown() -> None:
    shutdown_scheduler()
