"""
Flowmint AI — Product Catalog Import Service.

Production-grade bulk catalog ingestion supporting:
- Tabular spreadsheets (.xlsx, .csv) with multiple worksheets & dynamic header mapping.
- Structured documents (.docx, .pdf) with table & structured text extraction.
- Strict tenant data isolation scoped to merchant_id.
- Two-phase import workflow: preview/validation -> confirmed atomic execution.
- Deterministic duplicate resolution (skip or update) with full rollback safety.
"""

from __future__ import annotations

import csv
import io
import re
import uuid
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ValidationError
from app.events.bus import DomainEvent, event_bus
from app.events.types import EventType
from app.models.category import Category
from app.models.inventory import Inventory
from app.models.outbox import OutboxEvent
from app.models.product import Product
from app.schemas.product import (
    ProductImportConfirmRequest,
    ProductImportConfirmRow,
    ProductImportParseResponse,
    ProductImportResult,
    ProductImportRow,
    ProductImportSummary,
)
from app.services.product import _slugify

# File Processing Constraints
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_ROW_COUNT = 1000  # Max records per batch
MAX_PDF_PAGES = 25

# Canonical Header Synonym Dictionary for Autonomous Column Mapping
HEADER_SYNONYMS: dict[str, list[str]] = {
    "name": [
        "product name", "product_name", "product", "name", "title",
        "item name", "item_name", "item", "product_title", "model",
        "product description / name", "device",
    ],
    "sku": [
        "sku", "product code", "product_code", "item code", "item_code",
        "code", "barcode", "upc", "identifier", "sku_code", "part number",
        "model number", "article number",
    ],
    "price": [
        "price", "selling price", "selling_price", "unit price", "unit_price",
        "mrp", "rate", "cost", "amount", "sale price", "regular price",
        "price inr", "price (inr)", "price (₹)", "price_inr",
    ],
    "compare_at_price": [
        "compare at price", "compare_at_price", "original price", "original_price",
        "list price", "list_price", "old price", "strikethrough price", "market price",
    ],
    "stock": [
        "stock", "stock quantity", "stock_quantity", "quantity", "qty",
        "inventory", "initial stock", "available stock", "units", "count",
        "stock qty", "opening stock",
    ],
    "description": [
        "description", "product description", "details", "desc", "about",
        "summary", "specs", "specifications", "features",
    ],
    "category": [
        "category", "category name", "product category", "collection",
        "dept", "department", "type", "genre", "classification",
    ],
    "status": [
        "status", "state", "active", "availability",
    ],
}


def _clean_str(val: Any) -> str:
    """Normalize cell to string, stripping whitespace."""
    if val is None:
        return ""
    return str(val).strip()


def _parse_numeric_price(val: Any) -> Decimal | None:
    """Safely parse price values preserving decimal precision and stripping currency formatting."""
    if val is None or val == "":
        return None
    if isinstance(val, (int, float, Decimal)):
        try:
            return round(Decimal(str(val)), 2)
        except InvalidOperation:
            return None

    cleaned = str(val).strip()
    # Remove currency symbols (₹, $, €, £), commas, spaces
    cleaned = re.sub(r"[^\d.-]", "", cleaned)
    if not cleaned or cleaned == "-" or cleaned == ".":
        return None
    try:
        dec = Decimal(cleaned)
        return round(dec, 2)
    except (InvalidOperation, ValueError):
        return None


def _parse_stock_int(val: Any) -> int | None:
    """Parse stock integer while strictly preserving legitimate 0 values."""
    if val is None or val == "":
        return 0
    if isinstance(val, bool):
        return None
    if isinstance(val, int):
        return val
    if isinstance(val, float):
        return int(val)

    cleaned = str(val).strip()
    cleaned = re.sub(r"[^\d-]", "", cleaned)
    if not cleaned:
        return 0
    try:
        return int(cleaned)
    except ValueError:
        return None


