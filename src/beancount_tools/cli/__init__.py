"""
CLI interface for beancount-tools.

Provides the ``bct`` command group with subcommands:

- ``bct import``  – Import transactions from financial institution exports
- ``bct process`` – Apply rule-based categorization to .bean files
- ``bct convert`` – Convert XLSX files to CSV
"""

from .main import cli, convert_cmd, import_cmd, postprocess_cmd

__all__ = ["cli", "import_cmd", "postprocess_cmd", "convert_cmd"]
