-- Release 2024.11 database changes
-- Target database: PostgreSQL 15
-- Table sizes: orders is about 50 million rows
-- Applied in the same release as the application deploy, which stops using users.phone

ALTER TABLE orders ADD COLUMN status VARCHAR(20) NOT NULL;

CREATE INDEX idx_orders_created_at ON orders (created_at);

ALTER TABLE users DROP COLUMN phone;

ALTER TABLE users ADD CONSTRAINT uq_users_email UNIQUE (email);
