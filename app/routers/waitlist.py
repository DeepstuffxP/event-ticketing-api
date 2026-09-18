from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime, timedelta
import asyncpg
from app.database import get_pool
from app.dependencies import get_current_user, CurrentUser

router = APIRouter()

CLAIM_WINDOW_MINUTES = 15

class WaitlistJoinRequest(BaseModel):
    ticket_tier_id: int

class WaitlistOut(BaseModel):
    id: int
    ticket_tier_id: int
    status: str
    joined_at: datetime
    claim_expires_at: datetime | None

@router.post("/join", response_model=WaitlistOut)
async def join_waitlist(
    payload: WaitlistJoinRequest,
    user: CurrentUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
):
    async with pool.acquire() as conn:
        tier = await conn.fetchrow(
            "SELECT * FROM ticket_tiers WHERE id = $1", payload.ticket_tier_id
        )
        if tier is None:
            raise HTTPException(404, "ticket tier not found")
        if tier["quantity_sold"] < tier["quantity_total"]:
            raise HTTPException(400, "tickets still available — buy directly instead")

        existing = await conn.fetchrow(
            """
            SELECT id FROM waitlist_entries
            WHERE user_id = $1 AND ticket_tier_id = $2 AND status IN ('waiting', 'offered')
            """,
            user.id, payload.ticket_tier_id,
        )
        if existing:
            raise HTTPException(409, "already on the waitlist for this tier")

        row = await conn.fetchrow(
            """
            INSERT INTO waitlist_entries (user_id, ticket_tier_id, status)
            VALUES ($1, $2, 'waiting')
            RETURNING id, ticket_tier_id, status, joined_at, claim_expires_at
            """,
            user.id, payload.ticket_tier_id,
        )
        return dict(row)