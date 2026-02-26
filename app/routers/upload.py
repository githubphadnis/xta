import os
import shutil
from fastapi import APIRouter, UploadFile, File, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.session import get_db
from app.models.expense import Expense, ExpenseItem
from app.services.ocr_service import ocr_service
from app.services.statement_service import statement_service

router = APIRouter()

@router.post("/upload", response_class=HTMLResponse)
async def upload_file(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    filename = file.filename.lower()
    
    # --- ROUTE 1: SPREADSHEETS (Omitted for brevity, keep your existing CSV logic) ---
    if filename.endswith(('.csv', '.xls', '.xlsx')):
        # ... (Keep your current spreadsheet code here) ...
        pass

    # --- ROUTE 2: IMAGES (RECEIPTS) ---
    elif filename.endswith(('.png', '.jpg', '.jpeg')):
        temp_file_path = f"/tmp/{file.filename}"
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        extracted_data = ocr_service.parse_receipt(temp_file_path)
        
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            
        # LOUD FAILURE CHECK: Catch truncation or extraction errors
        if "error" in extracted_data:
            return f"""
            <div class="p-8 text-center bg-red-50 rounded-lg border-2 border-red-500 border-dashed">
                <strong class="text-red-700">Extraction Error:</strong> {extracted_data['error']}
                <br><button onclick="window.location.reload()" class="mt-4 px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700 text-sm">Reset</button>
            </div>
            """

        date_str = extracted_data.get("date", datetime.now().strftime("%Y-%m-%d"))
        try:
            parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            parsed_date = datetime.now().date()
            
        amount = extracted_data.get("amount", 0.0)
        vendor = extracted_data.get("vendor", "Unknown")

        existing_expense = db.query(Expense).filter(
            Expense.date == parsed_date,
            Expense.amount == amount,
            Expense.vendor == vendor
        ).first()

        if existing_expense:
            return f"""
            <div class="p-8 text-center bg-yellow-50 rounded-lg border-2 border-yellow-500 border-dashed">
                <strong class="text-yellow-700">Duplicate Detected:</strong> This receipt already exists.
                <br><button onclick="window.location.reload()" class="mt-4 px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700 text-sm">Reset</button>
            </div>
            """

        new_expense = Expense(
            vendor=vendor,
            date=parsed_date,
            amount=amount,
            currency=extracted_data.get("currency", "EUR"),
            category=extracted_data.get("category", "Uncategorized"),
            description=extracted_data.get("description", "")
        )
        
        items_list = extracted_data.get("items", [])
        for item in items_list:
            db_item = ExpenseItem(
                name=item.get("name", "Unknown Item") if isinstance(item, dict) else item.name,
                quantity=item.get("quantity", 1.0) if isinstance(item, dict) else item.quantity,
                price=item.get("price", 0.0) if isinstance(item, dict) else item.price
            )
            new_expense.items.append(db_item)

        db.add(new_expense)
        db.commit()
        
        return f"""
        <div class="p-12 text-center bg-green-50 rounded-lg border-2 border-green-500 border-dashed">
            <h3 class="text-lg font-medium text-green-800">Success: {new_expense.vendor}</h3>
            <p class="text-sm text-green-700 mt-2">Extracted {len(items_list)} items.</p>
            <button onclick="window.location.reload()" class="mt-4 px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700">Refresh Dashboard</button>
        </div>
        """
    
    return "Unsupported file format."