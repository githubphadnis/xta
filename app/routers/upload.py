import os
import shutil
from fastapi import APIRouter, UploadFile, File, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.session import get_db
from app.models.expense import Expense
from app.services.ocr_service import ocr_service
from app.services.statement_service import statement_service

router = APIRouter()

@router.post("/upload", response_class=HTMLResponse)
async def upload_file(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    filename = file.filename.lower()
    
    # --- ROUTE 1: SPREADSHEETS (CSV / EXCEL) ---
    if filename.endswith(('.csv', '.xls', '.xlsx')):
        contents = await file.read()
        
        # Send to the Pandas / AI Mapper Service
        expenses_data = statement_service.process_file(contents, filename)
        
        # Handle Errors
        if not expenses_data or "error" in expenses_data[0]:
            error_msg = expenses_data[0].get("error", "Failed to parse spreadsheet.") if expenses_data else "No data found."
            return f"""
            <div class="p-8 text-center bg-red-50 rounded-lg border-2 border-red-500 border-dashed">
                <strong class="text-red-700">Error:</strong> {error_msg}
                <br><button onclick="window.location.reload()" class="mt-4 px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700 text-sm">Reset</button>
            </div>
            """
            
        # Bulk Insert into Database with Deduplication
        db_expenses = []
        duplicates_skipped = 0
        seen_in_batch = set() # Catches duplicates within the CSV itself
        
        for item in expenses_data:
            date_str = item.get("date", datetime.now().strftime("%Y-%m-%d"))
            try:
                parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                parsed_date = datetime.now().date()
                
            amount = item.get("amount", 0.0)
            vendor = item.get("vendor", "Unknown")
            
            # 1. Check if we already processed this exact row in the current CSV
            batch_key = (parsed_date, amount, vendor)
            if batch_key in seen_in_batch:
                duplicates_skipped += 1
                continue
            seen_in_batch.add(batch_key)

            # 2. Check if it already exists in the database
            existing_expense = db.query(Expense).filter(
                Expense.date == parsed_date,
                Expense.amount == amount,
                Expense.vendor == vendor
            ).first()

            if existing_expense:
                duplicates_skipped += 1
                continue
                
            new_expense = Expense(
                vendor=vendor,
                date=parsed_date,
                amount=amount,
                currency=item.get("currency", "EUR"),
                category=item.get("category", "Uncategorized"),
                description=item.get("description", "Bank Statement Import")
            )
            db_expenses.append(new_expense)
        
        if db_expenses:
            db.add_all(db_expenses)
            db.commit()
            
        dup_msg = f"<br><span class='text-sm text-green-700 font-bold'>Skipped {duplicates_skipped} duplicate entries.</span>" if duplicates_skipped > 0 else ""
        
        return f"""
        <div class="p-12 text-center bg-green-50 rounded-lg border-2 border-green-500 border-dashed">
            <h3 class="text-lg font-medium text-green-800">Successfully imported {len(db_expenses)} transactions!</h3>
            {dup_msg}
            <button onclick="window.location.reload()" class="mt-4 px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700">Refresh Dashboard</button>
        </div>
        """

    # --- ROUTE 2: IMAGES (RECEIPTS) ---
    elif filename.endswith(('.png', '.jpg', '.jpeg')):
        # Save temp file for the OCR service
        temp_file_path = f"/tmp/{file.filename}"
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Send to the OpenAI Vision Service
        extracted_data = ocr_service.parse_receipt(temp_file_path)
        
        # Clean up temp file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            
        if "error" in extracted_data and extracted_data["vendor"] == "Unknown":
            return f"""
            <div class="p-8 text-center bg-red-50 rounded-lg border-2 border-red-500 border-dashed">
                <strong class="text-red-700">OCR Error:</strong> {extracted_data['error']}
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

        # Duplicate Check for Single Receipt
        existing_expense = db.query(Expense).filter(
            Expense.date == parsed_date,
            Expense.amount == amount,
            Expense.vendor == vendor
        ).first()

        if existing_expense:
            return f"""
            <div class="p-8 text-center bg-yellow-50 rounded-lg border-2 border-yellow-500 border-dashed">
                <strong class="text-yellow-700">Duplicate Detected:</strong> This receipt ({vendor} for €{amount}) has already been scanned on {parsed_date}.
                <br><button onclick="window.location.reload()" class="mt-4 px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700 text-sm">Reset</button>
            </div>
            """

        # Insert Single Receipt into Database
        new_expense = Expense(
            vendor=vendor,
            date=parsed_date,
            amount=amount,
            currency=extracted_data.get("currency", "EUR"),
            category=extracted_data.get("category", "Uncategorized"),
            description=extracted_data.get("description", "")
        )
        db.add(new_expense)
        db.commit()
        
        return f"""
        <div class="p-12 text-center bg-green-50 rounded-lg border-2 border-green-500 border-dashed">
            <h3 class="text-lg font-medium text-green-800">Receipt processed: {new_expense.vendor} (€{new_expense.amount})</h3>
            <button onclick="window.location.reload()" class="mt-4 px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700">Refresh Dashboard</button>
        </div>
        """
        
    else:
        return """
        <div class="p-8 text-center bg-yellow-50 rounded-lg border-2 border-yellow-500 border-dashed">
            <strong class="text-yellow-700">Unsupported File:</strong> Please upload an image or spreadsheet.
            <br><button onclick="window.location.reload()" class="mt-4 px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700 text-sm">Reset</button>
        </div>
        """