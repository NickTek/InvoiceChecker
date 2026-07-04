"""
rules/builtin.py

The default rule pack that ships with the project. These are deliberately
DETERMINISTIC (plain math/date/lookup logic, not LLM guesses) wherever
possible -- this makes them 100% reliable and explainable, which matters
a lot for a controllership tool. See README.md for how to add your own.
"""

from datetime import datetime
from rules.base_rule import BaseRule, Issue


class ArithmeticCheck(BaseRule):
    """Flags invoices where line items + tax don't add up to the stated total."""
    name = "arithmetic_check"

    def check(self, invoice_data: dict, contract_data: dict) -> list:
        issues = []
        line_items = invoice_data.get("line_items") or []
        total = invoice_data.get("total")
        tax = invoice_data.get("tax_amount") or 0

        if total is None or not line_items:
            return issues

        line_sum = sum(item.get("amount", 0) or 0 for item in line_items)
        expected_total = round(line_sum + tax, 2)

        if abs(expected_total - total) > 0.01:
            issues.append(Issue(
                rule_name=self.name,
                severity="high",
                message=(
                    f"Line items + tax sum to {expected_total}, but the invoice "
                    f"states a total of {total}. Difference: {round(total - expected_total, 2)}."
                ),
            ))
        return issues


class StalenessCheck(BaseRule):
    """Flags invoices that are unusually old relative to today."""
    name = "staleness_check"

    def __init__(self, threshold_days: int = 90):
        self.threshold_days = threshold_days

    def check(self, invoice_data: dict, contract_data: dict) -> list:
        issues = []
        invoice_date_str = invoice_data.get("invoice_date")
        if not invoice_date_str:
            return issues

        try:
            invoice_date = datetime.strptime(invoice_date_str, "%Y-%m-%d")
        except ValueError:
            return issues  # date format unrecognized -- skip rather than guess

        age_days = (datetime.now() - invoice_date).days
        if age_days > self.threshold_days:
            issues.append(Issue(
                rule_name=self.name,
                severity="medium",
                message=(
                    f"Invoice is {age_days} days old (dated {invoice_date_str}), "
                    f"exceeding the {self.threshold_days}-day staleness threshold."
                ),
            ))
        return issues


class RateMismatchCheck(BaseRule):
    """Flags invoices whose line item unit prices exceed the contracted rate."""
    name = "rate_mismatch_check"

    def __init__(self, tolerance_pct: float = 0.01):
        self.tolerance_pct = tolerance_pct

    def check(self, invoice_data: dict, contract_data: dict) -> list:
        issues = []
        contracted_rate = contract_data.get("rate_amount")
        if contracted_rate is None:
            return issues

        for item in invoice_data.get("line_items") or []:
            unit_price = item.get("unit_price")
            if unit_price is None:
                continue
            allowed_max = contracted_rate * (1 + self.tolerance_pct)
            if unit_price > allowed_max:
                issues.append(Issue(
                    rule_name=self.name,
                    severity="high",
                    message=(
                        f"Line item '{item.get('description', 'unnamed')}' is billed at "
                        f"{unit_price}, exceeding the contracted rate of {contracted_rate}."
                    ),
                ))
        return issues


class TaxJurisdictionCheck(BaseRule):
    """
    Flags cross-border service invoices where tax was charged but the
    configured jurisdiction rules say it should not have been (or vice versa).

    Rules are loaded from config/tax_rules.yaml so YOU control the actual
    tax logic -- the code does not attempt to "know" tax law on its own.
    """
    name = "tax_jurisdiction_check"

    def __init__(self, rules_config: list):
        self.rules_config = rules_config or []

    def check(self, invoice_data: dict, contract_data: dict) -> list:
        issues = []
        vendor_country = (invoice_data.get("vendor_country") or contract_data.get("vendor_country") or "").strip().lower()
        buyer_country = (invoice_data.get("buyer_country") or contract_data.get("buyer_country") or "").strip().lower()
        tax_amount = invoice_data.get("tax_amount") or 0

        if not vendor_country or not buyer_country:
            return issues  # not enough info to judge -- don't guess

        for rule in self.rules_config:
            if (
                rule.get("vendor_country", "").lower() == vendor_country
                and rule.get("buyer_country", "").lower() == buyer_country
            ):
                expected_no_tax = rule.get("tax_should_be_zero", False)
                if expected_no_tax and tax_amount > 0:
                    issues.append(Issue(
                        rule_name=self.name,
                        severity="medium",
                        message=(
                            f"Cross-border service from {vendor_country.title()} to "
                            f"{buyer_country.title()}: tax of {tax_amount} was charged, but "
                            f"configured rule '{rule.get('label', 'unnamed rule')}' says tax "
                            f"should not apply here."
                        ),
                    ))
                elif not expected_no_tax and tax_amount == 0:
                    issues.append(Issue(
                        rule_name=self.name,
                        severity="low",
                        message=(
                            f"Cross-border service from {vendor_country.title()} to "
                            f"{buyer_country.title()}: no tax was charged, but configured rule "
                            f"'{rule.get('label', 'unnamed rule')}' suggests tax should apply."
                        ),
                    ))
        return issues
