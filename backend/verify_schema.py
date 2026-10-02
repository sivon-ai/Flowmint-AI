import psycopg2
from app.database import Base
import app.models

conn = psycopg2.connect(host='localhost', port=5434, user='flowmint', dbname='flowmint_db')
cur = conn.cursor()

# 1. Check tables
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE' ORDER BY table_name;")
db_tables = set(r[0] for r in cur.fetchall()) - {'alembic_version'}
model_tables = set(Base.metadata.tables.keys())

print(f"Model tables ({len(model_tables)}): {sorted(model_tables)}")
print(f"DB tables ({len(db_tables)}): {sorted(db_tables)}")
assert model_tables == db_tables, f"Mismatch! Missing: {model_tables - db_tables}, Extra: {db_tables - model_tables}"

# 2. Check extensions
cur.execute("SELECT extname FROM pg_extension;")
extensions = [r[0] for r in cur.fetchall()]
print(f"\nInstalled extensions: {extensions}")
assert "pg_trgm" in extensions, "pg_trgm extension missing"
assert "uuid-ossp" in extensions, "uuid-ossp extension missing"

# 3. Check check constraints on inventory
cur.execute("SELECT conname FROM pg_constraint WHERE conrelid = 'inventory'::regclass AND contype = 'c';")
checks = [r[0] for r in cur.fetchall()]
print(f"\nInventory check constraints: {checks}")
assert "ck_inventory_quantity_positive" in checks
assert "ck_inventory_reserved_positive" in checks
assert "ck_inventory_reserved_lte_quantity" in checks

# 4. Check composite unique constraints
cur.execute("SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint WHERE contype = 'u';")
uqs = {r[0]: r[1] for r in cur.fetchall()}
print("\nUnique constraints in live database:")
for name, definition in sorted(uqs.items()):
    print(f"  {name}: {definition}")

# Verify critical composite constraints
assert "uq_product_merchant_slug" in uqs
assert "uq_product_merchant_sku" in uqs
assert "uq_category_merchant_slug" in uqs
assert "uq_customer_merchant_email" in uqs
assert "uq_user_merchant_email" in uqs
assert "uq_order_merchant_number" in uqs
assert "uq_payment_merchant_idempotency" in uqs
assert "uq_cart_item_product" in uqs

cur.close()
conn.close()
print("\n>>> LIVE SCHEMA VERIFICATION SUCCESS: All 14 tables, constraints, extensions, and check constraints verified against live PostgreSQL! <<<")
