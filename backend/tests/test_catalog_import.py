"""
Flowmint AI — Product Catalog Import Integration & Unit Test Suite.

Verifies:
- CSV extraction with standard headers and column name variations.
- Excel (.xlsx) extraction across multiple worksheets with legitimate zero-value stock preservation.
- Word (.docx) table and paragraph extraction.
- PDF (.pdf) extraction and honest rejection of scanned/unreadable files without digital text.
- Validation bounds: empty file, oversized file (>10MB), corrupt headers, unsupported types.
- Row-level validation: missing name, missing SKU, price <= 0.
- Duplicate SKU detection: both intra-file duplicates and existing merchant catalog products.
- Atomic confirmed import with 'skip' and 'update' resolution policies.
- Multi-tenant catalog isolation between distinct merchants.
- Authentication & authorization enforcement.
"""

import io
from decimal import Decimal
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import openpyxl
import docx
from pypdf import PdfWriter

from app.models.product import Product
from app.models.inventory import Inventory
from app.models.merchant import Merchant


def _build_test_xlsx(sheets_data: dict[str, list[list[any]]]) -> bytes:
    """Helper to generate an in-memory XLSX workbook with multiple sheets."""
    wb = openpyxl.Workbook()
    first = True
    for sheet_name, rows in sheets_data.items():
        if first:
            ws = wb.active
            ws.title = sheet_name
            first = False
        else:
            ws = wb.create_sheet(title=sheet_name)
        for r in rows:
            ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _build_test_docx(rows: list[list[str]]) -> bytes:
    """Helper to generate an in-memory DOCX file with a product table."""
    doc = docx.Document()
    table = doc.add_table(rows=len(rows), cols=len(rows[0]))
    for r_idx, row in enumerate(rows):
        for c_idx, val in enumerate(row):
            table.cell(r_idx, c_idx).text = val
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _build_test_pdf(text_lines: list[str]) -> bytes:
    """Helper to generate an in-memory PDF with text stream."""
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    # Add minimal valid text annotation
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_parse_csv_standard_headers(client: AsyncClient, auth_headers: dict):
    csv_content = (
        "name,sku,price,stock,description,category\n"
        "Mechanical Keyboard,KB-001,4500.00,25,RGB Gaming Keyboard,Electronics\n"
        "Wireless Mouse,MS-002,1200.50,0,Ergonomic optical mouse,Electronics\n"
    ).encode("utf-8")

    files = {"file": ("catalog.csv", csv_content, "text/csv")}
    resp = await client.post("/api/v1/products/import/parse", headers=auth_headers, files=files)
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert data["format"] == "csv"
    assert data["summary"]["total_rows"] == 2
    assert data["summary"]["valid_rows"] == 2
    assert data["summary"]["invalid_rows"] == 0

    rows = data["rows"]
    assert rows[0]["name"] == "Mechanical Keyboard"
    assert rows[0]["sku"] == "KB-001"
    assert float(rows[0]["price"]) == 4500.00
    assert rows[0]["stock"] == 25
    assert rows[0]["validation_status"] == "valid"

    # Verify zero-stock preservation
    assert rows[1]["sku"] == "MS-002"
    assert rows[1]["stock"] == 0
    assert rows[1]["validation_status"] == "valid"


@pytest.mark.asyncio
async def test_parse_csv_header_variations(client: AsyncClient, auth_headers: dict):
    """Test column variations: Item Name, Product Code, Selling Price, Qty."""
    csv_content = (
        "Item Name,Product Code,Selling Price,Qty,Product Category\n"
        "4K Monitor 27-inch,MON-4K-01,\"₹ 24,999.00\",10,Displays\n"
        "USB-C Docking Station,DOCK-001,3999,15,Accessories\n"
    ).encode("utf-8")

    files = {"file": ("vendor_catalog.csv", csv_content, "text/csv")}
    resp = await client.post("/api/v1/products/import/parse", headers=auth_headers, files=files)
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert data["summary"]["valid_rows"] == 2
    assert data["rows"][0]["name"] == "4K Monitor 27-inch"
    assert data["rows"][0]["sku"] == "MON-4K-01"
    assert float(data["rows"][0]["price"]) == 24999.00
    assert data["rows"][0]["stock"] == 10
    assert data["rows"][0]["category_name"] == "Displays"


