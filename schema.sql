CREATE TYPE user_role AS ENUM ('organizer', 'attendee');
CREATE TYPE order_status as ENUM ('confirmed', 'cancelled');
CREATE TYPE waitlist_status as ENUM ('waiting', 'offered', 'expired', 'claimed');

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role user_role NOT NULL DEFAULT 'attendee',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    organizer_id INTEGER NOT NULL REFERENCES users(id),
    name VARCHAR(255) NOT NULL,
    venue VARCHAR(255),
    event_date TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE ticket_tiers (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    price NUMERIC(10, 2) NOT NULL,
    quantity_total INTEGER NOT NULL,
    quantity_sold INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT quantity_valid CHECK (quantity_sold <= quantity_total)
);

CREATE TABLE promo_codes (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    code VARCHAR(50) NOT NULL,
    discount_pct NUMERIC(5, 2) NOT NULL CHECK (discount_pct > 0 AND discount_pct <= 100),
    max_uses INTEGER NOT NULL,
    uses_count INTEGER NOT NULL DEFAULT 0,
    expires_at TIMESTAMPTZ,
    UNIQUE (event_id, code)
);

CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    event_id INTEGER NOT NULL REFERENCES events(id),
    promo_code_id INTEGER REFERENCES promo_codes(id),
    status order_status NOT NULL DEFAULT 'confirmed',
    total_price NUMERIC(10, 2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE tickets (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    ticket_tier_id INTEGER NOT NULL REFERENCES ticket_tiers(id)
);

CREATE TABLE waitlist_entries (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    ticket_tier_id INTEGER NOT NULL REFERENCES ticket_tiers(id),
    status waitlist_status NOT NULL DEFAULT 'waiting',
    joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    claim_expires_at TIMESTAMPTZ
);

CREATE INDEX idx_orders_user ON orders(user_id);
CREATE INDEX idx_tickets_order ON tickets(order_id);
CREATE INDEX idx_waitlist_tier_status ON waitlist_entries(ticket_tier_id, status);