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
        - vendor (string): CRITICAL: Normalize the merchant name to its core brand. Remove all legal suffixes (e.g., GmbH, KG, AG, e.K., OHG, mbH). Fix casing to standard brand representation. Examples: "REWE Markt GmbH" -> "REWE", "Kissel Sbk" -> "Kissel", "ALDI SÜD" -> "Aldi".
        - date (string): Exact date in YYYY-MM-DD format. If the year is missing, assume it is {current_year}.
        - amount (float): Total final amount charged.
        - currency (string): ISO 3-letter currency code. Default to EUR.
        - category (string): Categorize the expense. You MUST choose exactly one from this exact list: [Groceries, Dining, Transport, Utilities, Shopping, Entertainment, Health, Travel, Home, Other].
        - description (string): A short 3-5 word summary of the main items purchased.
        - receipt_details (array): Extract every individual line item purchased on the receipt. Each item in the array must be an object with:
            - name (string): The name of the product or service.
            - quantity (float): The quantity purchased (default to 1.0 if not explicitly stated).
            - price (float): The total final price for this line item.
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
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000, 
                temperature=0.0
            )

            raw_content = response.choices[0].message.content.strip()
            
            if raw_content.startswith("```"):
                raw_content = raw_content.replace("```json", "").replace("```", "").strip()

            parsed_data = json.loads(raw_content)
            
            # Safety net to ensure the key always exists even if AI missed it
            if "receipt_details" not in parsed_data:
                parsed_data["receipt_details"] = []
                
            return parsed_data

        except Exception as e:
            print(f"OCR Error: {e}")
            return {
                "vendor": "Unknown",
                "amount": 0.0,
                "date": f"{datetime.now().strftime('%Y-%m-%d')}",
                "receipt_details": [],
                "error": str(e)
            }

ocr_service = OCRService()