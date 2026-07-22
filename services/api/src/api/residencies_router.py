"""Residency (address history) REST endpoints.

See docs/superpowers/plans/2026-07-11-entity-address-history.md. Detection
itself happens in `entity_agent.py` as a side effect of document processing
-- this router is read/review surface only: list a user's history, and
approve/reject a `pending_review` residency period the same way entities
are reviewed (docs/superpowers/specs/2026-07-09-entity-review-queue-design.md).
"""
import logging
from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.address_parser import build_maps_url
from api.auth import get_current_user
from api.db import get_db
from api.models import AddressDetail, Document, Entity, Residency, User
from api.signal_client import send_signal_message

logger = logging.getLogger(__name__)

router = APIRouter(tags=["residencies"])


def _require_admin(current_user: User) -> None:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")


class AddressOut(BaseModel):
    id: UUID
    name: str
    street: str | None
    house_number: str | None
    postal_code: str | None
    city: str | None
    country: str | None
    maps_url: str | None


class ResidencyOut(BaseModel):
    id: UUID
    address: AddressOut
    valid_from: date | None
    valid_to: date | None
    status: str
    source_document_id: UUID | None
    linked_document_count: int
    created_at: datetime


async def _list_residencies(db: AsyncSession, user_id: UUID) -> list[Residency]:
    result = await db.execute(
        select(Residency)
        .where(Residency.user_id == user_id)
        .order_by(Residency.valid_from.desc().nulls_last(), Residency.created_at.desc())
    )
    return list(result.scalars().all())


async def _to_out(db: AsyncSession, residency: Residency) -> ResidencyOut:
    detail = await db.get(AddressDetail, residency.address_entity_id)
    entity_row = await db.get(Entity, residency.address_entity_id)
    count_result = await db.execute(
        select(func.count()).select_from(Document).where(Document.residency_id == residency.id)
    )
    return ResidencyOut(
        id=residency.id,
        address=AddressOut(
            id=residency.address_entity_id,
            name=entity_row.name if entity_row else "",
            street=detail.street if detail else None,
            house_number=detail.house_number if detail else None,
            postal_code=detail.postal_code if detail else None,
            city=detail.city if detail else None,
            country=detail.country if detail else None,
            maps_url=build_maps_url(
                street=detail.street if detail else None,
                house_number=detail.house_number if detail else None,
                postal_code=detail.postal_code if detail else None,
                city=detail.city if detail else None,
                country=detail.country if detail else None,
            ) if detail else None,
        ),
        valid_from=residency.valid_from,
        valid_to=residency.valid_to,
        status=residency.status,
        source_document_id=residency.source_document_id,
        linked_document_count=count_result.scalar_one(),
        created_at=residency.created_at,
    )


@router.get("/users/me/residencies", response_model=list[ResidencyOut])
async def list_my_residencies(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ResidencyOut]:
    residencies = await _list_residencies(db, current_user.id)
    return [await _to_out(db, r) for r in residencies]


@router.get("/admin/users/{user_id}/residencies", response_model=list[ResidencyOut])
async def list_user_residencies(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ResidencyOut]:
    _require_admin(current_user)
    residencies = await _list_residencies(db, user_id)
    return [await _to_out(db, r) for r in residencies]


class ResidencyCorrection(BaseModel):
    valid_from: date | None = None
    valid_to: date | None = None


async def _transition_residency(db: AsyncSession, residency_id: UUID, new_status: str) -> Residency:
    residency = await db.get(Residency, residency_id)
    if residency is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Residency not found")
    if residency.status != "pending_review":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Residency is not pending review (status: {residency.status})",
        )
    residency.status = new_status
    await db.commit()
    await db.refresh(residency)
    return residency


@router.post("/residencies/{residency_id}/approve", response_model=ResidencyOut)
async def approve_residency(
    residency_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResidencyOut:
    residency = await _transition_residency(db, residency_id, "confirmed")
    out = await _to_out(db, residency)
    await _maybe_notify_confirmed_residency(db, residency, out)
    return out


async def _maybe_notify_confirmed_residency(db: AsyncSession, residency: Residency, out: ResidencyOut) -> None:
    """Best-effort (see signal_client.py's own contract) -- a Signal failure must
    never break the approve endpoint itself. Gated on the address having all of
    street/house_number/postal_code/city populated: a strictly-worse maps link
    isn't useful, and this doubles as a live signal that the extraction pipeline
    is actually producing complete data."""
    address = out.address
    if not all([address.street, address.house_number, address.postal_code, address.city]):
        return
    user = await db.get(User, residency.user_id)
    if user is None or not user.phone_number or not address.maps_url:
        return
    try:
        await send_signal_message(
            user.phone_number,
            f"Your address has been confirmed: {address.street} {address.house_number}, "
            f"{address.postal_code} {address.city}\n{address.maps_url}",
        )
    except Exception:
        logger.exception("residencies_router: failed to send residency-confirmed Signal notification")


@router.post("/residencies/{residency_id}/reject", response_model=ResidencyOut)
async def reject_residency(
    residency_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResidencyOut:
    residency = await _transition_residency(db, residency_id, "rejected")
    return await _to_out(db, residency)


@router.patch("/residencies/{residency_id}", response_model=ResidencyOut)
async def correct_residency(
    residency_id: UUID,
    payload: ResidencyCorrection,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResidencyOut:
    """Admin/self correction of a residency period's dates (e.g. the extracted
    document date was off by a few days from the actual move date)."""
    residency = await db.get(Residency, residency_id)
    if residency is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Residency not found")
    if residency.user_id != current_user.id:
        _require_admin(current_user)
    if payload.valid_from is not None:
        residency.valid_from = payload.valid_from
    if payload.valid_to is not None:
        residency.valid_to = payload.valid_to
    await db.commit()
    await db.refresh(residency)
    return await _to_out(db, residency)


@router.get("/documents/{document_id}/residency", response_model=ResidencyOut | None)
async def get_document_residency(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResidencyOut | None:
    document = await db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if document.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your document")
    if document.residency_id is None:
        return None
    residency = await db.get(Residency, document.residency_id)
    return await _to_out(db, residency) if residency else None
