from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
import asyncpg

from app.database import get_pool
from app.dependencies import get_current_user, CurrentUser

router = APIRouter()

CLAIM_WINDOW_MINUTES = 15


class PurchaseRequest(BaseModel):
    ticket_tier_id: int
    quantity: int
    promo_code: Optional[str] = None


class OrderOut(BaseModel):
    id: int
    event_id: int
    status: str
    total_price: float
    ticket_ids: List[int]


@router.post("/purchase", response_model=OrderOut)
async def purchase_tickets(
    payload: PurchaseRequest,
    user: CurrentUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
):
    if payload.quantity < 1:
        raise HTTPException(400, "quantity must be at least 1")

    async with pool.acquire() as conn:
        async with conn.transaction():
            tier = await conn.fetchrow(
                "SELECT * FROM ticket_tiers WHERE id = $1 FOR UPDATE",
                payload.ticket_tier_id,
            )
            if tier is None:
                raise HTTPException(404, "ticket tier not found")

            updated = await conn.fetchrow(
                """
                UPDATE ticket_tiers
                SET quantity_sold = quantity_sold + $2
                WHERE id = $1 AND quantity_sold + $2 <= quantity_total
                RETURNING *
                """,
                payload.ticket_tier_id, payload.quantity,
            )
            if updated is None:
                raise HTTPException(409, "not enough tickets remaining")

            price = float(updated["price"])
            total_price = price * payload.quantity

            promo_id = None
            if payload.promo_code:
                promo = await conn.fetchrow(
                    """
                    SELECT * FROM promo_codes
                    WHERE event_id = $1 AND code = $2
                    FOR UPDATE
                    """,
                    updated["event_id"], payload.promo_code,
                )
                if promo is None:
                    raise HTTPException(400, "invalid promo code")
                if promo["expires_at"] and promo["expires_at"] < datetime.utcnow():
                    raise HTTPException(400, "promo code expired")
                if promo["uses_count"] >= promo["max_uses"]:
                    raise HTTPException(400, "promo code usage limit reached")

                prior_uses = await conn.fetchval(
                    """
                    SELECT COUNT(*) FROM orders
                    WHERE user_id = $1 AND promo_code_id = $2 AND status = 'confirmed'
                    """,
                    user.id, promo["id"],
                )
                if prior_uses > 0:
                    raise HTTPException(400, "promo code already used by this user")

                promo_id = promo["id"]
                total_price = total_price * (1 - float(promo["discount_pct"]) / 100)

                await conn.execute(
                    "UPDATE promo_codes SET uses_count = uses_count + 1 WHERE id = $1",
                    promo_id,
                )

            order = await conn.fetchrow(
                """
                INSERT INTO orders (user_id, event_id, promo_code_id, status, total_price)
                VALUES ($1, $2, $3, 'confirmed', $4)
                RETURNING id, event_id, status, total_price
                """,
                user.id, updated["event_id"], promo_id, total_price,
            )

            ticket_ids = []
            for _ in range(payload.quantity):
                t = await conn.fetchrow(
                    "INSERT INTO tickets (order_id, ticket_tier_id) VALUES ($1, $2) RETURNING id",
                    order["id"], payload.ticket_tier_id,
                )
                ticket_ids.append(t["id"])

            return {
                "id": order["id"],
                "event_id": order["event_id"],
                "status": order["status"],
                "total_price": float(order["total_price"]),
                "ticket_ids": ticket_ids,
            }


async def _promote_next_waiter(conn, ticket_tier_id: int, freed_count: int):
    for _ in range(freed_count):
        waiter = await conn.fetchrow(
            """
            SELECT id FROM waitlist_entries
            WHERE ticket_tier_id = $1 AND status = 'waiting'
            ORDER BY joined_at ASC
            LIMIT 1
            FOR UPDATE SKIP LOCKED
            """,
            ticket_tier_id,
        )
        if waiter is None:
            return

        expires = datetime.utcnow() + timedelta(minutes=CLAIM_WINDOW_MINUTES)
        await conn.execute(
            """
            UPDATE waitlist_entries
            SET status = 'offered', claim_expires_at = $2
            WHERE id = $1
            """,
            waiter["id"], expires,
        )


@router.post("/{order_id}/cancel")
async def cancel_order(
    order_id: int,
    user: CurrentUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
):
    async with pool.acquire() as conn:
        async with conn.transaction():
            order = await conn.fetchrow(
                "SELECT * FROM orders WHERE id = $1 AND user_id = $2 FOR UPDATE",
                order_id, user.id,
            )
            if order is None:
                raise HTTPException(404, "order not found")
            if order["status"] == "cancelled":
                raise HTTPException(400, "order already cancelled")

            tickets = await conn.fetch(
                "SELECT id, ticket_tier_id FROM tickets WHERE order_id = $1", order_id
            )
            tier_counts = {}
            for t in tickets:
                tier_counts[t["ticket_tier_id"]] = tier_counts.get(t["ticket_tier_id"], 0) + 1

            await conn.execute(
                "UPDATE orders SET status = 'cancelled' WHERE id = $1", order_id
            )

            for tier_id, count in tier_counts.items():
                await conn.execute(
                    "UPDATE ticket_tiers SET quantity_sold = quantity_sold - $2 WHERE id = $1",
                    tier_id, count,
                )
                await _promote_next_waiter(conn, tier_id, count)

            return {"status": "cancelled", "order_id": order_id}