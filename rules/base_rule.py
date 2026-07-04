"""
rules/base_rule.py

Defines the "contract" (interface) every rule must follow.

Anyone -- including you, for a new country's tax logic, or someone else
who clones this repo -- can add a new rule by:
  1. Creating a new file in rules/community/ (or anywhere)
  2. Writing a function that matches this signature
  3. Registering it in rules/registry.py

This is what makes the checking logic "pluggable" instead of hardcoded.
"""

from dataclasses import dataclass


@dataclass
class Issue:
    rule_name: str        # which rule raised this, e.g. "arithmetic_check"
    severity: str          # "high", "medium", "low"
    message: str           # plain-English description shown to the user


class BaseRule:
    """
    Subclass this and implement `check()`.

    check() receives:
      invoice_data:  dict from core/parse.py's parse_invoice()
      contract_data: dict from core/match.py's apply_amendments()
                      (i.e. the contract's terms AFTER amendments applied)

    check() must return a list of Issue objects (empty list = no problems).
    """

    name = "unnamed_rule"

    def check(self, invoice_data: dict, contract_data: dict) -> list:
        raise NotImplementedError
