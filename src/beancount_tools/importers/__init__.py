"""
Beancount importers for Chinese financial institutions.

Importers parse export files (CSV, XLSX, etc.) from banks and payment platforms
and produce beancount ``Transaction`` directives.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .alipay import AlipayImporter
from .base import BaseImporter
from .wechat import WeChatImporter

if TYPE_CHECKING:
    pass

# Registry of known importers – order matters: first match wins.
IMPORTERS: list[type[BaseImporter]] = [
    AlipayImporter,
    WeChatImporter,
]


def detect_importer(path: str | Path) -> BaseImporter | None:
    """Auto-detect and return an initialised importer for *path*.

    Iterates over :data:`IMPORTERS` and returns the first one whose
    ``can_handle`` returns ``True`` and whose ``__init__`` succeeds.
    Returns ``None`` if no importer matches.
    """
    path = Path(path)
    for cls in IMPORTERS:
        try:
            if cls.can_handle(path):
                return cls(path)
        except (ValueError, RuntimeError, OSError):
            continue
    # Fallback: try each importer constructor directly
    for cls in IMPORTERS:
        try:
            return cls(path)
        except (ValueError, RuntimeError, OSError):
            continue
    return None


__all__ = [
    "BaseImporter",
    "AlipayImporter",
    "WeChatImporter",
    "IMPORTERS",
    "detect_importer",
]
