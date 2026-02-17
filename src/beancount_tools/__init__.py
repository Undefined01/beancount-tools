"""
Beancount Tools - Importers and transaction processing for Chinese financial institutions.
"""

__version__ = "0.1.0"

# Expose main components
from .importers import AlipayImporter, Base, WeChatImporter
from .processing import process_beancount_file
from .rules import RuleEngine

__all__ = [
    "__version__",
    "RuleEngine",
    "process_beancount_file",
    "Base",
    "AlipayImporter",
    "WeChatImporter",
]
