import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def create_users_db():
    conn = sqlite3.connect(os.path.join(BASE_DIR, "users.db"))
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            username TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            first_name TEXT,
            last_name TEXT,
            phone TEXT,
            date_of_birth TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS addresses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            street TEXT,
            city TEXT,
            state TEXT,
            zip_code TEXT,
            country TEXT DEFAULT 'US',
            is_default INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        INSERT OR IGNORE INTO users (id, email, username) VALUES
            (1, 'alice@example.com', 'alice'),
            (2, 'bob@example.com', 'bob'),
            (3, 'carol@example.com', 'carol');
        INSERT OR IGNORE INTO profiles (user_id, first_name, last_name, phone) VALUES
            (1, 'Alice', 'Smith', '555-0101'),
            (2, 'Bob', 'Jones', '555-0102'),
            (3, 'Carol', 'White', '555-0103');
        INSERT OR IGNORE INTO addresses (user_id, street, city, state, zip_code) VALUES
            (1, '123 Maple St', 'Springfield', 'IL', '62701'),
            (2, '456 Oak Ave', 'Shelbyville', 'IL', '62702');
    """)
    conn.commit()
    conn.close()

def create_orders_db():
    conn = sqlite3.connect(os.path.join(BASE_DIR, "orders.db"))
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            total_amount REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(id)
        );
        INSERT OR IGNORE INTO orders (id, user_id, status, total_amount) VALUES
            (1, 1, 'completed', 149.99),
            (2, 1, 'pending', 49.99),
            (3, 2, 'completed', 299.99),
            (4, 3, 'cancelled', 19.99);
        INSERT OR IGNORE INTO order_items (order_id, product_id, quantity, unit_price) VALUES
            (1, 1, 2, 49.99),
            (1, 3, 1, 50.01),
            (2, 2, 1, 49.99),
            (3, 1, 6, 49.99);
    """)
    conn.commit()
    conn.close()

def create_products_db():
    conn = sqlite3.connect(os.path.join(BASE_DIR, "products.db"))
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT
        );
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER,
            name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            sku TEXT UNIQUE,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        );
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            quantity_in_stock INTEGER DEFAULT 0,
            reorder_threshold INTEGER DEFAULT 10,
            last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id)
        );
        INSERT OR IGNORE INTO categories (id, name) VALUES
            (1, 'Electronics'), (2, 'Clothing'), (3, 'Books');
        INSERT OR IGNORE INTO products (id, category_id, name, price, sku) VALUES
            (1, 1, 'Wireless Headphones', 49.99, 'ELEC-001'),
            (2, 1, 'USB-C Hub', 49.99, 'ELEC-002'),
            (3, 2, 'Cotton T-Shirt', 19.99, 'CLO-001'),
            (4, 3, 'Python Programming', 39.99, 'BOK-001');
        INSERT OR IGNORE INTO inventory (product_id, quantity_in_stock) VALUES
            (1, 120), (2, 45), (3, 200), (4, 80);
    """)
    conn.commit()
    conn.close()

def create_payments_db():
    conn = sqlite3.connect(os.path.join(BASE_DIR, "payments.db"))
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            status TEXT DEFAULT 'pending',
            method TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_id INTEGER NOT NULL,
            type TEXT,
            amount REAL,
            gateway_ref TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (payment_id) REFERENCES payments(id)
        );
        INSERT OR IGNORE INTO payments (id, order_id, amount, status, method) VALUES
            (1, 1, 149.99, 'completed', 'credit_card'),
            (2, 2, 49.99, 'pending', 'paypal'),
            (3, 3, 299.99, 'completed', 'credit_card'),
            (4, 4, 19.99, 'refunded', 'credit_card');
        INSERT OR IGNORE INTO transactions (payment_id, type, amount, gateway_ref) VALUES
            (1, 'charge', 149.99, 'TXN-001'),
            (3, 'charge', 299.99, 'TXN-002'),
            (4, 'charge', 19.99, 'TXN-003'),
            (4, 'refund', 19.99, 'TXN-004');
    """)
    conn.commit()
    conn.close()

def setup_all():
    create_users_db()
    create_orders_db()
    create_products_db()
    create_payments_db()
    print("All mock databases created successfully.")

if __name__ == "__main__":
    setup_all()
