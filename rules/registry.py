"""
rules/registry.py

Central list of which rules actually run. To add your own rule:
  1. Write a new class in rules/builtin.py, rules/community/, or your own file,
     subclassing BaseRule (see base_rule.py).
  2. Import it below and add an instance to ACTIVE_RULES.

That's the entire extension mechanism -- no other code needs to change.
"""

import os
import yaml

from rules.builtin import (
    ArithmeticCheck,
    StalenessCheck,
    RateMismatchCheck,
    TaxJurisdictionCheck,
)

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "tax_rules.yaml")


def _load_tax_rules() -> list:
    if not os.path.exists(_CONFIG_PATH):
        return []
    with open(_CONFIG_PATH, "r") as f:
        data = yaml.safe_load(f) or {}
    return data.get("rules", [])


def get_active_rules() -> list:
    return [
        ArithmeticCheck(),
        StalenessCheck(threshold_days=90),
        RateMismatchCheck(tolerance_pct=0.01),
        TaxJurisdictionCheck(rules_config=_load_tax_rules()),
    ]
