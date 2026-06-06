from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.api.routers import (
    consumption, dashboard, ems, forecasts, reports, weather,
)
from backend.app.api.exceptions import register_exception_handlers
from backend.config.config import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = get_settings()
    logger.info("EMS API starting  object=%s  db=%s",
                cfg.object.name, cfg.database.url.split("@")[-1])
    yield
    logger.info("EMS API shutdown")


def create_app() -> FastAPI:
    cfg = get_settings()

    app = FastAPI(
        title="EMS — Energy Management System API",
        description=(
            "REST API для системи енергоменеджменту поліклініки (Київ).\n\n"
            "Інтегрує:\n"
            "- **ЛР1**: PostgreSQL, вимірювання, метеодані, тарифи\n"
            "- **ЛР2**: ML-прогнозування (Gradient Boosting, MAPE=7.16%)\n"
            "- **ЛР3**: EMS Engine, симуляція, NPV/IRR\n\n"
            f"Об'єкт: {cfg.object.name} | Площа: {cfg.object.area_m2} м²"
        ),
        version="4.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    origins = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:4173",
        "http://127.0.0.1:3000",
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    prefix = cfg.api.prefix

    app.include_router(dashboard.router, prefix=prefix, tags=["Dashboard"])
    app.include_router(consumption.router, prefix=prefix, tags=["Consumption"])
    app.include_router(weather.router, prefix=prefix, tags=["Weather"])
    app.include_router(forecasts.router, prefix=prefix, tags=["Forecasts"])
    app.include_router(ems.router, prefix=prefix, tags=["EMS"])
    app.include_router(reports.router, prefix=prefix, tags=["Reports"])

    @app.get("/health", tags=["System"])
    async def health():
        return {"status": "ok", "version": "4.0.0", "object": cfg.object.name}

    return app


app = create_app()
