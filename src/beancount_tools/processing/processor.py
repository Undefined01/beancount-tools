"""
Transaction Processor for Beancount Files

Loads beancount files, applies rule-based transformations, and writes back.
"""

from beancount import loader
from beancount.core import data
from beancount.parser import printer
from typing import Dict, Any, List
import io

from beancount_tools.rules import RuleEngine


def extract_transaction_fields(transaction: data.Transaction) -> Dict[str, Any]:
    """
    Extract fields from a Beancount Transaction into a flat dictionary.

    Includes:
    - Native fields: payee, narration, date, flag
    - All metadata fields
    """
    tx_dict = {
        "payee": transaction.payee or "",
        "narration": transaction.narration or "",
        "date": str(transaction.date),
        "flag": transaction.flag,
        "tags": transaction.tags,
    }

    # Add all metadata fields
    if transaction.meta:
        for key, value in transaction.meta.items():
            # Skip internal beancount metadata
            if not key.startswith("__"):
                tx_dict[key] = value

    if len(transaction.postings) == 2:
        tx_dict["counterpartyAccount"] = transaction.postings[0].account
        tx_dict["transactionAccount"] = transaction.postings[1].account

    return tx_dict


def update_transaction_meta(
    transaction: data.Transaction, tx_dict: Dict[str, Any]
) -> data.Transaction:
    """
    Update transaction metadata from the modified dictionary.

    Only updates metadata fields (not native fields like payee/narration).
    """
    # Create a new meta dict with updated values
    new_meta = dict(transaction.meta) if transaction.meta else {}

    # Update with modified fields from tx_dict
    # Skip native transaction fields
    native_fields = {"payee", "narration", "date", "flag", "tags"}

    special_fields = {"transactionAccount", "counterpartyAccount"}

    for key, value in tx_dict.items():
        if key not in native_fields | special_fields:
            new_meta[key] = value

    updates = {k: v for k, v in tx_dict.items() if k in native_fields}

    postings = transaction.postings
    if postings:
        assert len(postings) == 2
        # if len(postings) == 1:
        #     print(postings)
        #     assert postings[0].units.number == 0
        #     postings.append(
        #         data.Posting(
        #             account="Unknown:Counterparty",
        #             units=None,
        #             cost=None,
        #             price=None,
        #             flag=None,
        #             meta=None
        #         )
        #     )
        if "counterpartyAccount" in tx_dict:
            postings[0] = postings[0]._replace(account=tx_dict["counterpartyAccount"])
        if "transactionAccount" in tx_dict:
            postings[1] = postings[1]._replace(account=tx_dict["transactionAccount"])

    # Create a new transaction with updated metadata
    return transaction._replace(meta=new_meta, postings=postings, **updates)


def process_beancount_file(
    bean_file: str, rules_file: str, output_file: str = None, verbose: bool = False
) -> None:
    """
    Process a beancount file with rule-based transformations.

    Args:
        bean_file: Path to input .bean file
        rules_file: Path to rules YAML file
        output_file: Path to output file (defaults to in-place update)
        verbose: Enable verbose logging
    """
    # Load beancount file
    if verbose:
        print(f"Loading beancount file: {bean_file}")

    entries, errors, options_map = loader.load_file(bean_file)

    if errors:
        print(f"Warning: {len(errors)} errors found while loading:")
        for error in errors[:5]:  # Show first 5 errors
            print(f"  {error}")

    # Load rules
    if verbose:
        print(f"Loading rules from: {rules_file}")

    with open(rules_file, "r", encoding="utf-8") as f:
        rules_data = f.read()

    rule_engine = RuleEngine(rules_data)

    # Process transactions
    modified_entries = []
    transaction_count = 0
    modified_count = 0

    for entry in entries:
        if isinstance(entry, data.Transaction):
            transaction_count += 1

            # Extract fields
            tx_dict = extract_transaction_fields(entry)
            original_meta = dict(tx_dict)

            # Apply rules
            rule_engine.match_and_apply(tx_dict)

            # Check if modified
            if tx_dict != original_meta:
                modified_count += 1
                if verbose:
                    print(
                        f"Modified transaction: {entry.date} {entry.payee} {entry.narration}"
                    )

            # Update transaction
            entry = update_transaction_meta(entry, tx_dict)

        modified_entries.append(entry)

    # Write output
    output_path = output_file or bean_file

    if verbose:
        print(
            f"\nProcessed {transaction_count} transactions, modified {modified_count}"
        )
        print(f"Writing to: {output_path}")

    with open(output_path, "w", encoding="utf-8") as f:
        printer.print_entries(modified_entries, file=f)

    if verbose:
        print("Done!")
