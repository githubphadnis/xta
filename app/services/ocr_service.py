import base64
import json
import os
from openai import OpenAI
from app.core.config import settings

class OCRService:
    def __init__(self):
        # Initialize OpenAI client using the key from .env
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def encode_image(self, image_path: str) -> str:
        """Helper to convert image to base64 for the API"""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def parse_receipt(self, file_path: str) -> dict:
        """
        Sends the image to OpenAI and returns structured JSON.
        """
        # 1. Prepare the image
        try:
            base64_image = self.encode_image(file_path)
        except Exception as e:
            return {"error": f"Could not read file: {e}"}

        # 2. Define the Prompt (Strict JSON output)
        prompt = """
        You are an expense tracking assistant. Analyze this receipt image.
        Extract the following fields and return them as a valid JSON object ONLY. 
        Do not wrap in markdown code blocks.
        
        Fields required:
        - vendor (string): Name of the merchant
        - date (string): Date in YYYY-MM-DD format. If year is missing, assume current year.
        - amount (float): Total amount.
        - currency (string): ISO 3-letter currency code (e.g. EUR, USD). Default to EUR if symbol is €.
        - category (string): Guess a category (e.g. Food, Transport, Utilities, Groceries).
        - description (string): A short 3-5 word summary.
        """

        # 3. Call OpenAI
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o", 
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=300,
                temperature=0.1 # Low temperature = more factual
            )

            # 4. Extract and Clean Response
            raw_content = response.choices[0].message.content.strip()
            
            # Remove markdown formatting if OpenAI adds it
            if raw_content.startswith("```"):
                raw_content = raw_content.replace("```json", "").replace("```", "")
            
            return json.loads(raw_content)

        except Exception as e:
            print(f"OCR Error: {e}")
            # Return a dummy object so the app doesn't crash on failure
            return {
                "vendor": "Unknown",
                "amount": 0.0,
                "date": "2025-01-01",
                "error": str(e)
            }

ocr_service = OCRService()