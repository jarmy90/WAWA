"""Punto de entrada de la aplicación.

Arranque: ``uvicorn app.main:app --host 0.0.0.0 --port 8000``
La base de datos SQLite se inicializa automáticamente (``init_db``).
"""
from __future__ import annotations

import traceback

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response
from starlette.types import Scope


class NoCacheStaticFiles(StaticFiles):
    """Sirve el frontend SIN cabeceras de caché (iteración 011).

    Elimina la caché heurística del navegador/proxy: el propietario veía la
    interfaz de la iteración 009 porque el navegador reutilizaba el HTML y el
    app.js antiguos (mismas URLs sin versión y sin Cache-Control).
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-store"
        return response

from app.api.routes import router as api_router
from app.core.config import get_settings
from app.core.container import AppContainer, build_container
from app.core.errors import AppError
from app.core.logging import get_logger

log = get_logger("main")


def create_app(container: AppContainer | None = None) -> FastAPI:
    """Crea la aplicación. Si no se pasa contenedor, lo construye con la
    configuración por defecto (o la de ``.env``)."""
    if container is None:
        container = build_container()

    settings = container.settings
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        description="Motor autónomo de investigación y selección de oportunidades (MVP local).",
    )
    app.state.container = container

    # Iteración 010: CORS local RESTRICTIVO por defecto (127.0.0.1/localhost).
    # El panel NO debe exponerse a Internet sin autenticación/CSRF/TLS/rate limit.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        log.error("Error no controlado", extra={"path": request.url.path, "error": str(exc)})
        log.debug(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error", "message": "Error interno del servidor."}},
        )

    # Vistas premium (iteración 020) y CANDIDATAS (iteración 022): rutas
    # limpias que funcionan directamente y tras refrescar el navegador.
    if settings.frontend_dir.exists():
        for route, filename in (
            ("/mission-control", "mission-control.html"),
            ("/agents-viz", "agents-viz.html"),
            ("/candidates", "candidates.html"),
            ("/arena", "arena.html"),
        ):
            path = settings.frontend_dir / filename
            if path.exists():
                app.get(route)(lambda path=path: FileResponse(path, media_type="text/html"))

        # Frontend estático: se monta al final para no sombrear /api/*.
        # NoCacheStaticFiles: sin cabeceras de caché para que el navegador nunca
        # sirva un frontend antiguo de iteraciones previas (iteración 011).
        app.mount("/", NoCacheStaticFiles(directory=str(settings.frontend_dir), html=True), name="frontend")

    return app


app = create_app()
