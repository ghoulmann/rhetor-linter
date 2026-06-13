"""SP23: Frontmatter metadata enforcement (opt-in).

All checks are disabled by default (const.FRONTMATTER_ENFORCEMENT_ENABLED = False).
Enable via .rhetoric-lint.yaml:

    FRONTMATTER_ENFORCEMENT_ENABLED: true

Checks
------
Metadata.MissingOwner      owner field absent
Metadata.MissingAudience   audience field absent
Metadata.InvalidAudience   audience not in const.VALID_AUDIENCE_VALUES
Metadata.Stale             date field > const.METADATA_STALE_DAYS days ago
Metadata.MissingDate       owner present but no date field
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

GENRES = frozenset({"all"})

_DATE_PATTERNS = [
    r"^\d{4}-\d{2}-\d{2}$",          # 2026-06-13
    r"^\d{4}/\d{2}/\d{2}$",           # 2026/06/13
    r"^\d{2}/\d{2}/\d{4}$",           # 06/13/2026
    r"^\d{4}-\d{2}$",                  # 2026-06
]


def _parse_date(value: Any) -> Optional[date]:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if not isinstance(value, str):
        return None
    s = value.strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%Y-%m"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def check(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    const = context.get("const")
    if const is None:
        return []

    if not getattr(const, "FRONTMATTER_ENFORCEMENT_ENABLED", False):
        return []

    path = context.get("path", "")
    frontmatter: Dict[str, Any] = context.get("frontmatter") or {}
    issues: List[Dict[str, Any]] = []

    stale_days: int = getattr(const, "METADATA_STALE_DAYS", 183)
    valid_audiences = getattr(const, "VALID_AUDIENCE_VALUES", frozenset())
    sev_levels = getattr(const, "RULE_SEVERITY_LEVELS", {})

    def _sev(check_name: str, default: str) -> str:
        return sev_levels.get(check_name, default)

    def _issue(check_name: str, message: str, severity: str) -> Dict[str, Any]:
        return {"path": path, "line": 1, "column": 1,
                "message": message, "severity": severity, "check": check_name}

    owner = frontmatter.get("owner")
    audience = frontmatter.get("audience")
    date_value = frontmatter.get("date") or frontmatter.get("updated") or frontmatter.get("last_updated")

    # Metadata.MissingOwner
    if not owner:
        issues.append(_issue(
            "Metadata.MissingOwner",
            "Frontmatter is missing an 'owner' field — add the team or person responsible for this document.",
            _sev("Metadata.MissingOwner", "warning"),
        ))

    # Metadata.MissingAudience
    if not audience:
        issues.append(_issue(
            "Metadata.MissingAudience",
            "Frontmatter is missing an 'audience' field — specify the intended reader (e.g., developer, admin).",
            _sev("Metadata.MissingAudience", "suggestion"),
        ))
    elif valid_audiences and str(audience).lower() not in valid_audiences:
        issues.append(_issue(
            "Metadata.InvalidAudience",
            f"Frontmatter 'audience' value '{audience}' is not in the approved list: {', '.join(sorted(valid_audiences))}.",
            _sev("Metadata.InvalidAudience", "suggestion"),
        ))

    # Metadata.MissingDate — only fires when owner IS present
    if owner and not date_value:
        issues.append(_issue(
            "Metadata.MissingDate",
            "Frontmatter has an 'owner' field but no 'date' field — add a date to track content freshness.",
            _sev("Metadata.MissingDate", "suggestion"),
        ))

    # Metadata.Stale — date field exists and is too old
    if date_value:
        parsed = _parse_date(date_value)
        if parsed is not None:
            today = date.today()
            age_days = (today - parsed).days
            if age_days > stale_days:
                issues.append(_issue(
                    "Metadata.Stale",
                    f"Document date '{date_value}' is {age_days} days old (threshold: {stale_days}) — review and update the content.",
                    _sev("Metadata.Stale", "warning"),
                ))

    return issues
