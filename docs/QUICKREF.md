# Quick Reference

Quick reference for beancount-tools commands and rules.

## Commands

### Import Transactions

```bash
# Single file
beancount-import file.csv -b main.bean -o imported.bean

# Multiple files
beancount-import *.csv *.eml -b main.bean -o imported.bean

# Dry run
beancount-import file.csv -b main.bean --dry-run

# With unmatched report
beancount-import file.csv -b main.bean -o imported.bean --unmatched-report
```

### Apply Rules

```bash
# In-place
beancount-postprocess imported.bean config/rules.yaml

# To new file
beancount-postprocess imported.bean config/rules.yaml -o categorized.bean

# Verbose
beancount-postprocess imported.bean config/rules.yaml -v
```

## Rule Syntax

### Basic Rule

```yaml
rules:
  - when:
      payee: /美团/
    then:
      counterpartyAccount: Expenses:Food:Delivery
```

### With Children

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

### Multiple Conditions

```yaml
rules:
  - when:
      all:
        - payee: /美团/
        - narration: /外卖/
    then:
      counterpartyAccount: Expenses:Food:Delivery
```

### OR Conditions

```yaml
rules:
  - when:
      any:
        - payee: /美团/
        - payee: /饿了么/
    then:
      counterpartyAccount: Expenses:Food:Delivery
```

### Add Tags

```yaml
then:
  counterpartyAccount: Expenses:Food:Delivery
  +tags: food
  +tags: delivery
```

### Remove Tags

```yaml
then:
  -tags: uncategorized
```

## Pattern Matching

### Substring (case-insensitive)

```yaml
when:
  payee: 美团  # Matches if payee contains "美团"
```

### Regex

```yaml
when:
  payee: /^美团/              # Starts with
  payee: /美团$/              # Ends with
  payee: /美团|饿了么/        # OR
  narration: /早餐|午餐|晚餐/  # Multiple options
```

## Common Patterns

### Food Delivery

```yaml
- when:
    any:
      - payee: /美团/
      - payee: /饿了么/
  then:
    counterpartyAccount: Expenses:Food:Delivery
    +tags: food
```

### Transportation

```yaml
- when:
    any:
      - payee: /滴滴/
      - payee: /Uber/
  then:
    counterpartyAccount: Expenses:Transport:Taxi
    +tags: transport
```

### Shopping

```yaml
- when:
    any:
      - payee: /淘宝/
      - payee: /京东/
  then:
    counterpartyAccount: Expenses:Shopping:Online
    +tags: shopping
```

### Refunds

```yaml
- when:
    narration: /退款/
  then:
    +tags: refund
    flag: "!"
```

## Workflow

```bash
# 1. Import
beancount-import alipay.csv -b main.bean -o imported.bean -v

# 2. Categorize
beancount-postprocess imported.bean config/rules.yaml -o categorized.bean -v

# 3. Review
less categorized.bean

# 4. Validate
bean-check categorized.bean

# 5. Merge
cat categorized.bean >> main.bean
```

## Troubleshooting

### No transactions imported
- Check file format
- Use `--verbose`
- Try `--dry-run`

### Rules not applying
- Use `-v` to see matches
- Check YAML syntax
- Verify field names
- Test regex patterns

### Duplicates
- Ensure correct `-b` file
- Check transaction IDs
- Review unmatched report

## File Formats

| Format | Extension | Institution |
|--------|-----------|-------------|
| CSV | .csv | Alipay, WeChat |
| ZIP | .zip | Alipay, WeChat |
| EML | .eml | ICBC, ABC |
| XLS | .xls | CCB, YuEBao |
| HTML | .html | ICBC |

## Fields

### Transaction Fields
- `payee` - Payee name
- `narration` - Description
- `date` - Date (YYYY-MM-DD)
- `flag` - Flag (*, !)
- `tags` - Tags set

### Account Fields
- `counterpartyAccount` - First posting
- `transactionAccount` - Second posting

### Metadata
- Any custom field from importer
- `alipay_trade_no`, `timestamp`, etc.

## See Also

- [Full CLI Reference](docs/CLI.md)
- [Rule Engine Guide](docs/RULES.md)
- [Postprocessor Details](docs/POSTPROCESSOR.md)
