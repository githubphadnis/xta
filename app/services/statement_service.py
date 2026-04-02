import json
import io
import os
from datetime import datetime

import pandas as pd
from openai import OpenAI
from app.core.config import settings

class StatementService:
    def __init__(self):
        self.ai_mode = os.getenv("AI_MODE", "cloud").lower()
        
        if self.ai_mode == "local":
            self.client = OpenAI(base_url="http://ollama:11434/v1", api_key="ollama")
            self.model = "llama3.2"
        else:
            self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
            self.model = "gpt-4o-mini"

    @staticmethod
    def _normalize_date(raw_date: object) -> str:
        """
        Normalize assorted spreadsheet date formats to YYYY-MM-DD.
        Priority:
        1) Strict ISO (YYYY-MM-DD) if already present.
        2) General parser with dayfirst fallback.
        3) Today if parsing fails.
        """
        text = str(raw_date).strip()
        if not text or text.lower() in {"nan", "none"}:
            return datetime.now().strftime("%Y-%m-%d")

        try:
            return datetime.strptime(text, "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            pass

        # Dot/slash separated formats are typically day-first in EU exports.
        dayfirst_hint = any(sep in text for sep in (".", "/"))
        parsed = pd.to_datetime(text, dayfirst=dayfirst_hint, errors="coerce")
        if pd.notna(parsed):
            return parsed.strftime("%Y-%m-%d")

        parsed_dayfirst = pd.to_datetime(text, dayfirst=True, errors="coerce")
        if pd.notna(parsed_dayfirst):
            return parsed_dayfirst.strftime("%Y-%m-%d")

        return datetime.now().strftime("%Y-%m-%d")

    def _clean_json_response(self, raw_content: str) -> dict:
        raw_content = raw_content.strip()
        if raw_content.startswith("```"):
            raw_content = raw_content.replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(raw_content)
        except json.JSONDecodeError as e:
            print(f"JSON Decode Error: {e} - Raw Content: {raw_content}")
            return {}

    @staticmethod
    def _result_payload(
        rows: list[dict],
        *,
        source: str,
        total_rows: int,
        skipped_rows: int,
        fallback_used: bool,
        confidence: str,
        error: str | None = None,
    ) -> dict:
        meta = {
            "source": source,
            "total_rows": total_rows,
            "parsed_rows": len(rows),
            "skipped_rows": skipped_rows,
            "fallback_used": fallback_used,
            "confidence": confidence,
        }
        return {
            "rows": rows,
            "expenses": rows,  # Backward-compatible alias for existing callers.
            "error": error,
            "errors": [error] if error else [],
            "meta": meta,
            "parser_mode": source,
            "skipped_rows": skipped_rows,
        }

    def process_file(self, file_contents: bytes, filename: str) -> dict:
        try:
            if filename.lower().endswith('.csv'):
                df = pd.read_csv(io.BytesIO(file_contents), sep=None, engine='python', encoding_errors='replace')
            elif filename.lower().endswith(('.xls', '.xlsx')):
                df = pd.read_excel(io.BytesIO(file_contents))
            else:
                return self._result_payload(
                    rows=[],
                    source="unsupported",
                    total_rows=0,
                    skipped_rows=0,
                    fallback_used=False,
                    confidence="low",
                    error="Unsupported file format.",
                )
        except Exception as e:
            return self._result_payload(
                rows=[],
                source="read_error",
                total_rows=0,
                skipped_rows=0,
                fallback_used=False,
                confidence="low",
                error=f"Could not read spreadsheet: {e}",
            )

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
                fallback_rows = self.parse_fallback_unstructured(file_contents, filename)
                total_rows = int(len(df.index))
                parsed_rows = len(fallback_rows)
                return self._result_payload(
                    rows=fallback_rows,
                    source="fallback_unstructured",
                    total_rows=total_rows,
                    skipped_rows=max(total_rows - parsed_rows, 0),
                    fallback_used=True,
                    confidence="low",
                    error="AI could not accurately map the spreadsheet columns. Used unstructured fallback.",
                )
        except Exception as e:
            fallback_rows = self.parse_fallback_unstructured(file_contents, filename)
            total_rows = int(len(df.index))
            parsed_rows = len(fallback_rows)
            return self._result_payload(
                rows=fallback_rows,
                source="fallback_unstructured",
                total_rows=total_rows,
                skipped_rows=max(total_rows - parsed_rows, 0),
                fallback_used=True,
                confidence="low",
                error=f"Column mapping failed: {e}. Used unstructured fallback.",
            )

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
        total_rows = int(len(df.index))
        skipped_rows = 0
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
                    skipped_rows += 1
                    continue 

                raw_vendor_name = str(row[vendor_col]).strip()
                mapped_data = vendor_map.get(raw_vendor_name, {})
                
                expense = {
                    "vendor": mapped_data.get("vendor", raw_vendor_name),
                    "date": self._normalize_date(row[date_col]),
                    "amount": abs(amount),
                    "currency": "EUR", 
                    "category": mapped_data.get("category", "Uncategorized")
                }
                expenses.append(expense)
            except Exception:
                skipped_rows += 1
                continue 
        parsed_rows = len(expenses)
        confidence = "high" if parsed_rows > 0 and parsed_rows >= max(total_rows // 2, 1) else "medium"
        return self._result_payload(
            rows=expenses,
            source="mapped",
            total_rows=total_rows,
            skipped_rows=skipped_rows,
            fallback_used=False,
            confidence=confidence,
            error=None,
        )

    @staticmethod
    def parse_fallback_unstructured(file_contents: bytes, filename: str) -> list:
        """
        Best-effort fallback parser for unstructured sheets:
        - extracts numeric values
        - creates pseudo transactions with generic metadata
        """
        try:
            if filename.lower().endswith(".csv"):
                df = pd.read_csv(io.BytesIO(file_contents), header=None, dtype=str, encoding_errors="replace")
            else:
                df = pd.read_excel(io.BytesIO(file_contents), header=None, dtype=str)
        except Exception:
            return []

        expenses: list[dict] = []
        for _, row in df.iterrows():
            cells = [str(value).strip() for value in row.tolist() if str(value).strip() not in {"", "nan", "None"}]
            if not cells:
                continue
            amount = None
            for value in cells:
                normalized = value.replace(",", ".").replace(" ", "")
                try:
                    parsed = float(normalized)
                except ValueError:
                    continue
                if parsed < 0:
                    amount = abs(parsed)
                    break
                if parsed > 0 and amount is None:
                    amount = parsed
            if amount is None:
                continue

            vendor = next((c for c in cells if any(ch.isalpha() for ch in c)), "Unstructured Import")
            expenses.append(
                {
                    "vendor": vendor[:120],
                    "date": pd.Timestamp.now().strftime("%Y-%m-%d"),
                    "amount": float(amount),
                    "currency": "EUR",
                    "category": "Uncategorized",
                    "description": "Unstructured statement fallback",
                }
            )
            if len(expenses) >= 500:
                break
        return expenses

statement_service = StatementService()