class CatalogImportService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def parse_and_preview(
        self,
        file_bytes: bytes,
        filename: str,
        merchant_id: uuid.UUID,
        sheet_name: str | None = None,
    ) -> ProductImportParseResponse:
        """
        Validate, extract, map, and preview catalog records from uploaded file.
        Does NOT write to database.
        """
        file_size = len(file_bytes)
        if file_size == 0:
            raise ValidationError("The uploaded file is empty (0 bytes).")
        if file_size > MAX_FILE_SIZE:
            raise ValidationError(
                f"File size exceeds maximum allowed limit of {MAX_FILE_SIZE // (1024 * 1024)}MB."
            )

        lower_name = filename.lower()
        sheets: list[str] = []
        selected_sheet: str | None = None
        raw_headers: list[str] = []
        raw_rows: list[list[Any]] = []
        fmt: str = ""

        # 1. Format Detection & Parser Dispatch
        if lower_name.endswith(".csv"):
            fmt = "csv"
            raw_headers, raw_rows = self._extract_csv(file_bytes)
        elif lower_name.endswith(".xlsx"):
            fmt = "xlsx"
            self._validate_zip_signature(file_bytes, "Excel (.xlsx)")
            sheets, selected_sheet, raw_headers, raw_rows = self._extract_xlsx(
                file_bytes, sheet_name
            )
        elif lower_name.endswith(".docx"):
            fmt = "docx"
            self._validate_zip_signature(file_bytes, "Word (.docx)")
            raw_headers, raw_rows = self._extract_docx(file_bytes)
        elif lower_name.endswith(".pdf"):
            fmt = "pdf"
            self._validate_pdf_signature(file_bytes)
            raw_headers, raw_rows = self._extract_pdf(file_bytes)
        else:
            raise ValidationError(
                "Unsupported file format. Please upload .xlsx, .csv, .docx, or .pdf files."
            )

        if not raw_headers and not raw_rows:
            raise ValidationError(
                f"No tabular product records or extractable data could be found in '{filename}'."
            )

        # 2. Header Mapping
        column_mapping = self._map_columns(raw_headers)
        warnings: list[str] = []
        if "name" not in column_mapping:
            warnings.append("Could not confidently identify a 'Product Name' column.")
        if "price" not in column_mapping:
            warnings.append("Could not confidently identify a 'Price' column.")

        # 3. Row Normalization
        name_idx = column_mapping.get("name")
        sku_idx = column_mapping.get("sku")
        price_idx = column_mapping.get("price")
        compare_idx = column_mapping.get("compare_at_price")
        stock_idx = column_mapping.get("stock")
        desc_idx = column_mapping.get("description")
        cat_idx = column_mapping.get("category")
        status_idx = column_mapping.get("status")

        extracted_rows: list[ProductImportRow] = []
        seen_skus: set[str] = set()
        candidate_skus: set[str] = set()

        for idx, row in enumerate(raw_rows[:MAX_ROW_COUNT], start=1):
            # Check for completely empty row
            if not any(_clean_str(cell) for cell in row):
                continue

            row_dict = {}
            for col_name, col_header in column_mapping.items():
                if col_header in raw_headers:
                    c_idx = raw_headers.index(col_header)
                    if c_idx < len(row):
                        row_dict[col_name] = row[c_idx]

            name = _clean_str(row_dict.get("name", ""))
            raw_sku = _clean_str(row_dict.get("sku", ""))
            price_dec = _parse_numeric_price(row_dict.get("price"))
            compare_dec = _parse_numeric_price(row_dict.get("compare_at_price"))
            stock_int = _parse_stock_int(row_dict.get("stock"))
            desc = _clean_str(row_dict.get("description", "")) or None
            cat_name = _clean_str(row_dict.get("category", "")) or None
            status_val = _clean_str(row_dict.get("status", "active")).lower()
            if status_val not in ("active", "draft", "archived"):
                status_val = "active"

            errors: list[str] = []
            if not name:
                errors.append("Product name is required.")
            elif len(name) > 500:
                errors.append("Product name exceeds 500 characters.")

            if not raw_sku:
                errors.append("SKU is required.")
            elif len(raw_sku) > 100:
                errors.append("SKU exceeds 100 characters.")

            if price_dec is None:
                errors.append("Price is required and must be a valid number.")
            elif price_dec <= Decimal("0"):
                errors.append("Price must be greater than 0.")

            if compare_dec is not None and compare_dec <= Decimal("0"):
                errors.append("Compare at price must be greater than 0.")

            if stock_int is None or stock_int < 0:
                errors.append("Stock quantity must be a non-negative integer.")
                stock_int = 0

            # File duplicate detection
            validation_status = "valid"
            if raw_sku:
                if raw_sku.lower() in seen_skus:
                    validation_status = "file_duplicate"
                    errors.append(f"SKU '{raw_sku}' appears multiple times in this file.")
                else:
                    seen_skus.add(raw_sku.lower())
                    candidate_skus.add(raw_sku)

            if errors and validation_status == "valid":
                validation_status = "invalid"

            extracted_rows.append(
                ProductImportRow(
                    row_index=idx,
                    name=name,
                    sku=raw_sku,
                    price=price_dec,
                    compare_at_price=compare_dec,
                    stock=stock_int,
                    description=desc,
                    category_name=cat_name,
                    status=status_val,
                    validation_status=validation_status,
                    validation_errors=errors,
                    is_existing=False,
                    existing_product_id=None,
                )
            )

        # 4. Check for Existing Database Products within Current Merchant
        existing_map: dict[str, uuid.UUID] = {}
        if candidate_skus:
            stmt = select(Product.id, Product.sku).where(
                Product.merchant_id == merchant_id,
                Product.sku.in_(list(candidate_skus)),
            )
            res = await self.db.execute(stmt)
            for prod_id, prod_sku in res.all():
                existing_map[prod_sku.lower()] = prod_id

        # Update duplicate status for existing products
        for r in extracted_rows:
            if r.sku and r.sku.lower() in existing_map:
                r.is_existing = True
                r.existing_product_id = existing_map[r.sku.lower()]
                if r.validation_status == "valid":
                    r.validation_status = "duplicate"
                    r.validation_errors.append(
                        f"SKU '{r.sku}' matches an existing product in your catalog."
                    )

        # 5. Build Summary Statistics
        total_rows = len(extracted_rows)
        valid_rows = sum(1 for r in extracted_rows if r.validation_status == "valid")
        duplicate_rows = sum(1 for r in extracted_rows if r.validation_status == "duplicate")
        file_duplicate_rows = sum(
            1 for r in extracted_rows if r.validation_status == "file_duplicate"
        )
        invalid_rows = sum(1 for r in extracted_rows if r.validation_status == "invalid")

        summary = ProductImportSummary(
            total_rows=total_rows,
            valid_rows=valid_rows,
            invalid_rows=invalid_rows,
            duplicate_rows=duplicate_rows,
            file_duplicate_rows=file_duplicate_rows,
            existing_skus_found=list(existing_map.keys()),
        )

        return ProductImportParseResponse(
            file_name=filename,
            file_size=file_size,
            format=fmt,
            sheets=sheets,
            selected_sheet=selected_sheet,
            headers=raw_headers,
            column_mapping=column_mapping,
            summary=summary,
            rows=extracted_rows,
            warnings=warnings,
        )

    async def confirm_import(
        self,
        merchant_id: uuid.UUID,
        request: ProductImportConfirmRequest,
    ) -> ProductImportResult:
        """
        Persist confirmed products into database with transaction safety and duplicate resolution.
        """
        imported_count = 0
        updated_count = 0
        skipped_count = 0
        failed_count = 0
        errors: list[str] = []

        # Cache existing categories for this merchant
        cat_stmt = select(Category).where(Category.merchant_id == merchant_id)
        cat_res = await self.db.execute(cat_stmt)
        categories = {c.name.lower(): c for c in cat_res.scalars().all()}

        # Load existing products for matching
        input_skus = [r.sku.strip() for r in request.rows if r.sku]
        existing_products: dict[str, Product] = {}
        if input_skus:
            prod_stmt = (
                select(Product)
                .options(selectinload(Product.inventory))
                .where(
                    Product.merchant_id == merchant_id,
                    Product.sku.in_(input_skus),
                )
            )
            prod_res = await self.db.execute(prod_stmt)
            for p in prod_res.scalars().all():
                existing_products[p.sku.lower()] = p

        processed_skus_in_batch: set[str] = set()

        for idx, row in enumerate(request.rows, start=1):
            sku_clean = row.sku.strip()
            sku_key = sku_clean.lower()

            # Prevent intra-batch duplicates from corrupting unique constraints
            if sku_key in processed_skus_in_batch:
                skipped_count += 1
                errors.append(f"Row {idx} skipped: Duplicate SKU '{sku_clean}' in same import payload.")
                continue
            processed_skus_in_batch.add(sku_key)

            # Re-validate fields at write time
            if not row.name or not row.name.strip():
                failed_count += 1
                errors.append(f"Row {idx}: Name cannot be empty.")
                continue

            if not row.sku or not row.sku.strip():
                failed_count += 1
                errors.append(f"Row {idx}: SKU cannot be empty.")
                continue

            if row.price <= Decimal("0"):
                failed_count += 1
                errors.append(f"Row {idx}: Price must be greater than 0.")
                continue

            # Resolve Category
            category_id: uuid.UUID | None = None
            if row.category_name and row.category_name.strip():
                cat_clean = row.category_name.strip()
                cat_key = cat_clean.lower()
                if cat_key in categories:
                    category_id = categories[cat_key].id
                else:
                    new_cat = Category(
                        merchant_id=merchant_id,
                        name=cat_clean,
                        slug=_slugify(cat_clean),
                    )
                    self.db.add(new_cat)
                    await self.db.flush()
                    categories[cat_key] = new_cat
                    category_id = new_cat.id

            # Existing Product Resolution
            if sku_key in existing_products:
                if request.duplicate_resolution == "skip":
                    skipped_count += 1
                    continue
                elif request.duplicate_resolution == "update":
                    existing_p = existing_products[sku_key]
                    existing_p.name = row.name.strip()
                    existing_p.price = row.price
                    existing_p.compare_at_price = row.compare_at_price
                    if row.description is not None:
                        existing_p.description = row.description
                    if category_id is not None:
                        existing_p.category_id = category_id
                    existing_p.status = row.status

                    if existing_p.inventory:
                        existing_p.inventory.quantity = row.stock
                    else:
                        self.db.add(
                            Inventory(
                                product_id=existing_p.id,
                                merchant_id=merchant_id,
                                quantity=row.stock,
                                reserved=0,
                            )
                        )

                    self.db.add(
                        OutboxEvent(
                            event_type=EventType.PRODUCT_UPDATED,
                            aggregate_type="product",
                            aggregate_id=str(existing_p.id),
                            payload={"merchant_id": str(merchant_id), "sku": sku_clean, "action": "import_update"},
                        )
                    )
                    updated_count += 1
                    continue

            # Create New Product
            slug = _slugify(row.name.strip())
            # Slug uniqueness check
            slug_stmt = select(Product.id).where(
                Product.merchant_id == merchant_id,
                Product.slug == slug,
            )
            if (await self.db.execute(slug_stmt)).scalar_one_or_none():
                slug = f"{slug}-{uuid.uuid4().hex[:6]}"

            new_prod = Product(
                merchant_id=merchant_id,
                category_id=category_id,
                name=row.name.strip(),
                slug=slug,
                description=row.description,
                sku=sku_clean,
                price=row.price,
                compare_at_price=row.compare_at_price,
                currency="INR",
                status=row.status,
            )
            self.db.add(new_prod)
            await self.db.flush()

            # Create Inventory Record
            inventory = Inventory(
                product_id=new_prod.id,
                merchant_id=merchant_id,
                quantity=row.stock,
                reserved=0,
            )
            self.db.add(inventory)

            # Record Outbox Event
            self.db.add(
                OutboxEvent(
                    event_type=EventType.PRODUCT_CREATED,
                    aggregate_type="product",
                    aggregate_id=str(new_prod.id),
                    payload={"merchant_id": str(merchant_id), "product_name": new_prod.name, "action": "import_create"},
                )
            )

            imported_count += 1

        # Commit all batched operations atomically
        await self.db.commit()

        # Emit domain event for real-time subscribers
        await event_bus.publish(
            DomainEvent(
                event_type=EventType.PRODUCT_CREATED,
                aggregate_type="catalog_import",
                aggregate_id=str(merchant_id),
                payload={
                    "imported_count": imported_count,
                    "updated_count": updated_count,
                    "skipped_count": skipped_count,
                },
                merchant_id=str(merchant_id),
            )
        )

        return ProductImportResult(
            imported_count=imported_count,
            updated_count=updated_count,
            skipped_count=skipped_count,
            failed_count=failed_count,
            errors=errors,
        )

    # --- Parser Implementations ---

    def _extract_csv(self, file_bytes: bytes) -> tuple[list[str], list[list[Any]]]:
        """Extract headers and rows from CSV, detecting encoding and delimiters."""
        # Try decodings
        text = ""
        for encoding in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
            try:
                text = file_bytes.decode(encoding)
                break
            except UnicodeDecodeError:
                continue

        if not text:
            raise ValidationError("Could not decode CSV text content. Please ensure valid UTF-8 encoding.")

        # Detect delimiter
        sample = text[:4096]
        delimiter = ","
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            delimiter = dialect.delimiter
        except Exception:
            if "\t" in sample and "," not in sample:
                delimiter = "\t"
            elif ";" in sample and "," not in sample:
                delimiter = ";"

        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        raw_rows = [row for row in reader if any(cell.strip() for cell in row)]
        if not raw_rows:
            return [], []

        headers = [_clean_str(h) for h in raw_rows[0]]
        data_rows = raw_rows[1:]
        return headers, data_rows

    def _extract_xlsx(
        self, file_bytes: bytes, sheet_name: str | None
    ) -> tuple[list[str], str | None, list[str], list[list[Any]]]:
        """Extract headers, available sheets, and rows from openpyxl workbook."""
        try:
            import openpyxl
        except ImportError:
            raise ValidationError("openpyxl library is required for Excel parsing.")

        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True, read_only=True)
        sheets = wb.sheetnames
        if not sheets:
            return [], None, [], []

        selected = sheet_name if (sheet_name and sheet_name in sheets) else sheets[0]
        ws = wb[selected]

        rows: list[list[Any]] = []
        for r in ws.iter_rows(values_only=True):
            if any(cell is not None and str(cell).strip() != "" for cell in r):
                rows.append([cell if cell is not None else "" for cell in r])

        wb.close()
        if not rows:
            return sheets, selected, [], []

        headers = [_clean_str(h) for h in rows[0]]
        data_rows = rows[1:]
        return sheets, selected, headers, data_rows

    def _extract_docx(self, file_bytes: bytes) -> tuple[list[str], list[list[Any]]]:
        """Extract product table or structured text lines from Word document."""
        try:
            import docx
        except ImportError:
            raise ValidationError("python-docx library is required for Word document parsing.")

        doc = docx.Document(io.BytesIO(file_bytes))

        # Check for Tables first (preferred structured format in Word documents)
        for table in doc.tables:
            t_rows: list[list[str]] = []
            for row in table.rows:
                cells = [_clean_str(cell.text) for cell in row.cells]
                if any(cells):
                    t_rows.append(cells)
            if len(t_rows) >= 2:
                headers = t_rows[0]
                data_rows = t_rows[1:]
                return headers, data_rows

        # Fallback to Paragraph Structured Line Extraction
        lines = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        if not lines:
            raise ValidationError("The Word document contains no readable text or product tables.")

        headers, data_rows = self._extract_structured_text_lines(lines)
        return headers, data_rows

    def _extract_pdf(self, file_bytes: bytes) -> tuple[list[str], list[list[Any]]]:
        """Extract digital text and tabular lines from PDF document."""
        try:
            import pypdf
        except ImportError:
            raise ValidationError("pypdf library is required for PDF parsing.")

        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        total_pages = min(len(reader.pages), MAX_PDF_PAGES)
        full_text = ""
        for i in range(total_pages):
            page_text = reader.pages[i].extract_text() or ""
            full_text += "\n" + page_text

        # Detect Scanned / Non-Text PDF Limitation
        if len(full_text.strip()) < 20:
            raise ValidationError(
                "The uploaded PDF appears to be a scanned image or contains no digital text. "
                "OCR is not available. Please upload a spreadsheet (.xlsx, .csv) or text-searchable PDF."
            )

        lines = [line.strip() for line in full_text.splitlines() if line.strip()]
        return self._extract_structured_text_lines(lines)

    def _extract_structured_text_lines(
        self, lines: list[str]
    ) -> tuple[list[str], list[list[Any]]]:
        """
        Parse structured lines from PDF or Word paragraphs.
        Supports pipe/comma/tab delimited rows, or key-value product blocks.
        """
        # 1. Check if lines look like delimited table rows
        delim_counts = {",": 0, "\t": 0, "|": 0}
        for l in lines[:10]:
            for d in delim_counts:
                if d in l:
                    delim_counts[d] += 1

        best_delim = max(delim_counts, key=delim_counts.get)
        if delim_counts[best_delim] >= 3:
            raw_rows = []
            for l in lines:
                parts = [_clean_str(p) for p in l.split(best_delim)]
                if any(parts):
                    raw_rows.append(parts)
            if len(raw_rows) >= 2:
                return raw_rows[0], raw_rows[1:]

        # 2. Key-Value or Heuristic Line Parsing
        # Pattern: [Name / Title] [SKU] [Price] [Stock]
        headers = ["name", "sku", "price", "stock", "description"]
        data_rows: list[list[Any]] = []

        # Look for lines containing price patterns (e.g. ₹499 or INR 1,200 or $45.00)
        price_regex = re.compile(r"(?:₹|inr|\$)\s*([\d,]+(?:\.\d{1,2})?)", re.IGNORECASE)
        sku_regex = re.compile(r"\b([A-Z0-9]{3,}-[A-Z0-9]+)\b")

        for line in lines:
            price_match = price_regex.search(line)
            if not price_match:
                continue

            price_str = price_match.group(1).replace(",", "")
            sku_match = sku_regex.search(line)
            sku_val = sku_match.group(1) if sku_match else ""

            # Name is text preceding the price or SKU
            line_without_price = price_regex.sub("", line).strip(" -|,")
            if sku_match:
                line_without_price = sku_regex.sub("", line_without_price).strip(" -|,")

            name_val = line_without_price[:100].strip() or "Imported Product"

            data_rows.append([name_val, sku_val, price_str, "0", ""])

        if not data_rows:
            raise ValidationError(
                "Could not extract structured product items from the document text. "
                "Ensure prices and product names are clearly formatted."
            )

        return headers, data_rows

    def _map_columns(self, headers: list[str]) -> dict[str, str]:
        """Map raw headers to canonical fields using synonym matching."""
        mapping: dict[str, str] = {}
        used_headers: set[str] = set()

        # Step 1: Exact Match
        for canonical, synonyms in HEADER_SYNONYMS.items():
            for raw in headers:
                if raw in used_headers:
                    continue
                norm_raw = re.sub(r"[_\s-]+", " ", raw.lower().strip())
                if norm_raw in synonyms:
                    mapping[canonical] = raw
                    used_headers.add(raw)
                    break

        # Step 2: Substring / Word Match for unmapped fields
        for canonical, synonyms in HEADER_SYNONYMS.items():
            if canonical in mapping:
                continue
            for raw in headers:
                if raw in used_headers:
                    continue
                norm_raw = re.sub(r"[_\s-]+", " ", raw.lower().strip())
                for syn in synonyms:
                    if syn in norm_raw or norm_raw in syn:
                        mapping[canonical] = raw
                        used_headers.add(raw)
                        break
                if canonical in mapping:
                    break

        return mapping

    def _validate_zip_signature(self, file_bytes: bytes, file_type: str) -> None:
        """Validate PK zip header for Office Open XML documents."""
        if not file_bytes.startswith(b"PK\x03\x04"):
            raise ValidationError(
                f"The uploaded file is not a valid {file_type} document (missing ZIP container signature)."
            )

    def _validate_pdf_signature(self, file_bytes: bytes) -> None:
        """Validate %PDF header."""
        if not file_bytes.startswith(b"%PDF"):
            raise ValidationError(
                "The uploaded file is not a valid PDF document (missing %PDF signature)."
            )
