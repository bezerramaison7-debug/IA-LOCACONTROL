import logging
from contextlib import asynccontextmanager

from alembic.script import ScriptDirectory
from fastapi import Depends, FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import __version__
from app.api.health import router as health_router
from app.auth.local import installation, local_operator, not_in_local_mode
from app.auth.routes import router as identity_router
from app.auth.routes import set_station_cookie
from app.contracts.routes import router as contracts_router
from app.core.config import Settings, resource
from app.drafts.routes import router as drafts_router
from app.fiscal.routes import router as fiscal_router
from app.imports.routes import router as imports_router
from app.masters.routes import router as masters_router
from app.network.routes import record_reuse
from app.network.routes import router as stations_router
from app.network.stations import registry_for
from app.network.tls import TLS_FOLDER, LocalAuthority
from app.ops.backup import BackupManager, BackupScheduler
from app.ops.maintenance import MaintenanceGate, MaintenanceMiddleware
from app.ops.routes import router as backups_router
from app.persistence.database import build_engine
from app.portal.routes import router as portal_router
from app.quotes.routes import router as quotes_router
from app.reports.routes import router as reports_router


def configure_logging():
    """Uvicorn only configures its own loggers; application messages need a handler too."""
    logger = logging.getLogger("app")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False


def prepare_installation(engine, local_mode: bool):
    """Installation id (never regenerated) and, in the local edition, the local operator."""
    try:
        with Session(engine) as db:
            db.execute(text("BEGIN IMMEDIATE"))
            installation(db)
            if local_mode:
                local_operator(db)
            db.commit()
    except SQLAlchemyError:
        # Database not migrated yet: /health reports it; /api/auth/me creates both later.
        logging.getLogger("app").warning("Identificação da instalação adiada: banco indisponível.")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.engine = build_engine(settings.database_url)
        try:
            scripts = ScriptDirectory(str(resource("backend/migrations")))
            app.state.expected_heads = set(scripts.get_heads())
            prepare_installation(app.state.engine, settings.local_mode)
            scheduler = None
            if settings.backup_scheduler:
                scheduler = BackupScheduler(BackupManager(settings, app.state.engine))
                scheduler.start()
            try:
                yield
            finally:
                if scheduler:
                    scheduler.stop()
        finally:
            app.state.engine.dispose()

    app = FastAPI(title="LocaControl API", version=__version__, lifespan=lifespan)
    app.state.settings = settings
    app.state.gate = MaintenanceGate()
    # Paired stations of the store network (ADR-025); outside the database on purpose.
    app.state.stations = registry_for(settings)
    # Local certificate authority for HTTPS (P1-E), beside the station list, outside backups.
    app.state.tls = LocalAuthority(app.state.stations.path.parent / TLS_FOLDER)
    app.add_middleware(MaintenanceMiddleware, gate=app.state.gate)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token", "X-LocaControl-Request"],
        expose_headers=["X-LocaControl-Edition", "X-LocaControl-Retry", "X-LocaControl-Pairing"],
    )

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        # Station token rotation and reuse (A1), after the request's transaction has ended.
        rotate = getattr(request.state, "station_rotate", None)
        if rotate:
            set_station_cookie(response, settings, rotate, request)
        reuse = getattr(request.state, "station_reuse", None)
        if reuse:
            await run_in_threadpool(record_reuse, app.state.engine, reuse)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
            if settings.local_mode:
                # Lets the interface tell "this computer has no access" from "sign in".
                response.headers["X-LocaControl-Edition"] = "local"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request, _error):
        # FastAPI's default response contains rejected input, potentially a password.
        return JSONResponse(
            status_code=422,
            content={"detail": "Dados inválidos. Confira os campos e os limites informados."},
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error(_request, _error):
        return JSONResponse(
            status_code=503,
            content={"detail": "Banco indisponível. Verifique a conexão e as migrations."},
        )

    app.include_router(health_router)
    app.include_router(identity_router)
    app.include_router(masters_router)
    app.include_router(imports_router)
    app.include_router(quotes_router)
    app.include_router(contracts_router)
    app.include_router(reports_router)
    # The customer portal belongs to a future web edition; the code stays, the routes do not.
    app.include_router(portal_router, dependencies=[Depends(not_in_local_mode)])
    app.include_router(fiscal_router)
    app.include_router(backups_router)
    app.include_router(drafts_router)
    app.include_router(stations_router)
    dist = resource("frontend/dist")
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
    return app


app = create_app()
