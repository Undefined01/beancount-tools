# Beancount Tools

Beancount importers and transaction processing tools for Chinese financial institutions.

## Features

- **Multi-format importers** for major Chinese banks and payment platforms
- **Automatic deduplication** to prevent duplicate imports
- **Rule-based transaction categorization** using tree-based rules
- **Batch processing** support for multiple files
- **Unmatched transaction reporting** for reconciliation

## Supported Institutions

| Institution | Format | Importer |
|------------|--------|----------|
| Alipay (支付宝) | CSV, ZIP | `AlipayImporter` |
| WeChat Pay (微信支付) | CSV, ZIP | `WeChatImporter` |

## Installation

```bash
# Install in development mode
pip install -e .

# Or using uv
uv pip install -e .
```

## Quick Start

### 1. Import Transactions

Import transactions from bank/payment platform files:

```bash
# Import single file
beancount-import alipay.csv -o imported.bean

# Import multiple files at once
beancount-import alipay.csv wechat.csv icbc.eml -o imported.bean

# Dry run to preview
beancount-import alipay.csv --dry-run
```

**Important**: Imported transactions will have generic placeholder accounts like `Expenses:Unknown` or `Income:Unknown`. You must run postprocessing to categorize them.

### 2. Categorize with Rules

Apply rule-based categorization to assign proper accounts:

```bash
# Process transactions with rules
beancount-postprocess imported.bean config/rules.yaml

# Or specify output file
beancount-postprocess imported.bean config/rules.yaml -o categorized.bean

# Verbose mode
beancount-postprocess imported.bean config/rules.yaml -v
```

### 3. Review and Merge

Review the categorized transactions and merge into your main beancount file.

## Workflow

```
┌─────────────────┐
│  Bank/Payment   │
│  Export Files   │
│  (CSV/XLS/EML)  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────┐
│  beancount-import           │
│  • Parse transactions       │
│  • Deduplicate              │
│  • Generic accounts         │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────┐
│  imported.bean  │
│  (Uncategorized)│
└────────┬────────┘
         │
         ▼
┌─────────────────────────────┐
│  beancount-postprocess      │
│  • Apply rules.yaml         │
│  • Categorize accounts      │
│  • Add metadata             │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────┐
│ categorized.bean│
│  (Ready to use) │
└─────────────────┘
```

## Documentation

- [CLI Reference](docs/CLI.md) - Command-line interface documentation
- [Rule Engine](docs/RULES.md) - How to write categorization rules
- [Postprocessor](docs/POSTPROCESSOR.md) - Transaction processing details
- [Importers](docs/IMPORTERS.md) - Importer details and file formats

## Configuration

### rules.yaml

Define tree-based rules for transaction categorization:

```yaml
rules:
  - match:
      payee: /美团/
    apply:
      counterpartyAccount: Expenses:Food:Delivery
    children:
      - match:
          narration: /早餐/
        apply:
          counterpartyAccount: Expenses:Food:Breakfast
```

See [Rule Engine Documentation](docs/RULES.md) for complete syntax.

## Examples

### Import and Process

```bash
# Step 1: Import from Alipay
beancount-import alipay_202401.csv -o jan_imported.bean -v

# Step 2: Categorize transactions
beancount-postprocess jan_imported.bean config/rules.yaml -o jan_categorized.bean -v

# Step 3: Review and append to main file
cat jan_categorized.bean >> main.bean
```

### Batch Import Multiple Sources

```bash
# Import from multiple sources at once
beancount-import \
  alipay_202401.csv \
  wechat_202401.csv \
  icbc_statement.eml \
  \
  -o jan_all.bean \
  --unmatched-report unmatched.bean
```

### Generate Unmatched Report

```bash
# Import with unmatched transaction report
beancount-import alipay.csv -o imported.bean \
  --unmatched-report unmatched.bean

# Review unmatched transactions
cat unmatched.bean
```

## Project Structure

```
beancount-tools/
├── src/beancount_tools/
│   ├── cli/              # Command-line interfaces
│   ├── importers/        # Bank/platform importers
│   ├── processing/       # Transaction processing
│   ├── rules/            # Rule engine
│   └── utils/            # Utilities
├── config/
│   ├── rules.yaml        # Categorization rules
│   └── pay_account.yaml  # Payment account mappings
├── tests/                # Test files
└── docs/                 # Documentation
```

## Development

### Running Tests

```bash
pytest tests/
```

### Adding a New Importer

1. Create importer class in `src/beancount_tools/importers/`
2. Follow the pattern from `alipay_prove.py`:
   - First posting: counterparty (generic account)
   - Second posting: user's account (specific)
3. Add to `IMPORTERS` list in `cli/import.py`
4. Update documentation

### Writing Rules

Rules use tree-based matching with stop-on-match semantics:

```yaml
rules:
  - match:
      payee: /滴滴/
    apply:
      counterpartyAccount: Expenses:Transport:Taxi
      $add:
        tags: transport
```

See [Rule Engine Documentation](docs/RULES.md) for details.

## Design Philosophy

### Separation of Concerns

- **Importers**: Parse transactions, identify direction, use generic accounts
- **Rules**: Categorize transactions based on patterns
- **Postprocessor**: Apply rules to update accounts

### Why Generic Accounts?

Importers use `Expenses:Unknown` and `Income:Unknown` because:

1. **Flexibility**: Change categorization without re-importing
2. **Maintainability**: Rules are easier to update than code
3. **Consistency**: All categorization through one system
4. **Transparency**: Clear what needs categorization

## Troubleshooting

### No transactions imported

- Check file format matches expected format
- Use `--verbose` to see detailed error messages
- Verify file encoding (should be GBK for Chinese files)

### Duplicate transactions

- Ensure you're using the correct beancount file for deduplication
- Check transaction timestamps and unique IDs
- Review unmatched report for details

### Rules not applying

- Verify YAML syntax is correct
- Use verbose mode to see which rules match
- Check field names match transaction metadata
- Test with simple rules first

## Contributing

Contributions welcome! Please:

1. Follow existing code style
2. Add tests for new features
3. Update documentation
4. Keep importers simple (no account guessing)

Formatter:

- Use `black` for Python code
- Use `prettier` for YAML files
- Use `markdownlint` for documentation
- Use `beancount-format` for beancount files

## Acknowledgments

Built for the beancount ecosystem. Thanks to the beancount community for the excellent double-entry accounting system.
