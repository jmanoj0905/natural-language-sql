-- Initialize PostgreSQL test database with sample data
-- This script creates sample tables for testing the Natural Language SQL Engine

-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    full_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    role VARCHAR(50) DEFAULT 'user'
);

-- Create products table
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price DECIMAL(10, 2) NOT NULL,
    stock_quantity INTEGER DEFAULT 0,
    category VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create orders table
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_amount DECIMAL(10, 2) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    shipping_address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create order_items table
CREATE TABLE IF NOT EXISTS order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
    product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL DEFAULT 1,
    unit_price DECIMAL(10, 2) NOT NULL,
    subtotal DECIMAL(10, 2) GENERATED ALWAYS AS (quantity * unit_price) STORED
);

-- Insert sample users
INSERT INTO users (username, email, full_name, created_at, role) VALUES
('john_doe', 'john@example.com', 'John Doe', CURRENT_TIMESTAMP - INTERVAL '30 days', 'user'),
('jane_smith', 'jane@example.com', 'Jane Smith', CURRENT_TIMESTAMP - INTERVAL '25 days', 'user'),
('bob_wilson', 'bob@example.com', 'Bob Wilson', CURRENT_TIMESTAMP - INTERVAL '20 days', 'admin'),
('alice_brown', 'alice@example.com', 'Alice Brown', CURRENT_TIMESTAMP - INTERVAL '15 days', 'user'),
('charlie_davis', 'charlie@example.com', 'Charlie Davis', CURRENT_TIMESTAMP - INTERVAL '10 days', 'user'),
('diana_evans', 'diana@example.com', 'Diana Evans', CURRENT_TIMESTAMP - INTERVAL '5 days', 'user'),
('frank_garcia', 'frank@example.com', 'Frank Garcia', CURRENT_TIMESTAMP - INTERVAL '3 days', 'user'),
('grace_harris', 'grace@example.com', 'Grace Harris', CURRENT_TIMESTAMP - INTERVAL '1 day', 'user');

-- Insert sample products
INSERT INTO products (name, description, price, stock_quantity, category) VALUES
('Laptop Pro 15', 'High-performance laptop with 16GB RAM', 1299.99, 50, 'Electronics'),
('Wireless Mouse', 'Ergonomic wireless mouse', 29.99, 200, 'Accessories'),
('USB-C Cable', '2m USB-C charging cable', 14.99, 500, 'Accessories'),
('Mechanical Keyboard', 'RGB mechanical gaming keyboard', 89.99, 75, 'Accessories'),
('Monitor 27"', '4K UHD 27-inch monitor', 399.99, 30, 'Electronics'),
('Webcam HD', '1080p HD webcam', 59.99, 100, 'Electronics'),
('Desk Lamp', 'LED desk lamp with USB charging', 34.99, 150, 'Office'),
('Office Chair', 'Ergonomic office chair', 249.99, 25, 'Office'),
('Notebook Set', 'Pack of 3 premium notebooks', 19.99, 300, 'Stationery'),
('Pen Set', 'Set of 10 ballpoint pens', 9.99, 400, 'Stationery');

-- Insert sample orders
INSERT INTO orders (user_id, order_date, total_amount, status, shipping_address) VALUES
(1, CURRENT_TIMESTAMP - INTERVAL '25 days', 1329.98, 'delivered', '123 Main St, City, State 12345'),
(2, CURRENT_TIMESTAMP - INTERVAL '20 days', 89.99, 'delivered', '456 Oak Ave, City, State 12346'),
(3, CURRENT_TIMESTAMP - INTERVAL '15 days', 459.97, 'delivered', '789 Pine Rd, City, State 12347'),
(4, CURRENT_TIMESTAMP - INTERVAL '10 days', 649.98, 'shipped', '321 Elm St, City, State 12348'),
(5, CURRENT_TIMESTAMP - INTERVAL '7 days', 44.98, 'processing', '654 Maple Dr, City, State 12349'),
(6, CURRENT_TIMESTAMP - INTERVAL '5 days', 1299.99, 'processing', '987 Cedar Ln, City, State 12350'),
(7, CURRENT_TIMESTAMP - INTERVAL '3 days', 119.97, 'pending', '147 Birch Way, City, State 12351'),
(1, CURRENT_TIMESTAMP - INTERVAL '2 days', 399.99, 'pending', '123 Main St, City, State 12345');

-- Insert sample order items
INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES
-- Order 1
(1, 1, 1, 1299.99),
(1, 2, 1, 29.99),
-- Order 2
(2, 4, 1, 89.99),
-- Order 3
(3, 5, 1, 399.99),
(3, 2, 2, 29.99),
-- Order 4
(4, 1, 1, 1299.99),
-- Order 5
(5, 3, 3, 14.99),
-- Order 6
(6, 1, 1, 1299.99),
-- Order 7
(7, 9, 6, 19.99),
-- Order 8
(8, 5, 1, 399.99);

-- Create audit log table for tracking deleted records
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    operation_type VARCHAR(50) NOT NULL,  -- 'delete_user', 'delete_order', etc.
    table_name VARCHAR(100) NOT NULL,
    record_id INTEGER NOT NULL,
    record_snapshot JSONB NOT NULL,       -- Full record before deletion
    cascade_impact JSONB,                 -- Details of cascaded deletes
    performed_by VARCHAR(255),            -- User/system that performed operation
    performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reason TEXT                           -- Optional reason for deletion
);

-- Create indexes for better query performance
CREATE INDEX idx_users_created_at ON users(created_at);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_products_category ON products(category);
CREATE INDEX idx_products_price ON products(price);
CREATE INDEX idx_orders_user_id ON orders(user_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_order_date ON orders(order_date);
CREATE INDEX idx_order_items_order_id ON order_items(order_id);
CREATE INDEX idx_order_items_product_id ON order_items(product_id);
CREATE INDEX idx_audit_log_table_record ON audit_log(table_name, record_id);
CREATE INDEX idx_audit_log_performed_at ON audit_log(performed_at);

-- Grant SELECT permissions to readonly_user
GRANT CONNECT ON DATABASE testdb TO readonly_user;
GRANT USAGE ON SCHEMA public TO readonly_user;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly_user;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO readonly_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO readonly_user;

-- Print summary
DO $$
BEGIN
    RAISE NOTICE 'Database initialized successfully!';
    RAISE NOTICE 'Tables created: users, products, orders, order_items';
    RAISE NOTICE 'Sample data inserted for testing';
    RAISE NOTICE 'Indexes created for performance';
END $$;
