#!/usr/bin/env python3
"""
Beancount Post-Processing CLI

Apply tree-based rules to beancount transaction files.
"""

import argparse
import sys
from pathlib import Path

from beancount_tools.processing import process_beancount_file


def main():
    parser = argparse.ArgumentParser(
        description="Apply tree-based rules to beancount transactions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process file in-place
  python postprocess.py transactions.bean rules.yaml

  # Process and write to new file
  python postprocess.py transactions.bean rules.yaml -o output.bean

  # Verbose mode
  python postprocess.py transactions.bean rules.yaml -v
        """,
    )

    parser.add_argument("bean_file", help="Input beancount file (.bean)")

    parser.add_argument("rules_file", help="Rules file (.yaml)")

    parser.add_argument(
        "-o",
        "--output",
        dest="output_file",
        help="Output file (defaults to in-place update)",
    )

    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose output"
    )

    args = parser.parse_args()

    # Validate input files exist
    bean_path = Path(args.bean_file)
    rules_path = Path(args.rules_file)

    if not bean_path.exists():
        print(f"Error: Beancount file not found: {args.bean_file}", file=sys.stderr)
        sys.exit(1)

    if not rules_path.exists():
        print(f"Error: Rules file not found: {args.rules_file}", file=sys.stderr)
        sys.exit(1)

    try:
        process_beancount_file(
            bean_file=args.bean_file,
            rules_file=args.rules_file,
            output_file=args.output_file,
            verbose=args.verbose,
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
