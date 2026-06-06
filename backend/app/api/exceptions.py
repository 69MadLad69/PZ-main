from __future__ import annotations
import logging
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(404)
    async def not_found(_req: Request, exc):
        return JSONResponse(status_code=404, content={"detail": "Not found"})

    @app.exception_handler(Exception)
    async def generic_error(_req: Request, exc: Exception):
        logger.error("Unhandled error: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error", "type": type(exc).__name__},
        )
