"""
File-format conversion utilities.

Currently supports XLSX → CSV conversion.
"""

from __future__ import annotations

import csv
from pathlib import Path

import openpyxl


def convert_xlsx_to_csv(xlsx_path: Path, csv_path: Path) -> None:
    """Read the first sheet of *xlsx_path* and write it to *csv_path* as UTF-8 CSV.

    The parent directory of *csv_path* is created automatically if it does
    not exist.
    """
    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb.active

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        for row in ws.iter_rows(values_only=True):
            writer.writerow(["" if v is None else v for v in row])
