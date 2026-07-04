"""
rules/community/example_rule_template.py

COPY THIS FILE to create your own rule. This one is not active by default --
it's a template. To activate a new rule:
  1. Copy this file, rename it, and write your logic in check().
  2. Open rules/registry.py, import your class, and add it to get_active_rules().

Example use case shown below: flag any invoice missing a PO/contract
reference number entirely (some companies require this on every invoice).
"""

from rules.base_rule import BaseRule, Issue


class MissingReferenceCheck(BaseRule):
    name = "missing_reference_check"

    def check(self, invoice_data: dict, contract_data: dict) -> list:
        issues = []
        if not invoice_data.get("contract_id_referenced"):
            issues.append(Issue(
                rule_name=self.name,
                severity="low",
                message="Invoice does not reference a contract/PO number.",
            ))
        return issues
