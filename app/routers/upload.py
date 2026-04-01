import html
import os
import tempfile
from datetime import date as DateType
from datetime import datetime

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import require_user_email
from app.db.session import get_db
from app.models.expense import Expense, ExpenseItem
from app.services.finance import fx_service
from app.services.ocr_service import ocr_service
from app.services.statement_service import statement_service

router = APIRouter()
MAX_UPLOAD_SIZE_BYTES = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10")) * 1024 * 1024
SPREADSHEET_SUFFIXES = (".csv", ".xls", ".xlsx")
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg")


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _render_status_card(
    title: str,
    message: str,
    style: str = "red",
    include_reset: bool = True,
) -> str:
    buttons = (
        '<br><button onclick="window.location.reload()" class="mt-4 px-4 py-2 bg-gray-600 text-white rounded '
        'hover:bg-gray-700 text-sm">Reset</button>'
        if include_reset
        else ""
    )
    return f"""
    <div class="p-8 text-center bg-{style}-50 rounded-lg border-2 border-{style}-500 border-dashed">
        <strong class="text-{style}-700">{_escape(title)}</strong> {_escape(message)}
        {buttons}
    </div>
    """


async def _read_limited_file(file: UploadFile) -> bytes:
    data = await file.read(MAX_UPLOAD_SIZE_BYTES + 1)
    if len(data) > MAX_UPLOAD_SIZE_BYTES:
        raise ValueError(f"File exceeds {MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)}MB limit.")
    return data


def _upsert_receipt_with_items(
    db: Session,
    user_email: str,
    vendor: str,
    parsed_date: DateType,
    amount: float,
    currency: str,
    base_currency_amount: float,
    fx_rate: float,
    extracted_data: dict,
) -> tuple[Expense, int, bool]:
    """
    Reconciliation strategy:
    1) If an exact receipt already exists, keep it.
    2) If a bank statement row exists (same user/date/vendor/amount/currency),
       upgrade it to receipt source and attach line items.
    3) Otherwise create a new receipt expense.
    Returns (expense, attached_items_count, was_existing_duplicate).
    """
    existing_receipt = (
        db.query(Expense)
        .filter(
            Expense.owner_email == user_email,
            Expense.date == parsed_date,
            Expense.amount == amount,
            Expense.currency == currency,
            Expense.vendor == vendor,
            Expense.source_type == "receipt",
        )
        .first()
    )
    if existing_receipt:
        return existing_receipt, 0, True

    expense = (
        db.query(Expense)
        .filter(
            Expense.owner_email == user_email,
            Expense.date == parsed_date,
            Expense.amount == amount,
            Expense.currency == currency,
            Expense.vendor == vendor,
        )
        .first()
    )

    if not expense:
        expense = Expense(
            owner_email=user_email,
            vendor=vendor,
            date=parsed_date,
            amount=amount,
            currency=currency,
            base_currency_amount=base_currency_amount,
            base_currency=settings.BASE_CURRENCY,
            fx_rate=fx_rate,
            category=extracted_data.get("category", "Uncategorized"),
            description=extracted_data.get("description", ""),
            source_type="receipt",
        )
        db.add(expense)
        db.flush()
    else:
        expense.source_type = "receipt"
        expense.category = extracted_data.get("category", expense.category)
        if extracted_data.get("description"):
            expense.description = extracted_data.get("description")
        expense.base_currency_amount = base_currency_amount
        expense.base_currency = settings.BASE_CURRENCY
        expense.fx_rate = fx_rate

    existing_item_keys = {
        (item.name, float(item.quantity), float(item.price))
        for item in expense.items
    }
    attached_items = 0
    for item in extracted_data.get("items", []):
        key = (
            item.get("name", "Unknown Item"),
            float(item.get("quantity", 1.0)),
            float(item.get("price", 0.0)),
        )
        if key in existing_item_keys:
            continue
        expense.items.append(
            ExpenseItem(
                name=key[0],
                quantity=key[1],
                price=key[2],
            )
        )
        existing_item_keys.add(key)
        attached_items += 1
    return expense, attached_items, False


