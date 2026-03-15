#!/usr/bin/env bash
# Seed a test MySQL database for natural-lang-sql testing.
# Creates DB + tables + data, waits for you to test, then drops everything.
#
# Usage:
#   ./scripts/seed_mysql.sh                           # defaults below
#   MYSQL_HOST=localhost MYSQL_PORT=3306 MYSQL_USER=root ./scripts/seed_mysql.sh

set -euo pipefail

DB_NAME="${MYSQL_DATABASE:-nlsql_test}"
MYSQL_HOST="${MYSQL_HOST:-localhost}"
MYSQL_PORT="${MYSQL_PORT:-3306}"
MYSQL_USER="${MYSQL_USER:-manoj}"
MYSQL_PASSWORD="${MYSQL_PASSWORD:-ssdiblr}"

MYSQL_CMD="mysql -h $MYSQL_HOST -P $MYSQL_PORT -u $MYSQL_USER"
if [ -n "$MYSQL_PASSWORD" ]; then
    MYSQL_CMD="$MYSQL_CMD -p$MYSQL_PASSWORD"
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  MySQL seed — $MYSQL_USER@$MYSQL_HOST:$MYSQL_PORT/$DB_NAME"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1. Create database ────────────────────────────────
echo "[1/3] Creating database '$DB_NAME'..."
$MYSQL_CMD -e "DROP DATABASE IF EXISTS \`$DB_NAME\`;"
$MYSQL_CMD -e "CREATE DATABASE \`$DB_NAME\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
echo "      ✓ database created"

# ── 2. Seed tables + data ─────────────────────────────
echo "[2/2] Creating tables and inserting sample data..."
$MYSQL_CMD "$DB_NAME" <<'SQL'

-- users
CREATE TABLE users (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(150) NOT NULL,
    email       VARCHAR(255) UNIQUE NOT NULL,
    role        VARCHAR(50) NOT NULL DEFAULT 'tenant',
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO users (name, email, role) VALUES
    ('Alice Marsh',    'alice@example.com',   'landlord'),
    ('Bob Tanaka',     'bob@example.com',     'tenant'),
    ('Carol Singh',    'carol@example.com',   'tenant'),
    ('David Osei',     'david@example.com',   'tenant'),
    ('Eva Rossi',      'eva@example.com',     'landlord');

-- properties
CREATE TABLE properties (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    owner_id    INT NOT NULL,
    address     VARCHAR(255) NOT NULL,
    city        VARCHAR(100) NOT NULL,
    bedrooms    INT NOT NULL,
    rent_price  DECIMAL(10,2) NOT NULL,
    status      VARCHAR(50) NOT NULL DEFAULT 'available',
    CONSTRAINT fk_prop_owner FOREIGN KEY (owner_id) REFERENCES users(id)
);

INSERT INTO properties (owner_id, address, city, bedrooms, rent_price, status) VALUES
    (1, '12 Oak Street',      'Austin',      2, 1800.00, 'rented'),
    (1, '45 Pine Avenue',     'Austin',      3, 2400.00, 'available'),
    (5, '8 Maple Road',       'Dallas',      1, 1200.00, 'rented'),
    (5, '101 Cedar Lane',     'Dallas',      4, 3100.00, 'available'),
    (1, '77 Elm Boulevard',   'Houston',     2, 1650.00, 'maintenance');

-- leases
CREATE TABLE leases (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    property_id   INT NOT NULL,
    tenant_id     INT NOT NULL,
    start_date    DATE NOT NULL,
    end_date      DATE NOT NULL,
    rent_amount   DECIMAL(10,2) NOT NULL,
    CONSTRAINT fk_lease_property FOREIGN KEY (property_id) REFERENCES properties(id),
    CONSTRAINT fk_lease_tenant   FOREIGN KEY (tenant_id)   REFERENCES users(id)
);

INSERT INTO leases (property_id, tenant_id, start_date, end_date, rent_amount) VALUES
    (1, 2, '2024-01-01', '2024-12-31', 1800.00),
    (3, 3, '2024-03-01', '2025-02-28', 1200.00),
    (1, 4, '2025-01-01', '2025-12-31', 1850.00);

-- payments
CREATE TABLE payments (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    lease_id       INT NOT NULL,
    amount         DECIMAL(10,2) NOT NULL,
    payment_date   DATE NOT NULL,
    status         VARCHAR(50) NOT NULL DEFAULT 'paid',
    CONSTRAINT fk_pay_lease FOREIGN KEY (lease_id) REFERENCES leases(id)
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
