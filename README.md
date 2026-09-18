# Event Ticketing API

A concurrency-safe event ticketing backend built with FastAPI and raw SQL (asyncpg) over PostgreSQL no ORM, so the concurrency-critical queries are explicit rather than abstracted away.

## What it does

Organizers create events with limited-quantity ticket tiers. Attendees buy tickets, or join a waitlist when a tier sells out. Promo codes apply discounts with usage limits. Two things this project focuses on getting genuinely right under concurrent load:

- **Anti-oversell purchasing** — an atomic `UPDATE ... WHERE quantity_sold + n <= quantity_total RETURNING *` guards every purchase, so two simultaneous buyers competing for the last ticket can never both succeed.
- **Waitlist promotion** — uses PostgreSQL's `SELECT ... FOR UPDATE SKIP LOCKED` so multiple concurrent cancellations promote *different* waitlisted users instead of blocking on each other or double-offering the same slot.

## Stack

- FastAPI
- asyncpg (raw SQL, not an ORM)
- PostgreSQL
- JWT auth (python-jose + passlib)
- Docker

## Core endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/auth/register` | Register as organizer or attendee |
| POST | `/auth/login` | Log in, get a JWT |
| POST | `/events` | Create an event (organizer only) |
| GET | `/events/{event_id}` | View an event |
| POST | `/events/{event_id}/tiers` | Create a ticket tier (organizer only, must own the event) |
| GET | `/events/{event_id}/tiers` | List tiers for an event |
| POST | `/orders/purchase` | Buy tickets — atomic anti-oversell logic lives here |
| POST | `/orders/{order_id}/cancel` | Cancel an order, freeing tickets and promoting the next waitlisted user |
| POST | `/waitlist/join` | Join the waitlist for a sold-out tier |

## Running locally

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in your real DB password and a random JWT secret

createdb ticket
psql -U postgres -d ticket -f schema.sql

uvicorn app.main:app --reload
```

API docs are then available at `http://localhost:8000/docs`.

## Why raw SQL instead of an ORM

The point of this project is demonstrating the SQL itself — the atomic `UPDATE`, `FOR UPDATE SKIP LOCKED`, and transactional promo-code validation are the actual subject matter. An ORM would abstract exactly the part being showcased.