@router.post("/upload", response_class=HTMLResponse)
async def upload_file(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    user_email = require_user_email(request)
    filename = (file.filename or "").lower().strip()
    if not filename:
        return _render_status_card("Error:", "Missing file name.")

    # --- ROUTE 1: SPREADSHEETS (CSV / EXCEL) ---
    if filename.endswith(SPREADSHEET_SUFFIXES):
        try:
            contents = await _read_limited_file(file)
        except ValueError as exc:
            return _render_status_card("Error:", str(exc))

        # Send to the Pandas / AI Mapper Service
        expenses_data = statement_service.process_file(contents, filename)

        # Handle Errors
        if not expenses_data or (isinstance(expenses_data, list) and "error" in expenses_data[0]):
            error_msg = expenses_data[0].get("error", "Failed to parse spreadsheet.") if expenses_data else "No data found."
            return _render_status_card("Error:", error_msg)

        db_expenses = []
        duplicates_skipped = 0
        seen_in_batch = set()

        for item in expenses_data:
            date_str = item.get("date", datetime.now().strftime("%Y-%m-%d"))
            try:
                parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                parsed_date = datetime.now().date()

            amount = float(item.get("amount", 0.0))
            currency = (item.get("currency") or settings.BASE_CURRENCY).upper()
            vendor = item.get("vendor", "Unknown")
            base_currency_amount, fx_rate = fx_service.convert_to_base(amount, currency, parsed_date)

            batch_key = (parsed_date, amount, currency, vendor)
            if batch_key in seen_in_batch:
                duplicates_skipped += 1
                continue
            seen_in_batch.add(batch_key)

            existing_expense = db.query(Expense).filter(
                Expense.owner_email == user_email,
                Expense.date == parsed_date,
                Expense.amount == amount,
                Expense.currency == currency,
                Expense.vendor == vendor,
            ).first()

            if existing_expense:
                duplicates_skipped += 1
                continue

            new_expense = Expense(
                owner_email=user_email,
                vendor=vendor,
                date=parsed_date,
                amount=amount,
                currency=currency,
                base_currency_amount=base_currency_amount,
                base_currency=settings.BASE_CURRENCY,
                fx_rate=fx_rate,
                category=item.get("category", "Uncategorized"),
                description=item.get("description", "Bank Statement Import"),
                source_type="statement",
            )
            db_expenses.append(new_expense)
        
        if db_expenses:
            db.add_all(db_expenses)
            db.commit()

        dup_msg = f"<br><span class='text-sm text-green-700 font-bold'>Skipped {duplicates_skipped} duplicates.</span>" if duplicates_skipped > 0 else ""

        return f"""
        <div class="p-12 text-center bg-green-50 rounded-lg border-2 border-green-500 border-dashed">
            <h3 class="text-lg font-medium text-green-800">Imported {len(db_expenses)} transactions!</h3>
            {dup_msg}
            <button onclick="window.location.reload()" class="mt-4 px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700">Refresh</button>
        </div>
        """

    # --- ROUTE 2: IMAGES (RECEIPTS) ---
    elif filename.endswith(IMAGE_SUFFIXES):
        try:
            image_bytes = await _read_limited_file(file)
        except ValueError as exc:
            return _render_status_card("Error:", str(exc))

        _, file_ext = os.path.splitext(filename)
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext, dir="/tmp") as temp_file:
            temp_file.write(image_bytes)
            temp_file_path = temp_file.name

        extracted_data = ocr_service.parse_receipt(temp_file_path)

        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

        if "error" in extracted_data:
            return _render_status_card("Extraction Error:", extracted_data["error"])

        date_str = extracted_data.get("date", datetime.now().strftime("%Y-%m-%d"))
        try:
            parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            parsed_date = datetime.now().date()

        amount = float(extracted_data.get("amount", 0.0))
        currency = (extracted_data.get("currency") or settings.BASE_CURRENCY).upper()
        vendor = extracted_data.get("vendor", "Unknown")
        base_currency_amount, fx_rate = fx_service.convert_to_base(amount, currency, parsed_date)

        expense, attached_items, is_duplicate = _upsert_receipt_with_items(
            db=db,
            user_email=user_email,
            vendor=vendor,
            parsed_date=parsed_date,
            amount=amount,
            currency=currency,
            base_currency_amount=base_currency_amount,
            fx_rate=fx_rate,
            extracted_data=extracted_data,
        )
        if is_duplicate:
            safe_vendor = _escape(vendor)
            return f"""
            <div class="p-8 text-center bg-yellow-50 rounded-lg border-2 border-yellow-500 border-dashed">
                <strong class="text-yellow-700">Duplicate:</strong> {safe_vendor} ({currency} {float(amount):.2f}) already exists.
                <br><button onclick="window.location.reload()" class="mt-4 px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700 text-sm">Reset</button>
            </div>
            """
        db.add(expense)
        db.commit()
        items_count = len(expense.items)

        return f"""
        <div class="p-12 text-center bg-green-50 rounded-lg border-2 border-green-500 border-dashed">
            <h3 class="text-lg font-medium text-green-800">Success: {_escape(expense.vendor)}</h3>
            <p class="text-sm text-green-700 mt-2">Extracted/attached {attached_items} new items ({items_count} total).</p>
            <button onclick="window.location.reload()" class="mt-4 px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700">Refresh</button>
        </div>
        """

    return _render_status_card(
        "Unsupported file format:",
        "Use PNG/JPG/JPEG or CSV/XLS/XLSX files.",
        style="yellow",
    )