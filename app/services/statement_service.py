import pandas as pd
import json
import io
import math
import os
from openai import OpenAI
from app.core.config import settings
from datetime import datetime

class StatementService:
    def __init__(self):
        self.ai_mode = os.getenv("AI_MODE", "cloud").lower()
        
        if self.ai_mode == "local":
            self.client = OpenAI(base_url="http://ollama:11434/v1", api_key="ollama")
            self.model = "llama3.2"
        else:
            self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
            self.model = "gpt-4o-mini"

    def _clean_json_response(self, raw_content: str) -> dict:
        raw_content = raw_content.strip()
        if raw_content.startswith("```"):
            raw_content = raw_content.replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(raw_content)
        except json.JSONDecodeError as e:
            print(f"JSON Decode Error: {e} - Raw Content: {raw_content}")
            return {}

    def process_file(self, file_contents: bytes, filename: str) -> list:
        try:
            if filename.lower().endswith('.csv'):
                df = pd.read_csv(io.BytesIO(file_contents), sep=None, engine='python', encoding_errors='replace')
            elif filename.lower().endswith(('.xls', '.xlsx')):
                df = pd.read_excel(io.BytesIO(file_contents))
            else:
                return [{"error": "Unsupported file format."}]
        except Exception as e:
            return [{"error": f"Could not read spreadsheet: {e}"}]

        df.dropna(how='all', inplace=True)
        df.dropna(axis=1, how='all', inplace=True)

        sample_csv = df.head(5).to_csv(index=False)
        col_prompt = f"""
        Identify the exact column headers for date, vendor/payee, and amount from this sample.
        Return ONLY JSON. Rules:
        - date_column: Exact header for transaction date.
        - vendor_column: Exact header for merchant/payee.
        - amount_column: Exact header for transaction amount.
        Sample:
        {sample_csv}
        """

        try:
            col_response = self.client.chat.completions.create(
                model=self.model,
                response_format={ "type": "json_object" },
                messages=[{"role": "user", "content": col_prompt}],
                temperature=0.0
            )
            mapping = self._clean_json_response(col_response.choices[0].message.content)
            
            date_col = mapping.get('date_column')
            vendor_col = mapping.get('vendor_column')
            amount_col = mapping.get('amount_column')

            if not all([date_col in df.columns, vendor_col in df.columns, amount_col in df.columns]):
                return [{"error": "AI could not accurately map the spreadsheet columns."}]
        except Exception as e:
            return [{"error": f"Column mapping failed: {e}"}]

        unique_vendors = [v for v in df[vendor_col].dropna().unique().tolist() if str(v).strip()]
        
        vendor_prompt = f"""
        Normalize these merchant names (remove legal suffixes like GmbH, Sbk, store numbers) and assign a category.
        You MUST use exactly one of these categories: [Groceries, Dining, Transport, Utilities, Shopping, Entertainment, Health, Travel, Home, Other].
        Return ONLY a JSON dictionary where the key is the exact raw vendor name, and the value is an object with 'vendor' and 'category'.
        Raw vendors to process: {unique_vendors}
        """

        try:
            vendor_response = self.client.chat.completions.create(
                model=self.model,
                response_format={ "type": "json_object" },
                messages=[{"role": "user", "content": vendor_prompt}],
                temperature=0.0
            )
            vendor_map = self._clean_json_response(vendor_response.choices[0].message.content)
        except Exception as e:
            print(f"Vendor mapping failed, falling back to raw data: {e}")
            vendor_map = {}

        expenses = []
        for index, row in df.iterrows():
            try:
                raw_amount = str(row[amount_col]).strip()
                if raw_amount.lower() in ['nan', 'none', '']:
                    continue
                
                if ',' in raw_amount and '.' in raw_amount:
                    if raw_amount.rfind(',') > raw_amount.rfind('.'):
                        raw_amount = raw_amount.replace('.', '').replace(',', '.') 
                    else:
                        raw_amount = raw_amount.replace(',', '') 
                elif ',' in raw_amount and len(raw_amount.split(',')[-1]) <= 2:
                    raw_amount = raw_amount.replace(',', '.') 
                
                amount = float(raw_amount)
                
                if amount >= 0:
                    continue 

                raw_vendor_name = str(row[vendor_col]).strip()
                mapped_data = vendor_map.get(raw_vendor_name, {})
                
                expense = {
                    "vendor": mapped_data.get("vendor", raw_vendor_name),
                    "date": pd.to_datetime(row[date_col], dayfirst=True, errors='coerce').strftime('%Y-%m-%d'),
                    "amount": abs(amount),
                    "currency": "EUR", 
                    "category": mapped_data.get("category", "Uncategorized")
                }
                expenses.append(expense)
            except Exception as e:
                continue 

        return expenses

statement_service = StatementService()