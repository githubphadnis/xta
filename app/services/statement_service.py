import pandas as pd
import json
import io
from openai import OpenAI
from app.core.config import settings
from datetime import datetime

class StatementService:
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def process_file(self, file_contents: bytes, filename: str) -> list:
        # 1. Load the file into a Pandas DataFrame
        try:
            if filename.lower().endswith('.csv'):
                # European bank CSVs often use ';' and varying encodings
                df = pd.read_csv(io.BytesIO(file_contents), sep=None, engine='python', encoding_errors='replace')
            elif filename.lower().endswith(('.xls', '.xlsx')):
                df = pd.read_excel(io.BytesIO(file_contents))
            else:
                return [{"error": "Unsupported file format."}]
        except Exception as e:
            return [{"error": f"Could not read spreadsheet: {e}"}]

        # Clean up the dataframe (drop totally empty rows/cols)
        df.dropna(how='all', inplace=True)
        df.dropna(axis=1, how='all', inplace=True)

        # 2. Extract a sample and ask AI to map the columns
        sample_csv = df.head(5).to_csv(index=False)
        
        prompt = f"""
        You are a financial data mapper. Analyze this bank statement sample.
        Identify the exact column headers that correspond to the date, vendor/payee, and amount.
        Return ONLY a JSON object. Do not wrap in markdown.
        
        Rules:
        - date_column: The exact header name for the transaction date.
        - vendor_column: The exact header name for the merchant/payee or description.
        - amount_column: The exact header name for the transaction amount.

        Sample Data:
        {sample_csv}
        """

        try:
            # We use the much cheaper/faster 4o-mini for this simple text task
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                response_format={ "type": "json_object" },
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0
            )
            mapping = json.loads(response.choices[0].message.content.strip())
            
            date_col = mapping.get('date_column')
            vendor_col = mapping.get('vendor_column')
            amount_col = mapping.get('amount_column')

            # Verify the AI didn't hallucinate column names
            if not all([date_col in df.columns, vendor_col in df.columns, amount_col in df.columns]):
                return [{"error": "AI could not accurately map the spreadsheet columns."}]

        except Exception as e:
            return [{"error": f"AI mapping failed: {e}"}]

        # 3. Process the DataFrame using the AI's map
        expenses = []
        for index, row in df.iterrows():
            try:
                # Basic string cleaning and European number formatting (e.g., "1.200,50" -> "1200.50")
                raw_amount = str(row[amount_col]).replace('.', '').replace(',', '.')
                amount = float(raw_amount)
                
                # We usually only want to track negative amounts (money spent)
                if amount >= 0:
                    continue 

                expense = {
                    "vendor": str(row[vendor_col]).strip(),
                    "date": pd.to_datetime(row[date_col], dayfirst=True, errors='coerce').strftime('%Y-%m-%d'),
                    "amount": abs(amount), # Store as positive absolute value
                    "currency": "EUR", # Defaulting to EUR for bank statements
                    "category": "Uncategorized" # You can bulk-edit these in the UI later
                }
                expenses.append(expense)
            except Exception as e:
                continue # Skip weird formatting rows (like footer totals)

        return expenses

statement_service = StatementService()