"""Shared FastAPI dependencies."""
from typing import AsyncIterator

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session


async def require_room(room_id: str, session: AsyncSession = Depends(get_session)):
    from app.models.entities import Room

    room = await session.get(Room, room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")
    return room


def runtime(request: Request):
    from app.core.runtime import get_runtime

    return get_runtime()
