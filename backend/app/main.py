from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routes import router
from .cleanup import start_cleanup_service, stop_cleanup_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    settings.JOBS_DIR.mkdir(parents=True, exist_ok=True)
    start_cleanup_service()
    yield
    stop_cleanup_service()


app = FastAPI(
    title="Separador Musical API",
    description="API para separación de voz e instrumentos usando Demucs",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
