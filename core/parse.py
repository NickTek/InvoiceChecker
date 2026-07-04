"""
core/parse.py

Turns raw extracted text (from extract.py) into structured data
(vendor name, rates, line items, dates, etc.) using the LLM.

This is the "extraction" step of the pipeline. Keeping the schema
consistent here is what lets matching and comparison logic
(match.py, rules/) work reliably downstream.
"""

from core.llm import extract_json


CONTRACT_SCHEMA_PROMPT = """
You are reading a vendor contract. Extract the following fields as JSON.
If a field is not present, use null.

Return ONLY valid JSON in this exact shape:
{{
  "vendor_name": string or null,
  "contract_id": string or null,
  "buyer_country": string or null,
  "vendor_country": string or null,
  "rate_amount": number or null,
  "rate_unit": string or null,           // e.g. "per month", "per hour", "per unit"
  "currency": string or null,
  "payment_terms": string or null,
  "scope_summary": string or null,       // 1-2 sentence summary of what is contracted
  "start_date": string or null,          // YYYY-MM-DD if determinable
  "end_date": string or null,            // YYYY-MM-DD if determinable
  "tax_treatment": string or null        // any statement about VAT/GST/tax if present
}}

Contract text:
---
{text}
---
"""

AMENDMENT_SCHEMA_PROMPT = """
You are reading a contract amendment / change order. Extract the following
fields as JSON. If a field is not present, use null.

Return ONLY valid JSON in this exact shape:
{{
  "vendor_name": string or null,
  "contract_id_referenced": string or null,
  "amendment_date": string or null,       // YYYY-MM-DD if determinable
  "changed_fields": {{
      "rate_amount": number or null,
      "rate_unit": string or null,
      "end_date": string or null,
      "scope_summary": string or null
  }},
  "amendment_summary": string or null      // 1-2 sentence plain-English summary of what changed
}}

Amendment text:
---
{text}
---
"""

INVOICE_SCHEMA_PROMPT = """
You are reading a vendor invoice. Extract the following fields as JSON.
If a field is not present, use null.

Return ONLY valid JSON in this exact shape:
{{
  "vendor_name": string or null,
  "contract_id_referenced": string or null,
  "invoice_number": string or null,
  "invoice_date": string or null,        // YYYY-MM-DD if determinable
  "currency": string or null,
  "line_items": [
    {{"description": string, "quantity": number or null, "unit_price": number or null, "amount": number}}
  ],
  "subtotal": number or null,
  "tax_amount": number or null,
  "total": number or null,
  "vendor_country": string or null,
  "buyer_country": string or null
}}

Invoice text:
---
{text}
---
"""


def parse_contract(text: str) -> dict:
    return extract_json(CONTRACT_SCHEMA_PROMPT.format(text=text[:8000]))


def parse_amendment(text: str) -> dict:
    return extract_json(AMENDMENT_SCHEMA_PROMPT.format(text=text[:8000]))


def parse_invoice(text: str) -> dict:
    return extract_json(INVOICE_SCHEMA_PROMPT.format(text=text[:8000]))
