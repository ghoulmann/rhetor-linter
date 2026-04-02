from __future__ import annotations

from typing import TypedDict


class Issue(TypedDict, total=False):
    path: str
    line: int
    column: int
    message: str
    severity: str
    check: str
