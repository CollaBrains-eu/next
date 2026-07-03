"""GET /learning/dataset (Phase 15, ADR 0030).

Admin-only: this exports real user questions and drafted document
content, the most sensitive data surface any endpoint in this codebase
touches -- narrower access than any prior phase's default.
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.db import get_db
from api.learning_dataset import build_training_dataset
from api.models import User

router = APIRouter(prefix="/learning", tags=["learning"])


@router.get("/dataset")
async def get_dataset(
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return await build_training_dataset(db, limit=limit)
