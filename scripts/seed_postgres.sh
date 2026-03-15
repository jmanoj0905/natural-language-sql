#!/usr/bin/env bash
# Seed a test PostgreSQL database for natural-lang-sql testing.
# Creates DB + tables + data, waits for you to test, then drops everything.
#
# Usage:
#   ./scripts/seed_postgres.sh                        # defaults below
#   PGHOST=localhost PGPORT=5432 PGUSER=postgres ./scripts/seed_postgres.sh

set -euo pipefail

DB_NAME="${PGDATABASE:-nlsql_test}"
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-manoj}"

export PGPASSWORD="${PGPASSWORD:-ssdiblr}"

PSQL="psql -h $PGHOST -p $PGPORT -U $PGUSER"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  PostgreSQL seed — $PGUSER@$PGHOST:$PGPORT/$DB_NAME"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1. Create database ────────────────────────────────
echo "[1/3] Creating database '$DB_NAME'..."
$PSQL -d postgres -c "DROP DATABASE IF EXISTS $DB_NAME;" 2>/dev/null || true
$PSQL -d postgres -c "CREATE DATABASE $DB_NAME;"
echo "      ✓ database created"

# ── 2. Seed tables + data ─────────────────────────────
echo "[2/2] Creating tables and inserting sample data..."
$PSQL -d "$DB_NAME" <<'SQL'

-- users
CREATE TABLE users (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    email       TEXT UNIQUE NOT NULL,
    role        TEXT NOT NULL DEFAULT 'tenant',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO users (name, email, role) VALUES
    ('Alice Marsh',    'alice@example.com',   'landlord'),
    ('Bob Tanaka',     'bob@example.com',     'tenant'),
    ('Carol Singh',    'carol@example.com',   'tenant'),
    ('David Osei',     'david@example.com',   'tenant'),
    ('Eva Rossi',      'eva@example.com',     'landlord');

-- properties
CREATE TABLE properties (
    id          SERIAL PRIMARY KEY,
    owner_id    INT NOT NULL REFERENCES users(id),
    address     TEXT NOT NULL,
    city        TEXT NOT NULL,
    bedrooms    INT NOT NULL,
    rent_price  NUMERIC(10,2) NOT NULL,
    status      TEXT NOT NULL DEFAULT 'available'   -- available | rented | maintenance
);

INSERT INTO properties (owner_id, address, city, bedrooms, rent_price, status) VALUES
    (1, '12 Oak Street',      'Austin',      2, 1800.00, 'rented'),
    (1, '45 Pine Avenue',     'Austin',      3, 2400.00, 'available'),
    (5, '8 Maple Road',       'Dallas',      1, 1200.00, 'rented'),
    (5, '101 Cedar Lane',     'Dallas',      4, 3100.00, 'available'),
    (1, '77 Elm Boulevard',   'Houston',     2, 1650.00, 'maintenance');

-- leases
CREATE TABLE leases (
    id            SERIAL PRIMARY KEY,
    property_id   INT NOT NULL REFERENCES properties(id),
    tenant_id     INT NOT NULL REFERENCES users(id),
    start_date    DATE NOT NULL,
    end_date      DATE NOT NULL,
    rent_amount   NUMERIC(10,2) NOT NULL
);

INSERT INTO leases (property_id, tenant_id, start_date, end_date, rent_amount) VALUES
    (1, 2, '2024-01-01', '2024-12-31', 1800.00),
    (3, 3, '2024-03-01', '2025-02-28', 1200.00),
    (1, 4, '2025-01-01', '2025-12-31', 1850.00);

-- payments
CREATE TABLE payments (
    id             SERIAL PRIMARY KEY,
    lease_id       INT NOT NULL REFERENCES leases(id),
    amount         NUMERIC(10,2) NOT NULL,
    payment_date   DATE NOT NULL,
    status         TEXT NOT NULL DEFAULT 'paid'   -- paid | late | pending
);

INSERT INTO payments (lease_id, amount, payment_date, status) VALUES
    (1, 1800.00, '2024-01-05', 'paid'),
    (1, 1800.00, '2024-02-04', 'paid'),
    (1, 1800.00, '2024-03-07', 'late'),
    (2, 1200.00, '2024-03-03', 'paid'),
    (2, 1200.00, '2024-04-01', 'paid'),
    (3, 1850.00, '2025-01-06', 'paid'),
    (3, 1850.00, '2025-02-10', 'pending');

SQL
echo "      ✓ tables + data inserted"
echo ""
echo "  Tables: users, properties, leases, payments"
echo ""
echo "  Sample questions to try in the UI:"
echo "    - show all available properties"
echo "    - which tenants have late payments?"
echo "    - total rent collected per property"
echo "    - list all leases ending in 2025"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Done. Connect to '$DB_NAME' in the UI to start testing."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
