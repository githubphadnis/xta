import os
import shutil
from datetime import datetime
from fastapi import UploadFile, HTTPException

class IngestionService:
    # We will save files to a folder named 'uploads' in the root
    UPLOAD_DIR = "uploads"

    def __init__(self):
        # Ensure upload directory exists
        if not os.path.exists(self.UPLOAD_DIR):
            os.makedirs(self.UPLOAD_DIR)

    async def save_upload(self, file: UploadFile) -> str:
        """
        Saves the uploaded file to disk with a timestamped name.
        Returns the absolute file path.
        """
        # 1. Basic Security: Validate file type
        allowed_types = [
            "image/jpeg", 
            "image/png", 
            "application/pdf", 
            "text/csv", 
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ]
        
        if file.content_type not in allowed_types:
            # Fallback: Check extension if content-type is generic
            ext = os.path.splitext(file.filename)[1].lower()
            if ext not in ['.jpg', '.jpeg', '.png', '.pdf', '.csv', '.xls', '.xlsx']:
                raise HTTPException(status_code=400, detail=f"File type {file.content_type} not allowed")

        # 2. Generate secure filename (YYYYMMDD_HHMMSS_OriginalName)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Sanitize filename (simple version)
        safe_filename = os.path.basename(file.filename).replace(" ", "_")
        new_filename = f"{timestamp}_{safe_filename}"
        
        file_path = os.path.join(self.UPLOAD_DIR, new_filename)

        # 3. Save to disk efficiently
        try:
            with open(file_path, "wb") as buffer:
                # copying in chunks is better for RAM
                shutil.copyfileobj(file.file, buffer)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Could not save file: {str(e)}")

        return file_path

# Export a singleton instance
ingestion_service = IngestionService()