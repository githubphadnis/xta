import os
import base64
import json
from fastapi import APIRouter, UploadFile, File
from fastapi.responses import HTMLResponse
from openai import OpenAI
from app.core.config import settings

router = APIRouter()
client = OpenAI(api_key=settings.OPENAI_API_KEY)

UPLOAD_DIR = "app/static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload")
async def handle_upload(file: UploadFile = File(...)):
    # 1. Save the image locally
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
        
    # 2. Encode image to Base64
    with open(file_path, "rb") as image_file:
        base64_image = base64.b64encode(image_file.read()).decode('utf-8')
        
    # 3. Call OpenAI Vision API - Now with Category logic!
    try:
        response = client.chat.completions.create(
            model="gpt-4o", 
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract the following details from this receipt: vendor name, total amount (as a number), date (YYYY-MM-DD), currency (e.g., EUR, USD), and a short, logical category based on the vendor and items (e.g., Groceries, Dining, Transport, Office Supplies, Utilities). Return ONLY a valid JSON object with keys: vendor, amount, date, currency, category. Do not use markdown blocks."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]
                }
            ],
            max_tokens=300
        )
        
        content = response.choices[0].message.content.strip()
        if content.startswith('```json'):
            content = content.replace('```json', '').replace('```', '').strip()
        data = json.loads(content)
        
    except Exception as e:
        print(f"OpenAI Error: {e}")
        data = {"vendor": "", "amount": 0.0, "date": "", "currency": "EUR", "category": "Uncategorized"}

    display_path = f"/static/uploads/{file.filename}"
    
    # 4. Generate the Review Form (Now includes the Category field)
    html_content = f"""
    <div class="bg-white p-6 rounded-lg border border-indigo-100 shadow-sm">
        <h3 class="text-lg font-medium text-gray-900 mb-4">Review Expense</h3>
        
        <form hx-post="/expenses/confirm" hx-swap="none">
            <input type="hidden" name="receipt_url" value="{display_path}">
            
            <div class="grid grid-cols-2 gap-4">
                <div class="col-span-2 sm:col-span-1">
                    <label class="block text-xs font-medium text-gray-500 uppercase">Vendor</label>
                    <input type="text" name="vendor" value="{data.get('vendor', '')}" required
                           class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border">
                </div>
                
                <div class="col-span-2 sm:col-span-1">
                    <label class="block text-xs font-medium text-gray-500 uppercase">Category</label>
                    <input type="text" name="category" value="{data.get('category', 'Uncategorized')}" required
                           class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border">
                </div>

                <div>
                    <label class="block text-xs font-medium text-gray-500 uppercase">Amount</label>
                    <input type="number" step="0.01" name="amount" value="{data.get('amount', '')}" required
                           class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border">
                </div>
                
                <div>
                    <label class="block text-xs font-medium text-gray-500 uppercase">Currency</label>
                    <input type="text" name="currency" value="{data.get('currency', 'EUR')}" required
                           class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border">
                </div>
                
                <div class="col-span-2">
                    <label class="block text-xs font-medium text-gray-500 uppercase">Date</label>
                    <input type="date" name="date" value="{data.get('date', '')}" required
                           class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border">
                </div>
            </div>

            <div class="mt-4 flex space-x-3">
                <button type="button" onclick="window.location.reload()" class="w-full inline-flex justify-center rounded-md border border-gray-300 bg-white py-2 px-4 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50">
                    Cancel
                </button>
                
                <button type="submit" 
                        onclick="setTimeout(() => window.location.reload(), 500)"
                        class="w-full inline-flex justify-center rounded-md border border-transparent bg-indigo-600 py-2 px-4 text-sm font-medium text-white shadow-sm hover:bg-indigo-700">
                    Confirm & Save
                </button>
            </div>
        </form>
    </div>
    """
    return HTMLResponse(content=html_content)