import base64
import json
import os
from datetime import datetime
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

        # Dynamically inject the current year into the prompt
        current_year = datetime.now().year

        # 2. Define the Prompt (Strict instructions for Entity Normalization)
        prompt = f"""
        You are a highly precise expense tracking data extraction assistant. Analyze this receipt image.
        Return a valid JSON object ONLY.

        Extraction and Normalization Rules:
        - vendor (string): CRITICAL: Normalize the merchant name to its core brand. Remove all legal suffixes (e.g., GmbH, KG, AG, e.K., OHG, mbH). Fix casing to standard brand representation. Examples: "REWE Markt GmbH" -> "REWE", "Kissel Sbk" -> "Kissel", "ALDI SÜD" -> "Aldi".
        - date (string): Exact date in YYYY-MM-DD format. If the year is missing, assume it is {current_year}.
        - amount (float): Total final amount charged.
        - currency (string): ISO 3-letter currency code. Default to EUR.
        - category (string): Categorize the expense. You MUST choose exactly one from this exact list: [Groceries, Dining, Transport, Utilities, Shopping, Entertainment, Health, Travel, Home, Other].
        - description (string): A short 3-5 word summary of the main items purchased.
        """

        # 3. Call OpenAI
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o", 
                response_format={ "type": "json_object" }, # Forces strict JSON architecture
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
                temperature=0.0 # Dropped to 0.0 for absolute deterministic data extraction
            )

            # 4. Extract and Clean Response
            raw_content = response.choices[0].message.content.strip()
            return json.loads(raw_content)

        except Exception as e:
            print(f"OCR Error: {e}")
            # Return a dummy object so the app doesn't crash on failure
            return {
                "vendor": "Unknown",
                "amount": 0.0,
                "date": f"{datetime.now().strftime('%Y-%m-%d')}",
                "error": str(e)
            }

ocr_service = OCRService()