"""
core/engine.py

Orchestrates the full pipeline for checking invoices against contracts:

  1. Parse all contracts and amendments once (cached for the whole batch).
  2. For each invoice: extract -> match to contract -> apply amendments
     -> run deterministic rules -> run one LLM "judgment" pass for fuzzy
     issues -> assemble a report entry.

This is the file app.py (the Streamlit UI) calls into. Keeping this
separate from the UI means the same engine could power a command-line
tool, an API, or a different UI later without changes.
"""

from core.extract import extract_text
from core.parse import parse_contract, parse_amendment, parse_invoice
from core.match import find_best_contract, find_relevant_amendments, apply_amendments
from core.llm import extract_json
from rules.registry import get_active_rules


def load_contracts(file_paths: list) -> list:
    """Parse a list of contract file paths into structured data (once, upfront)."""
    contracts = []
    for path in file_paths:
        text = extract_text(path)
        data = parse_contract(text)
        contracts.append({"path": path, "text": text, "data": data})
    return contracts


def load_amendments(file_paths: list) -> list:
    amendments = []
    for path in file_paths:
        text = extract_text(path)
        data = parse_amendment(text)
        amendments.append({"path": path, "text": text, "data": data})
    return amendments


JUDGMENT_PROMPT = """
You are a financial controller's assistant. Compare this invoice against
the effective contract terms below and flag any issues that a purely
mechanical check might miss -- e.g. scope creep (invoice bills for work
outside the contracted scope), ambiguous or inconsistent descriptions,
or anything else that looks off. Do NOT repeat simple math errors or
rate overages -- those are already checked separately.

If you find nothing noteworthy, return an empty list.

Return ONLY valid JSON in this shape:
{{
  "issues": [
    {{"severity": "low" | "medium" | "high", "message": "plain English description"}}
  ]
}}

CONTRACT (effective terms, after any amendments):
{contract_json}

INVOICE:
{invoice_json}
"""


def run_llm_judgment(invoice_data: dict, contract_data: dict) -> list:
    import json
    prompt = JUDGMENT_PROMPT.format(
        contract_json=json.dumps(contract_data, default=str),
        invoice_json=json.dumps(invoice_data, default=str),
    )
    result = extract_json(prompt)
    return result.get("issues", [])


def process_invoice(invoice_path: str, contracts: list, amendments: list) -> dict:
    """
    Returns a report entry:
    {
      "invoice_path": ...,
      "invoice_data": {...},
      "matched_contract": path or None,
      "status": "Clean" | "Flagged" | "No Matching Contract Found",
      "issues": [ {"rule": ..., "severity": ..., "message": ...}, ... ]
    }
    """
    invoice_text = extract_text(invoice_path)
    invoice_data = parse_invoice(invoice_text)

    match = find_best_contract(invoice_data, contracts)
    if match is None:
        return {
            "invoice_path": invoice_path,
            "invoice_data": invoice_data,
            "matched_contract": None,
            "status": "No Matching Contract Found",
            "issues": [],
        }

    relevant_amendments = find_relevant_amendments(match, amendments)
    effective_contract = apply_amendments(match["data"], relevant_amendments)

    all_issues = []

    # Deterministic rules first -- fast, reliable, no AI risk.
    for rule in get_active_rules():
        for issue in rule.check(invoice_data, effective_contract):
            all_issues.append({
                "rule": issue.rule_name,
                "severity": issue.severity,
                "message": issue.message,
            })

    # LLM judgment pass for fuzzier issues the rules can't catch.
    try:
        for issue in run_llm_judgment(invoice_data, effective_contract):
            all_issues.append({
                "rule": "llm_judgment",
                "severity": issue.get("severity", "low"),
                "message": issue.get("message", ""),
            })
    except Exception as e:
        all_issues.append({
            "rule": "llm_judgment",
            "severity": "low",
            "message": f"(LLM judgment pass failed to run: {e})",
        })

    return {
        "invoice_path": invoice_path,
        "invoice_data": invoice_data,
        "matched_contract": match["path"],
        "amendments_applied": effective_contract.get("_amendments_applied", []),
        "status": "Flagged" if all_issues else "Clean",
        "issues": all_issues,
    }
