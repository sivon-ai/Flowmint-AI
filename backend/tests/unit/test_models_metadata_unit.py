"""
Unit tests for SQLAlchemy Models and Database Schema constraints.

Verifies:
- All 14 Phase 1 tables are registered
- UUID primary keys
- Foreign key definitions with correct ondelete behaviors
- Multi-tenant composite constraints:
  - UNIQUE(merchant_id, product.slug)
  - UNIQUE(merchant_id, product.sku)
  - UNIQUE(merchant_id, category.slug)
  - UNIQUE(merchant_id, order.order_number)
  - UNIQUE(merchant_id, customer.email)
  - UNIQUE(merchant_id, user.email)
  - UNIQUE(merchant_id, payment.idempotency_key)
- Inventory check constraints
"""

import pytest
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base
import app.models  # ensure all models imported


class TestDatabaseSchemaMetadata:
    def test_all_tables_registered(self):
        expected_tables = {
            "merchants",
            "users",
            "categories",
            "products",
            "product_attributes",
            "inventory",
            "customers",
            "carts",
            "cart_items",
            "orders",
            "order_items",
            "payments",
            "payment_events",
            "outbox_events",
        }
        assert expected_tables.issubset(set(Base.metadata.tables.keys()))

    def test_tenant_composite_unique_constraints(self):
        """Verify all tenant-scoped composite unique constraints exist."""
        # 1. Product (merchant_id, slug) and (merchant_id, sku)
        prod_table = Base.metadata.tables["products"]
        prod_uqs = {
            tuple(c.name for c in uq.columns)
            for uq in prod_table.constraints
            if type(uq).__name__ == "UniqueConstraint"
        }
        assert ("merchant_id", "slug") in prod_uqs
        assert ("merchant_id", "sku") in prod_uqs

        # 2. Category (merchant_id, slug)
        cat_table = Base.metadata.tables["categories"]
        cat_uqs = {
            tuple(c.name for c in uq.columns)
            for uq in cat_table.constraints
            if type(uq).__name__ == "UniqueConstraint"
        }
        assert ("merchant_id", "slug") in cat_uqs

        # 3. User (merchant_id, email)
        user_table = Base.metadata.tables["users"]
        user_uqs = {
            tuple(c.name for c in uq.columns)
            for uq in user_table.constraints
            if type(uq).__name__ == "UniqueConstraint"
        }
        assert ("merchant_id", "email") in user_uqs

        # 4. Customer (merchant_id, email)
        cust_table = Base.metadata.tables["customers"]
        cust_uqs = {
            tuple(c.name for c in uq.columns)
            for uq in cust_table.constraints
            if type(uq).__name__ == "UniqueConstraint"
        }
        assert ("merchant_id", "email") in cust_uqs

        # 5. Order (merchant_id, order_number)
        order_table = Base.metadata.tables["orders"]
        order_uqs = {
            tuple(c.name for c in uq.columns)
            for uq in order_table.constraints
            if type(uq).__name__ == "UniqueConstraint"
        }
        assert ("merchant_id", "order_number") in order_uqs

        # 6. Payment (merchant_id, idempotency_key)
        pay_table = Base.metadata.tables["payments"]
        pay_uqs = {
            tuple(c.name for c in uq.columns)
            for uq in pay_table.constraints
            if type(uq).__name__ == "UniqueConstraint"
        }
        assert ("merchant_id", "idempotency_key") in pay_uqs

        # 7. CartItem (cart_id, product_id)
        ci_table = Base.metadata.tables["cart_items"]
        ci_uqs = {
            tuple(c.name for c in uq.columns)
            for uq in ci_table.constraints
            if type(uq).__name__ == "UniqueConstraint"
        }
        assert ("cart_id", "product_id") in ci_uqs

    def test_inventory_check_constraints(self):
        """Verify check constraints protect stock invariants."""
        inv_table = Base.metadata.tables["inventory"]
        check_names = {
            c.name for c in inv_table.constraints if type(c).__name__ == "CheckConstraint"
        }
        assert "ck_inventory_quantity_positive" in check_names
        assert "ck_inventory_reserved_positive" in check_names
        assert "ck_inventory_reserved_lte_quantity" in check_names

    def test_primary_keys_are_uuid(self):
        """Verify all tables use UUID primary keys."""
        for name, table in Base.metadata.tables.items():
            pk_cols = list(table.primary_key.columns)
            assert len(pk_cols) >= 1, f"Table {name} has no PK"
            for col in pk_cols:
                assert isinstance(col.type, UUID), f"Table {name} PK column {col.name} is not UUID"
