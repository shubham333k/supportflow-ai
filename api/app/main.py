from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.app.core.logging import setup_logging
from api.app.routers import analytics, health, kb, messages, sla, tickets


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    from api.app.core.config import settings
    if "sqlite" in settings.DATABASE_URL:
        from api.app.models.base import Base
        from api.app.models.database import engine
        import api.app.models.tables  # noqa: F401

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="SupportFlow AI API",
    description="Intelligent AI Customer Support Triage, Escalation & CRM Engine",
    version="1.0.0",
    lifespan=lifespan,
)

# Register routers
app.include_router(health.router)
app.include_router(health.router, prefix="/api/v1")
app.include_router(messages.router, prefix="/api/v1")
app.include_router(tickets.router, prefix="/api/v1")
app.include_router(kb.router, prefix="/api/v1")
app.include_router(sla.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "service": "SupportFlow AI",
        "status": "online",
        "docs_url": "/docs",
    }
