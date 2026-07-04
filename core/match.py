"""
core/match.py

Given one invoice's structured data, finds the best-matching contract
out of a folder of many, and applies the latest relevant amendment on top
of it (so comparisons happen against the CURRENT effective terms, not the
original contract if it has since been amended).

Matching strategy (in priority order):
  1. Exact contract_id match (invoice references a contract/PO number that
     exactly matches a contract's contract_id).
  2. Fuzzy vendor name match (handles "Acme Inc." vs "ACME INCORPORATED").

This is a lightweight, dependency-free stand-in for a full vector-search
/ RAG system. It is deliberately simple so it is easy to understand,
debug, and extend -- swap in a proper vector database later if you need
to match against thousands of contracts instead of hundreds.
"""

from difflib import SequenceMatcher


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.strip().lower(), b.strip().lower()).ratio()


def find_best_contract(invoice_data: dict, contracts: list) -> dict:
    """
    contracts: list of dicts like {"path": ..., "data": <parsed contract dict>}
    Returns the best-matching contract dict, or None if nothing matches well.
    """
    invoice_contract_id = (invoice_data.get("contract_id_referenced") or "").strip()
    invoice_vendor = invoice_data.get("vendor_name") or ""

    # 1. Try exact contract ID match first -- most reliable signal.
    if invoice_contract_id:
        for c in contracts:
            contract_id = (c["data"].get("contract_id") or "").strip()
            if contract_id and contract_id.lower() == invoice_contract_id.lower():
                return c

    # 2. Fall back to fuzzy vendor name matching.
    best_match = None
    best_score = 0.0
    for c in contracts:
        score = _similarity(invoice_vendor, c["data"].get("vendor_name") or "")
        if score > best_score:
            best_score = score
            best_match = c

    # Require a reasonably high similarity before trusting the match.
    if best_match and best_score >= 0.6:
        return best_match

    return None


def find_relevant_amendments(contract: dict, amendments: list) -> list:
    """
    Returns amendments that reference this specific contract, sorted
    oldest -> newest, so they can be applied in order.
    """
    contract_id = (contract["data"].get("contract_id") or "").strip().lower()
    contract_vendor = (contract["data"].get("vendor_name") or "").strip().lower()

    relevant = []
    for a in amendments:
        ref_id = (a["data"].get("contract_id_referenced") or "").strip().lower()
        ref_vendor = (a["data"].get("vendor_name") or "").strip().lower()
        if (contract_id and ref_id == contract_id) or (
            contract_vendor and _similarity(contract_vendor, ref_vendor) >= 0.7
        ):
            relevant.append(a)

    relevant.sort(key=lambda a: a["data"].get("amendment_date") or "")
    return relevant


def apply_amendments(contract_data: dict, amendments: list) -> dict:
    """
    Returns a NEW dict representing the contract's effective terms after
    applying each amendment's changed_fields in chronological order.
    The original contract_data is left untouched.
    """
    effective = dict(contract_data)
    applied_summaries = []

    for amendment in amendments:
        changes = amendment["data"].get("changed_fields") or {}
        for field, value in changes.items():
            if value is not None:
                effective[field] = value
        summary = amendment["data"].get("amendment_summary")
        if summary:
            applied_summaries.append(summary)

    effective["_amendments_applied"] = applied_summaries
    return effective
