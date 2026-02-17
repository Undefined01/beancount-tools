#!/usr/bin/env python3
"""
Beancount Import CLI

Import transactions from various Chinese financial institutions.
"""

import argparse
import sys
from pathlib import Path
from typing import List

from beancount.parser import printer

from beancount_tools.importers import (
    AlipayImporter,
    WeChatImporter,
)


# Map of importers to try based on file patterns
IMPORTERS = [
    AlipayImporter,
    WeChatImporter,
]


def detect_importer(filename: str, byte_content: bytes, entries, option_map):
    """
    Try each importer to detect which one can handle the file.

    Args:
        filename: Name of the file to import
        byte_content: Raw bytes of the file
        entries: Existing beancount entries
        option_map: Beancount options

    Returns:
        Initialized importer instance or None
    """
    for importer_class in IMPORTERS:
        try:
            importer = importer_class(filename, byte_content, entries, option_map)
            return importer
        except (ValueError, RuntimeError, Exception) as e:
            # This importer can't handle this file, try next
            continue
    return None


def import_file(input_file: str, verbose: bool = False) -> List:
    """
    Import transactions from a single file.

    Args:
        input_file: Path to file to import
        verbose: Enable verbose output

    Returns:
        List of imported transactions
    """
    input_path = Path(input_file)

    if not input_path.exists():
        print(f"Error: File not found: {input_file}", file=sys.stderr)
        return []

    # Read input file
    if verbose:
        print(f"Reading: {input_file}")

    with open(input_file, "rb") as f:
        byte_content = f.read()

    # Detect and initialize importer
    if "支付宝" in input_file:
        importer = AlipayImporter(input_file)
    elif "微信" in input_file:
        importer = WeChatImporter(input_file)
    else:
        print(f"Error: No importer found for file: {input_file}", file=sys.stderr)
        return []

    if verbose:
        print(f"Using importer: {importer.__class__.__name__}")

    # Parse transactions
    try:
        transactions = importer.parse()
        if verbose:
            print(f"Imported {len(transactions)} transactions from {input_file}")
        return transactions
    except Exception as e:
        print(f"Error parsing {input_file}: {e}", file=sys.stderr)
        if verbose:
            import traceback

            traceback.print_exc()
        return []


def main():
    parser = argparse.ArgumentParser(
        description="Import transactions from Chinese financial institutions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Import single file
  beancount-import alipay.csv -b main.bean -o imported.bean

  # Import multiple files
  beancount-import alipay.csv wechat.csv icbc.eml -b main.bean -o imported.bean

  # Dry run (show what would be imported)
  beancount-import alipay.csv -b main.bean --dry-run

  # Verbose output
  beancount-import alipay.csv -b main.bean -o imported.bean -v

  # Generate unmatched transactions report
  beancount-import alipay.csv -b main.bean -o imported.bean --unmatched-report

Supported file formats:
  - Alipay: CSV files (支付宝交易记录明细查询)
  - Alipay Proven: CSV files (导出信息)
  - WeChat: CSV/ZIP files (微信支付账单明细)
  - ICBC Credit: EML email files (中国工商银行)
  - ICBC Debit: HTML files (中国工商银行)
  - ABC Credit: EML email files (金穗信用卡)
  - CCB Debit: XLS files (China Construction Bank)
  - YuEBao: XLS files (余额宝收支明细)
        """,
    )

    parser.add_argument(
        "input_files", nargs="+", help="Input files to import (supports multiple files)"
    )

    parser.add_argument(
        "-o",
        "--output",
        dest="output_file",
        help="Output file for imported transactions (default: stdout)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be imported without writing files",
    )

    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose output"
    )

    parser.add_argument(
        "--unmatched-report",
        help="Generate report of unmatched transactions (default: out-unmatched.bean)",
    )

    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to output file instead of overwriting",
    )

    args = parser.parse_args()

    # Import all files
    all_transactions = []
    for input_file in args.input_files:
        transactions = import_file(
            input_file, verbose=args.verbose
        )
        all_transactions.extend(transactions)

    if not all_transactions:
        print("No transactions imported", file=sys.stderr)
        sys.exit(1)

    # Sort by date
    all_transactions.sort(key=lambda t: t.date)

    if args.verbose:
        print(f"\nTotal transactions imported: {len(all_transactions)}")

    # Dry run - just show what would be imported
    if args.dry_run:
        print("\n=== DRY RUN - Transactions that would be imported ===\n")
        for entry in all_transactions:
            print(printer.format_entry(entry))
        sys.exit(0)

    # Write output
    if args.output_file:
        output_path = Path(args.output_file)
        mode = "a" if args.append else "w"

        if args.verbose:
            action = "Appending to" if args.append else "Writing to"
            print(f"{action}: {args.output_file}")

        with open(output_path, mode, encoding="utf-8") as f:
            if args.append:
                f.write("\n\n")
            printer.print_entries(all_transactions, file=f)

        print(
            f"Successfully imported {len(all_transactions)} transactions to {args.output_file}"
        )
    else:
        # Output to stdout
        printer.print_entries(all_transactions)


if __name__ == "__main__":
    main()
