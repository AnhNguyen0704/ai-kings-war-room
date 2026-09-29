"""Health + provider status routes."""
from fastapi import APIRouter, Depends

from app.api.deps import runtime
from app.db.database import get_session
import sqlalchemy as sa

from app.models.entities import Agent

router = APIRouter(tags=["health"])


@router.get("/api/health")
async def health():
    return {"status": "ok", "service": "ai-kings-war-room"}


@router.get("/api/providers")
async def providers(rt=Depends(runtime)):
    return {"providers": rt.providers.status(), "judge": rt.providers.judge_label()}
