import base64
import json
import os
from datetime import datetime
from openai import OpenAI
from app.core.config import settings

class OCRService:
    def __init__(self):
        self.ai_mode = os.getenv("AI_MODE", "cloud").lower()
        
        if self.ai_mode == "local":
            self.client = OpenAI(base_url="http://ollama:11434/v1", api_key="ollama")
            self.model = "llama3.2-vision"
        else:
            self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
            self.model = "gpt-4o"

    def encode_image(self, image_path: str) -> str:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def parse_receipt(self, file_path: str) -> dict:
        try:
            base64_image = self.encode_image(file_path)
        except Exception as e:
            return {"error": f"Could not read file: {e}"}

        current_year = datetime.now().year
        prompt = f"""
        You are a highly precise expense tracking data extraction assistant. Analyze this receipt image.
        Return a valid JSON object ONLY. Do not include markdown formatting or explanation text.

        Extraction and Normalization Rules:
        - vendor (string): Normalize merchant name (remove legal suffixes like GmbH).
        - date (string): YYYY-MM-DD format. Default year: {current_year}.
        - amount (float): Total final amount.
        - currency (string): ISO 3-letter code. Default: EUR.
        - category (string): Exactly one from [Groceries, Dining, Transport, Utilities, Shopping, Entertainment, Health, Travel, Home, Other].
        - description (string): Short 3-5 word summary.
        - items (array of objects): Extract all individual line items. Each object MUST contain 'name' (string), 'quantity' (float), and 'price' (float).
        """

        try:
            response = self.client.chat.completions.create(
                model=self.model, 
                response_format={ "type": "json_object" }, 
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                            }
                        ]
                    }
                ],
                max_tokens=1500,  # Increased capacity for itemization
                temperature=0.0
            )

            raw_content = response.choices[0].message.content.strip()
            
            # Remove markdown blocks if present
            if raw_content.startswith("```"):
                raw_content = raw_content.replace("```json", "").replace("```", "").strip()

            try:
                return json.loads(raw_content)
            except json.JSONDecodeError:
                # LOUD FAILURE for truncated JSON
                return {
                    "vendor": "Unknown",
                    "error": "The receipt was too long to process. The data was truncated by the LLM."
                }

        except Exception as e:
            print(f"OCR Error: {e}")
            return {
                "vendor": "Unknown",
                "amount": 0.0,
                "date": f"{datetime.now().strftime('%Y-%m-%d')}",
                "error": str(e)
            }

ocr_service = OCRService()