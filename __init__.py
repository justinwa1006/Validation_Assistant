"""Validation Assistant package.

The GUI is imported lazily so pure-logic modules and CI can run without
requiring PySide6. Access ``ValidationAssistant`` exactly as before.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = ["ValidationAssistant"]

if TYPE_CHECKING:
    from .engine import ValidationAssistant as ValidationAssistant


def __getattr__(name: str) -> Any:
    if name == "ValidationAssistant":
        from .engine import ValidationAssistant
        return ValidationAssistant
    raise AttributeError(name)
