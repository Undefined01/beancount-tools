"""
Beancount Tools – importers and transaction processing for Chinese financial institutions.
"""

from __future__ import annotations

__version__ = "0.2.0"

# Expose main public API
from .importers import AlipayImporter, BaseImporter, WeChatImporter, detect_importer
from .processing import process_beancount_file
from .rules import RuleEngine

__all__ = [
    "__version__",
    "BaseImporter",
    "AlipayImporter",
    "WeChatImporter",
    "detect_importer",
    "RuleEngine",
    "process_beancount_file",
]