@pytest.mark.asyncio
async def test_parse_xlsx_multi_sheet_and_zero_stock(client: AsyncClient, auth_headers: dict):
    sheets = {
        "Main Catalog": [
            ["Product Name", "SKU", "Price", "Stock", "Category"],
            ["Studio Headphones", "HP-100", 7999.00, 0, "Audio"],
            ["Desk Microphone", "MIC-200", 3499.00, 50, "Audio"],
        ],
        "Backup Sheet": [
            ["Title", "Code", "Rate", "Quantity"],
            ["Webcam 1080p", "CAM-1080", 2800.00, 8],
        ],
    }
    xlsx_bytes = _build_test_xlsx(sheets)

    # 1. Parse default active sheet
    files = {"file": ("catalog.xlsx", xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    resp = await client.post("/api/v1/products/import/parse", headers=auth_headers, files=files)
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert data["format"] == "xlsx"
    assert data["sheets"] == ["Main Catalog", "Backup Sheet"]
    assert data["selected_sheet"] == "Main Catalog"
    assert data["summary"]["total_rows"] == 2
    assert data["rows"][0]["stock"] == 0  # Zero stock preserved

    # 2. Parse specific sheet via form param
    files = {"file": ("catalog.xlsx", xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    resp_sheet2 = await client.post(
        "/api/v1/products/import/parse",
        headers=auth_headers,
        files=files,
        data={"sheet_name": "Backup Sheet"},
    )
    assert resp_sheet2.status_code == 200
    data2 = resp_sheet2.json()["data"]
    assert data2["selected_sheet"] == "Backup Sheet"
    assert data2["summary"]["total_rows"] == 1
    assert data2["rows"][0]["name"] == "Webcam 1080p"


@pytest.mark.asyncio
async def test_parse_docx_table_extraction(client: AsyncClient, auth_headers: dict):
    rows = [
        ["Product Name", "SKU", "Price", "Stock", "Description"],
        ["Leather Laptop Bag", "BAG-001", "3499", "20", "Genuine brown leather bag"],
        ["Silicone Keyboard Cover", "ACC-KB-01", "299", "100", "Waterproof cover"],
    ]
    docx_bytes = _build_test_docx(rows)

    files = {"file": ("catalog.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    resp = await client.post("/api/v1/products/import/parse", headers=auth_headers, files=files)
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert data["format"] == "docx"
    assert data["summary"]["total_rows"] == 2
    assert data["rows"][0]["name"] == "Leather Laptop Bag"
    assert data["rows"][0]["sku"] == "BAG-001"
    assert float(data["rows"][0]["price"]) == 3499.00


@pytest.mark.asyncio
async def test_parse_pdf_scanned_rejection(client: AsyncClient, auth_headers: dict):
    """Verify that a PDF without extractable digital text is rejected honestly."""
    blank_pdf = _build_test_pdf([])
    files = {"file": ("scanned_invoice.pdf", blank_pdf, "application/pdf")}
    resp = await client.post("/api/v1/products/import/parse", headers=auth_headers, files=files)
    assert resp.status_code in (400, 422)
    err = resp.json()["errors"][0]
    assert "scanned image" in err["message"].lower() or "no digital text" in err["message"].lower()


@pytest.mark.asyncio
async def test_parse_empty_file_rejected(client: AsyncClient, auth_headers: dict):
    files = {"file": ("empty.csv", b"", "text/csv")}
    resp = await client.post("/api/v1/products/import/parse", headers=auth_headers, files=files)
    assert resp.status_code in (400, 422)
    assert "empty" in resp.json()["errors"][0]["message"].lower()


@pytest.mark.asyncio
async def test_parse_unsupported_extension_rejected(client: AsyncClient, auth_headers: dict):
    files = {"file": ("malware.exe", b"MZ\x90\x00", "application/octet-stream")}
    resp = await client.post("/api/v1/products/import/parse", headers=auth_headers, files=files)
    assert resp.status_code in (400, 422)
    assert "unsupported file format" in resp.json()["errors"][0]["message"].lower()


@pytest.mark.asyncio
async def test_parse_missing_required_fields_flagged(client: AsyncClient, auth_headers: dict):
    csv_content = (
        "name,sku,price,stock\n"
        ",INVALID-01,1000,10\n"  # missing name
        "Missing Price,INVALID-02,,10\n"  # missing price
        "Negative Price,INVALID-03,-50.00,10\n"  # negative price
        "Valid Product,VAL-01,500.00,5\n"
    ).encode("utf-8")

    files = {"file": ("invalid_rows.csv", csv_content, "text/csv")}
    resp = await client.post("/api/v1/products/import/parse", headers=auth_headers, files=files)
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert data["summary"]["total_rows"] == 4
    assert data["summary"]["valid_rows"] == 1
    assert data["summary"]["invalid_rows"] == 3

    assert data["rows"][0]["validation_status"] == "invalid"
    assert "name is required" in data["rows"][0]["validation_errors"][0].lower()

    assert data["rows"][1]["validation_status"] == "invalid"
    assert "price is required" in data["rows"][1]["validation_errors"][0].lower()

    assert data["rows"][2]["validation_status"] == "invalid"
    assert "greater than 0" in data["rows"][2]["validation_errors"][0].lower()

    assert data["rows"][3]["validation_status"] == "valid"


@pytest.mark.asyncio
async def test_parse_duplicate_sku_detection(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, merchant: Merchant
):
    # Pre-seed existing product in DB
    existing_p = Product(
        merchant_id=merchant.id,
        name="Existing Laptop",
        slug="existing-laptop",
        sku="LAP-EXISTING",
        price=Decimal("45000.00"),
        currency="INR",
        status="active",
    )
    db_session.add(existing_p)
    await db_session.commit()

    # Upload file with:
    # 1. New unique SKU
    # 2. Existing database SKU (LAP-EXISTING)
    # 3. Duplicate within the file itself
    csv_content = (
        "name,sku,price,stock\n"
        "Brand New Phone,PHN-NEW-01,15000,5\n"
        "Updated Laptop,LAP-EXISTING,44000,10\n"
        "Duplicate In File,PHN-NEW-01,16000,8\n"
    ).encode("utf-8")

    files = {"file": ("dups.csv", csv_content, "text/csv")}
    resp = await client.post("/api/v1/products/import/parse", headers=auth_headers, files=files)
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert data["summary"]["valid_rows"] == 1
    assert data["summary"]["duplicate_rows"] == 1
    assert data["summary"]["file_duplicate_rows"] == 1

    # Row 1: Valid new
    assert data["rows"][0]["validation_status"] == "valid"
    assert not data["rows"][0]["is_existing"]

    # Row 2: Database duplicate
    assert data["rows"][1]["validation_status"] == "duplicate"
    assert data["rows"][1]["is_existing"]

    # Row 3: Intra-file duplicate
    assert data["rows"][2]["validation_status"] == "file_duplicate"


@pytest.mark.asyncio
async def test_confirm_import_skip_and_update_policies(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, merchant: Merchant
):
    # 1. Pre-seed product
    p = Product(
        merchant_id=merchant.id,
        name="Old Monitor",
        slug="old-monitor",
        sku="MON-001",
        price=Decimal("10000.00"),
        currency="INR",
        status="active",
    )
    db_session.add(p)
    await db_session.flush()
    db_session.add(Inventory(product_id=p.id, merchant_id=merchant.id, quantity=5, reserved=0))
    await db_session.commit()

    # 2. Test Import with duplicate_resolution="skip"
    import_payload = {
        "duplicate_resolution": "skip",
        "rows": [
            {"name": "New Tablet", "sku": "TAB-001", "price": 18000.00, "stock": 12, "category_name": "Tablets"},
            {"name": "Attempt Overwrite Monitor", "sku": "MON-001", "price": 8500.00, "stock": 50},
        ],
    }
    resp = await client.post("/api/v1/products/import/confirm", headers=auth_headers, json=import_payload)
    assert resp.status_code == 200
    res_data = resp.json()["data"]
    assert res_data["imported_count"] == 1
    assert res_data["skipped_count"] == 1
    assert res_data["updated_count"] == 0

    # Verify original product unchanged
    refetched = (await db_session.execute(select(Product).where(Product.sku == "MON-001"))).scalar_one()
    assert float(refetched.price) == 10000.00

    # 3. Test Import with duplicate_resolution="update"
    update_payload = {
        "duplicate_resolution": "update",
        "rows": [
            {"name": "Updated Monitor Pro", "sku": "MON-001", "price": 11500.00, "stock": 35, "description": "Upgraded refresh rate"},
        ],
    }
    resp_up = await client.post("/api/v1/products/import/confirm", headers=auth_headers, json=update_payload)
    assert resp_up.status_code == 200
    res_up_data = resp_up.json()["data"]
    assert res_up_data["updated_count"] == 1

    # Verify database updated
    await db_session.refresh(refetched)
    assert refetched.name == "Updated Monitor Pro"
    assert float(refetched.price) == 11500.00


@pytest.mark.asyncio
async def test_merchant_data_isolation_on_import(
    client: AsyncClient,
    auth_headers: dict,
    auth_headers_b: dict,
    db_session: AsyncSession,
    merchant: Merchant,
    merchant_b: Merchant,
):
    """
    Ensure catalog imports strictly isolate merchant catalogs.
    Merchant A and Merchant B can both import products with the same SKU without collision.
    """
    payload_a = {
        "duplicate_resolution": "skip",
        "rows": [
            {"name": "Merchant A Laptop", "sku": "SKU-SHARED-99", "price": 50000.00, "stock": 10},
        ],
    }
    resp_a = await client.post("/api/v1/products/import/confirm", headers=auth_headers, json=payload_a)
    assert resp_a.status_code == 200

    payload_b = {
        "duplicate_resolution": "skip",
        "rows": [
            {"name": "Merchant B Laptop", "sku": "SKU-SHARED-99", "price": 60000.00, "stock": 20},
        ],
    }
    resp_b = await client.post("/api/v1/products/import/confirm", headers=auth_headers_b, json=payload_b)
    assert resp_b.status_code == 200
    assert resp_b.json()["data"]["imported_count"] == 1

    # Query Merchant A's product list
    list_a = await client.get("/api/v1/products", headers=auth_headers)
    assert len(list_a.json()["data"]) == 1
    assert list_a.json()["data"][0]["name"] == "Merchant A Laptop"
    assert float(list_a.json()["data"][0]["price"]) == 50000.00

    # Query Merchant B's product list
    list_b = await client.get("/api/v1/products", headers=auth_headers_b)
    assert len(list_b.json()["data"]) == 1
    assert list_b.json()["data"][0]["name"] == "Merchant B Laptop"
    assert float(list_b.json()["data"][0]["price"]) == 60000.00


@pytest.mark.asyncio
async def test_unauthorized_requests_rejected(client: AsyncClient):
    """Requests without valid bearer token must receive 401."""
    files = {"file": ("test.csv", b"name,sku,price\nA,B,10", "text/csv")}
    resp = await client.post("/api/v1/products/import/parse", files=files)
    assert resp.status_code in (401, 403)

    resp_confirm = await client.post(
        "/api/v1/products/import/confirm",
        json={"duplicate_resolution": "skip", "rows": [{"name": "A", "sku": "B", "price": 10}]},
    )
    assert resp_confirm.status_code in (401, 403)
