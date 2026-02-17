# CLI Reference

Command-line interface documentation for beancount-tools.

## Commands

- [beancount-import](#beancount-import) - Import transactions from financial institutions
- [beancount-postprocess](#beancount-postprocess) - Apply rules to categorize transactions

---

## beancount-import

Import transactions from Chinese financial institutions.

### Synopsis

```bash
beancount-import [OPTIONS] INPUT_FILES...
```

### Description

The `beancount-import` command parses transaction files from various Chinese banks and payment platforms, automatically detects the file format, deduplicates against existing transactions, and outputs beancount-formatted transactions.

**Important**: Imported transactions use generic placeholder accounts (`Expenses:Unknown`, `Income:Unknown`). You must run `beancount-postprocess` to categorize them properly.

### Options

#### Required

- `-b, --beancount-file FILE`

  Path to your main beancount file. Used for deduplication to prevent importing duplicate transactions.

#### Optional

- `-o, --output FILE`

  Output file for imported transactions. If not specified, outputs to stdout.

- `--dry-run`

  Preview what would be imported without writing any files. Useful for testing.

- `-v, --verbose`

  Enable verbose output showing detailed import progress and statistics.

- `--unmatched-report [FILE]`

  Generate a report of unmatched transactions. If FILE is not specified, defaults to `out-unmatched.bean`.

  The report includes:
  - Transactions in import files that don't match existing records
  - Transactions in beancount file that don't match imported records

- `--append`

  Append to output file instead of overwriting. Useful for incremental imports.

### Arguments

- `INPUT_FILES...`

  One or more files to import. Supports multiple file formats:
  - CSV files (Alipay, WeChat)
  - ZIP files (Alipay, WeChat)
  - EML email files (ICBC, ABC)
  - XLS files (CCB, YuEBao)
  - HTML files (ICBC)

### Examples

#### Basic Import

```bash
# Import single file
beancount-import alipay.csv -b main.bean -o imported.bean
```

#### Multiple Files

```bash
# Import from multiple sources
beancount-import \
  alipay_jan.csv \
  wechat_jan.csv \
  icbc_statement.eml \
  -b main.bean \
  -o jan_imported.bean
```

#### Dry Run

```bash
# Preview what would be imported
beancount-import alipay.csv -b main.bean --dry-run
```

#### With Unmatched Report

```bash
# Generate report of unmatched transactions
beancount-import alipay.csv -b main.bean -o imported.bean \
  --unmatched-report unmatched.bean
```

#### Verbose Mode

```bash
# See detailed import progress
beancount-import alipay.csv -b main.bean -o imported.bean -v
```

Output:
```
Loading beancount file: main.bean
Reading: alipay.csv
Using importer: AlipayImporter
Import Alipay: 账户：example@email.com
Importing 美团外卖 at 2024-01-15 12:30:00
Importing 滴滴出行 at 2024-01-15 18:45:00
...
Imported 45 transactions from alipay.csv

Total transactions imported: 45
Writing to: imported.bean
Successfully imported 45 transactions to imported.bean
```

#### Append Mode

```bash
# Append to existing file
beancount-import alipay_feb.csv -b main.bean -o imported.bean --append
```

### Supported File Formats

| Format | Institution | File Extension | Notes |
|--------|-------------|----------------|-------|
| CSV | Alipay | `.csv` | 支付宝交易记录明细查询 |
| CSV | Alipay Proven | `.csv` | Contains "导出信息" |
| ZIP | Alipay | `.zip` | Contains CSV inside |
| CSV | WeChat | `.csv` | 微信支付账单明细 |
| ZIP | WeChat | `.zip` | Contains CSV inside |
| EML | ICBC Credit | `.eml` | Email from 中国工商银行 |
| HTML | ICBC Debit | `.html`, `.htm` | Web export |
| EML | ABC Credit | `.eml` | Email with 金穗信用卡 |
| XLS | CCB Debit | `.xls` | China Construction Bank |
| XLS | YuEBao | `.xls` | 余额宝收支明细 |

### How It Works

1. **File Detection**: Automatically detects file format and selects appropriate importer
2. **Parsing**: Extracts transaction data (date, payee, amount, etc.)
3. **Deduplication**: Compares against existing beancount file to avoid duplicates
4. **Output**: Generates beancount transactions with generic accounts

### Transaction Structure

Imported transactions follow this structure:

```beancount
2024-01-15 * "美团外卖" "午餐订单"
  alipay_trade_no: "2024011522001234567890"
  timestamp: "1705294200"
  Expenses:Unknown                    35.50 CNY
  Assets:Company:Alipay:StupidAlipay -35.50 CNY
```

Note:
- **First posting**: Counterparty account (generic placeholder)
- **Second posting**: Your specific account (bank/payment platform)
- **Metadata**: Transaction IDs, timestamps for deduplication

### Exit Codes

- `0` - Success
- `1` - Error (file not found, parsing error, no transactions imported)

### Common Issues

#### No transactions imported

**Problem**: Command completes but no transactions are imported.

**Solutions**:
- Verify file format matches expected format
- Use `--verbose` to see detailed error messages
- Check file encoding (Chinese files should be GBK or UTF-8)
- Try `--dry-run` to see if transactions are detected

#### File format not recognized

**Problem**: "No importer found for file"

**Solutions**:
- Verify file extension is correct
- Check file content matches expected format
- Ensure file is not corrupted
- Try opening file in text editor to verify content

#### Duplicate transactions

**Problem**: Transactions appear multiple times

**Solutions**:
- Ensure you're using the correct beancount file with `-b`
- Check that transaction IDs are unique
- Review unmatched report with `--unmatched-report`

---

## beancount-postprocess

Apply tree-based rules to categorize transactions.

### Synopsis

```bash
beancount-postprocess [OPTIONS] BEAN_FILE RULES_FILE
```

### Description

The `beancount-postprocess` command applies categorization rules from a YAML file to beancount transactions. It updates generic placeholder accounts (`Expenses:Unknown`, `Income:Unknown`) with specific categories based on transaction patterns.

### Options

- `-o, --output FILE`

  Output file for processed transactions. If not specified, updates the input file in-place.

- `-v, --verbose`

  Enable verbose output showing which transactions are modified and which rules match.

### Arguments

- `BEAN_FILE`

  Input beancount file containing transactions to process.

- `RULES_FILE`

  YAML file containing categorization rules.

### Examples

#### Basic Processing

```bash
# Process and update in-place
beancount-postprocess imported.bean config/rules.yaml
```

#### With Output File

```bash
# Process and write to new file
beancount-postprocess imported.bean config/rules.yaml -o categorized.bean
```

#### Verbose Mode

```bash
# See which rules match
beancount-postprocess imported.bean config/rules.yaml -v
```

Output:
```
Loading beancount file: imported.bean
Loading rules from: config/rules.yaml
Modified transaction: 2024-01-15 美团外卖 午餐订单
Modified transaction: 2024-01-15 滴滴出行 打车
...

Processed 45 transactions, modified 42
Writing to: imported.bean
Done!
```

### How It Works

1. **Load**: Reads beancount file and rules
2. **Match**: For each transaction, evaluates rules in order
3. **Apply**: When a rule matches, applies the `then` actions
4. **Recurse**: Processes child rules if present
5. **Stop**: Stops at first matching rule (stop-on-match semantics)
6. **Write**: Outputs updated transactions

### Rule Matching

Rules are evaluated using tree-based matching:

```yaml
rules:
  - when:
      payee: /美团/
    then:
      counterpartyAccount: Expenses:Food:Delivery
    children:
      - when:
          narration: /早餐/
        then:
          counterpartyAccount: Expenses:Food:Breakfast
```

Process:
1. Check if payee contains "美团"
2. If yes, set account to `Expenses:Food:Delivery`
3. Check child rules
4. If narration contains "早餐", override to `Expenses:Food:Breakfast`
5. Stop processing siblings

### Transaction Fields

Available fields for matching:

- `payee` - Transaction payee
- `narration` - Transaction description
- `date` - Transaction date (YYYY-MM-DD)
- `flag` - Transaction flag (*, !, etc.)
- `tags` - Transaction tags
- `counterpartyAccount` - First posting account
- `transactionAccount` - Second posting account
- Any metadata field (e.g., `alipay_trade_no`, `timestamp`)

### Exit Codes

- `0` - Success
- `1` - Error (file not found, invalid YAML, parsing error)

### Common Issues

#### Rules not applying

**Problem**: Transactions remain uncategorized

**Solutions**:
- Use `--verbose` to see which rules match
- Check YAML syntax with a validator
- Verify field names match transaction data
- Test with simple rules first
- Check regex patterns are correct

#### YAML syntax error

**Problem**: "Error loading rules"

**Solutions**:
- Validate YAML syntax online
- Check indentation (use spaces, not tabs)
- Ensure colons have spaces after them
- Quote strings with special characters

#### Wrong accounts assigned

**Problem**: Transactions categorized incorrectly

**Solutions**:
- Review rule order (first match wins)
- Check regex patterns match intended text
- Use more specific patterns
- Test rules incrementally

---

## Workflow Example

Complete workflow from import to categorized transactions:

```bash
# Step 1: Import transactions
beancount-import \
  alipay_jan.csv \
  wechat_jan.csv \
  -b main.bean \
  -o jan_imported.bean \
  -v

# Step 2: Review imported transactions
less jan_imported.bean

# Step 3: Apply categorization rules
beancount-postprocess \
  jan_imported.bean \
  config/rules.yaml \
  -o jan_categorized.bean \
  -v

# Step 4: Review categorized transactions
less jan_categorized.bean

# Step 5: Validate with beancount
bean-check jan_categorized.bean

# Step 6: Merge into main file
cat jan_categorized.bean >> main.bean
```

---

## Tips and Best Practices

### Import Tips

1. **Always use -b flag**: Ensures proper deduplication
2. **Import incrementally**: Process one month at a time
3. **Use --dry-run first**: Preview before committing
4. **Generate unmatched reports**: Helps with reconciliation
5. **Keep source files**: Don't delete original exports

### Postprocessing Tips

1. **Start with broad rules**: Refine over time
2. **Use verbose mode**: Understand rule behavior
3. **Test on small files**: Validate rules before bulk processing
4. **Version control rules.yaml**: Track rule changes
5. **Document complex rules**: Add comments in YAML

### Workflow Tips

1. **Separate import and categorization**: Easier to debug
2. **Review before merging**: Check categorized transactions
3. **Use consistent naming**: e.g., `YYYYMM_imported.bean`
4. **Backup main file**: Before merging new transactions
5. **Run bean-check**: Validate before committing

---

## See Also

- [Rule Engine Documentation](RULES.md) - Complete rule syntax
- [Postprocessor Details](POSTPROCESSOR.md) - Processing internals
- [Importer Details](IMPORTERS.md) - File format specifications
