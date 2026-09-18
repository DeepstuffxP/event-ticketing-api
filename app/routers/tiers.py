from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import asyncpg
from app.database import get_pool
from app.dependencies import get_current_user, require_organizer, CurrentUser

router = APIRouter()


class TierCreate(BaseModel):
    name: str
    price: float
    quantity_total: int

class TierOut(BaseModel):
    id: int
    event_id: int
    name: str
    price: float
    quantity_total: int
    quantity_sold: int

async def _assert_owns_event(pool, event_id: int, organizer_id: int):
    row = await pool.fetchrow(
        "SELECT organizer_id FROM events WHERE id = $1", event_id
    )
    if row is None:
        raise HTTPException(404, "event not found")
    if row["organizer_id"] != organizer_id:
        raise HTTPException(403, "not your event")

@router.post("/{event_id}/tiers", response_model=TierOut)
async def create_tier(
    event_id: int,
    payload: TierCreate,
    user: CurrentUser = Depends(require_organizer),
    pool: asyncpg.Pool = Depends(get_pool),
):
    await _assert_owns_event(pool, event_id, user.id)
    row = await pool.fetchrow(
        """
        INSERT INTO ticket_tiers (event_id, name, price, quantity_total)
        VALUES ($1, $2, $3, $4)
        RETURNING id, event_id, name, price, quantity_total, quantity_sold
        """,
        event_id, payload.name, payload.price, payload.quantity_total,
    )
    return dict(row)

@router.get("/{event_id}/tiers", response_model=list[TierOut])
async def list_tiers(event_id: int, pool: asyncpg.Pool = Depends(get_pool)):
    rows = await pool.fetch(
        "SELECT id, event_id, name, price, quantity_total, quantity_sold FROM ticket_tiers WHERE event_id = $1",
        event_id,
    )
    return [dict(r) for r in rows]