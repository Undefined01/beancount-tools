"""
Unified Click-based CLI for beancount-tools.

Entry point: ``bct``

Subcommands
-----------
import   – Parse and import transactions from bank / payment-platform exports.
process  – Apply tree-based YAML rules to categorise beancount transactions.
convert  – Convert XLSX files to UTF-8 CSV.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from beancount_tools import __version__


# ---------------------------------------------------------------------------
# Root command group
# ---------------------------------------------------------------------------


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.version_option(__version__, "-V", "--version", prog_name="beancount-tools")
def cli() -> None:
    """beancount-tools – import, categorise and manage beancount transactions.

    Use ``bct <command> --help`` for details on each subcommand.
    """


# ---------------------------------------------------------------------------
# bct import
# ---------------------------------------------------------------------------


@cli.command("import")
@click.argument("input_files", nargs=-1, required=True, type=click.Path(exists=True))
@click.option(
    "-o",
    "--output",
    "output_file",
    type=click.Path(),
    help="Output .bean file.  Defaults to stdout.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview imported transactions without writing files.",
)
@click.option("--append", is_flag=True, help="Append to output file instead of overwriting.")
@click.option("-v", "--verbose", is_flag=True, help="Show detailed progress information.")
def import_cmd(
    input_files: tuple[str, ...],
    output_file: str | None,
    dry_run: bool,
    append: bool,
    verbose: bool,
) -> None:
    """Import transactions from Chinese financial institution exports.

    Accepts one or more CSV / XLSX files from Alipay or WeChat Pay and
    converts them into beancount transactions.

    \b
    Examples
    --------
      bct import alipay.csv -o imported.bean
      bct import alipay.csv wechat.csv -o all.bean -v
      bct import alipay.csv --dry-run
    """
    from beancount.parser import printer

    from beancount_tools.importers import detect_importer

    all_transactions: list = []

    for path_str in input_files:
        path = Path(path_str)
        if verbose:
            click.echo(f"Reading: {path}")

        importer = detect_importer(path)
        if importer is None:
            click.echo(f"Error: no importer found for {path}", err=True)
            continue

        if verbose:
            click.echo(f"  Using importer: {importer.__class__.__name__}")

        try:
            txns = importer.parse()
            if verbose:
                click.echo(f"  Imported {len(txns)} transactions")
            all_transactions.extend(txns)
        except Exception as exc:
            click.echo(f"Error parsing {path}: {exc}", err=True)
            if verbose:
                import traceback

                traceback.print_exc()

    if not all_transactions:
        click.echo("No transactions imported.", err=True)
        sys.exit(1)

    all_transactions.sort(key=lambda t: t.date)

    if verbose:
        click.echo(f"\nTotal: {len(all_transactions)} transactions")

    # Dry run ---------------------------------------------------------------
    if dry_run:
        click.echo("\n=== DRY RUN – transactions that would be imported ===\n")
        for entry in all_transactions:
            click.echo(printer.format_entry(entry))
        return

    # Write output ----------------------------------------------------------
    if output_file:
        mode = "a" if append else "w"
        if verbose:
            action = "Appending to" if append else "Writing to"
            click.echo(f"{action}: {output_file}")

        with open(output_file, mode, encoding="utf-8") as fh:
            if append:
                fh.write("\n\n")
            printer.print_entries(all_transactions, file=fh)

        click.echo(
            f"Successfully imported {len(all_transactions)} transactions → {output_file}"
        )
    else:
        printer.print_entries(all_transactions)


# ---------------------------------------------------------------------------
# bct process
# ---------------------------------------------------------------------------


@cli.command("process")
@click.argument("bean_file", type=click.Path(exists=True))
@click.argument("rules_files", nargs=-1, required=True, type=click.Path(exists=True))
@click.option(
    "-o",
    "--output",
    "output_file",
    type=click.Path(),
    help="Output file.  Defaults to in-place update.",
)
@click.option("-v", "--verbose", is_flag=True, help="Show matched rules and statistics.")
def postprocess_cmd(
    bean_file: str,
    rules_files: tuple[str, ...],
    output_file: str | None,
    verbose: bool,
) -> None:
    """Apply tree-based YAML rules to categorise beancount transactions.

    Reads BEAN_FILE, applies the rules defined in RULES_FILE, and writes the
    result.  Without ``-o``, the input file is updated in place.

    \b
    Examples
    --------
      bct process imported.bean rules.yaml -o categorized.bean -v
      bct process imported.bean rules.yaml          # in-place
    """
    from beancount_tools.processing import process_beancount_file
    try:
        process_beancount_file(
            bean_file=bean_file,
            rules_file=rules_files,
            output_file=output_file,
            verbose=verbose,
        )
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        if verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


# ---------------------------------------------------------------------------
# bct convert
# ---------------------------------------------------------------------------


@cli.command("convert")
@click.argument("input_files", nargs=-1, required=True, type=click.Path(exists=True))
@click.option(
    "-o",
    "--output",
    "output_path",
    type=click.Path(),
    help="Output CSV file or directory.",
)
def convert_cmd(input_files: tuple[str, ...], output_path: str | None) -> None:
    """Convert XLSX files to UTF-8 CSV.

    When a single file is given, ``-o`` can be a file path (default: same
    basename with .csv).  When multiple files are given, ``-o`` must be a
    directory.

    \b
    Examples
    --------
      bct convert data.xlsx
      bct convert data.xlsx -o output.csv
      bct convert *.xlsx -o csv_dir/
    """
    from beancount_tools.utils.convert import convert_xlsx_to_csv

    inputs = [Path(p) for p in input_files]
    out_arg = Path(output_path) if output_path else None

    if len(inputs) == 1:
        inp = inputs[0]
        if out_arg is None:
            out = inp.with_suffix(".csv")
        elif out_arg.is_dir():
            out = out_arg / inp.with_suffix(".csv").name
        else:
            out = out_arg
        convert_xlsx_to_csv(inp, out)
        click.echo(f"Converted {inp} → {out}")
    else:
        if out_arg is not None:
            out_arg.mkdir(parents=True, exist_ok=True)
            if out_arg.exists() and not out_arg.is_dir():
                click.echo(
                    "Error: -o must be a directory when converting multiple files.",
                    err=True,
                )
                sys.exit(1)
        for inp in inputs:
            out = (out_arg / inp.with_suffix(".csv").name) if out_arg else inp.with_suffix(".csv")
            convert_xlsx_to_csv(inp, out)
            click.echo(f"Converted {inp} → {out}")
