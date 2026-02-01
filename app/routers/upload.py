from fastapi import APIRouter, UploadFile, File, Depends, Request
from fastapi.responses import HTMLResponse # <--- IMPORT THIS
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.ingestion import ingestion_service

router = APIRouter()

@router.post("/upload", response_class=HTMLResponse) # <--- Add hint here
async def handle_upload(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Receives a file, saves it, and returns an HTMX-compatible HTML response.
    """
    # 1. Save the file
    file_path = await ingestion_service.save_upload(file)

    # 2. Return Success HTML
    # We wrap the string in HTMLResponse so FastAPI doesn't JSON-escape it
    html_content = f"""
    <div class="text-center p-6 bg-green-50 rounded-lg border border-green-200">
        <svg class="mx-auto h-12 w-12 text-green-500 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
        </svg>
        <h3 class="text-lg font-medium text-green-900">Upload Successful</h3>
        <p class="mt-1 text-sm text-green-600">File saved securely.</p>
        <p class="mt-1 text-xs text-gray-500 break-all">{file.filename}</p>
        
        <button onclick="window.location.reload()" class="mt-4 text-sm text-indigo-600 hover:text-indigo-800 underline">
            Upload another
        </button>
    </div>
    """
    
    return HTMLResponse(content=html_content)