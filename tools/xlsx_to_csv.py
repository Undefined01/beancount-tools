#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "openpyxl>=3.1.5",
# ]
# ///
"""Convert XLSX files (assumed to be GBK encoded content) to UTF-8 CSV.

Usage:
    python xlsx_to_csv.py input.xlsx output.csv

This script reads the first sheet of the workbook and writes the contents
as a CSV with UTF-8 encoding. It handles numeric and string cells and
preserves empty cells.

Note: openpyxl does not enforce a text encoding; Excel stores text as
Unicode. The reference to GBK is for any conversion that might be needed
if the original data was saved in a specific encoding environment. The
output CSV will always be UTF-8.
"""
import sys
import csv
from pathlib import Path
import argparse

try:
    import openpyxl
except ImportError:
    sys.exit("Please install openpyxl by `pip install openpyxl`, or use uv to run this script with `uv run xlsx_to_csv.py`")


def convert_xlsx_to_csv(xlsx_path: Path, csv_path: Path) -> None:
    """Read the first sheet of ``xlsx_path`` and write to ``csv_path``.

    ``xlsx_path`` must exist; ``csv_path``'s parent directory will be created
    if necessary. Both paths are ``Path`` objects.
    """
    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb.active

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        for row in ws.iter_rows(values_only=True):
            # values_only returns Python types, may include None
            writer.writerow(["" if v is None else v for v in row])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert one or more XLSX files to UTF-8 CSV."
    )
    parser.add_argument(
        "input",
        nargs="+",
        help="input xlsx file(s) to convert",
    )
    parser.add_argument(
        "-o",
        "--output",
        help=(
            "output CSV file or directory. "
            "When converting a single input, this may be a file path (default"
            "uses the same base name with .csv). "
            "When converting multiple inputs, this must be a directory. "
            "If omitted, outputs are created alongside inputs with the"
            ".csv suffix."
        ),
    )

    args = parser.parse_args()
    inputs = [Path(p) for p in args.input]

    # validate inputs exist
    for p in inputs:
        if not p.exists():
            sys.exit(f"Input file {p} does not exist")

    out_arg = Path(args.output) if args.output else None

    if len(inputs) == 1:
        inp = inputs[0]
        if out_arg is None:
            out = inp.with_suffix(".csv")
        else:
            if out_arg.is_dir():
                out = out_arg / inp.with_suffix(".csv").name
            else:
                out = out_arg
        convert_xlsx_to_csv(inp, out)
        print(f"Converted {inp} -> {out}")
    else:
        # multiple inputs
        if out_arg is None:
            # same directory as each input
            for inp in inputs:
                out = inp.with_suffix(".csv")
                convert_xlsx_to_csv(inp, out)
                print(f"Converted {inp} -> {out}")
        else:
            if not out_arg.exists():
                # try to create
                out_arg.mkdir(parents=True, exist_ok=True)
            if not out_arg.is_dir():
                sys.exit("When converting multiple files, -o/--output must be a directory")
            for inp in inputs:
                out = out_arg / inp.with_suffix(".csv").name
                convert_xlsx_to_csv(inp, out)
                print(f"Converted {inp} -> {out}")


if __name__ == "__main__":
    main()
