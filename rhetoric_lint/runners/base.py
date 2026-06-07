from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class StyleRunner(ABC):
    """Abstract base for external style checkers (Vale YAML, markdownlint, etc.).

    Subclasses must implement:
      - load(**kwargs): configure the runner (style dirs, enabled styles, etc.)
      - check(context) -> list[dict]: run checks and return findings

    Each finding dict must have at minimum:
      path, line, column, message, severity, check
    Never raise from check() — return an empty list on failure.
    """

    @abstractmethod
    def load(self, **kwargs: Any) -> None:
        """Load and configure the runner.  Called once before any check() calls."""

    @abstractmethod
    def check(self, context: dict) -> list[dict]:
        """Run checks against one file's context.  Return list of finding dicts."""
