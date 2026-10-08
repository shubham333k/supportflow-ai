from fastapi import APIRouter
from pydantic import BaseModel

from api.app.core.config import get_settings

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    ok: bool
    db: bool
    llm: bool
    version: str = "v1"


@router.get("/healthz", response_model=HealthResponse)
async def health_check():
    settings = get_settings()

    # In Phase 0/1 skeleton, db status will check connection if configured
    db_ok = bool(settings.DATABASE_URL)
    llm_ok = bool(settings.GEMINI_API_KEY)

    return HealthResponse(
        ok=True,
        db=db_ok,
        llm=llm_ok,
        version="v1"
    )
