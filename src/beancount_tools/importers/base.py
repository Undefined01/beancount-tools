"""
Abstract base class for all transaction importers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

from beancount.parser import printer

if TYPE_CHECKING:
    from beancount.core.data import Directive


class BaseImporter(ABC):
    """Base class that every importer must subclass.

    Subclasses must implement:
    - ``__init__(filename)`` – validate and load the file.
    - ``parse()``            – return a list of beancount directives.

    Optionally override ``can_handle(path)`` for automatic detection.
    """

    @abstractmethod
    def __init__(self, filename: str | Path) -> None:
        """Initialise the importer with *filename*.

        Raises ``ValueError`` if the file format is not supported.
        """

    @abstractmethod
    def parse(self) -> list[Directive]:
        """Parse the loaded file and return beancount directives."""

    @staticmethod
    def can_handle(path: Path) -> bool:
        """Return ``True`` if this importer can probably handle *path*.

        The default implementation always returns ``False``.  Subclasses
        should override this with fast heuristics (file extension, header
        sniffing, etc.).
        """
        return False

    # -- convenience --------------------------------------------------------

    def write(self, filename: str | Path) -> None:
        """Write parsed entries to *filename*."""
        with open(filename, "w", encoding="utf-8") as fh:
            printer.print_entries(self.parse(), file=fh)

