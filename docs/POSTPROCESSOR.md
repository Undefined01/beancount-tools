# Postprocessor Documentation

Detailed documentation for the beancount transaction postprocessor.

## Table of Contents

- [Overview](#overview)
- [How It Works](#how-it-works)
- [Transaction Processing](#transaction-processing)
- [Field Extraction](#field-extraction)
- [Rule Application](#rule-application)
- [Account Updates](#account-updates)
- [Examples](#examples)
- [Advanced Topics](#advanced-topics)

---

## Overview

The postprocessor applies rule-based transformations to beancount transactions. It's designed to categorize imported transactions that have generic placeholder accounts.

### Purpose

- **Categorize transactions**: Update `Expenses:Unknown` to specific categories
- **Add metadata**: Enrich transactions with tags and custom fields
- **Modify properties**: Update payee, narration, flags
- **Update accounts**: Change both counterparty and transaction accounts

### Workflow Position

```
Import → Generic Accounts → Postprocess → Categorized Accounts
```

---

## How It Works

### Processing Pipeline

1. **Load**: Read beancount file and parse entries
2. **Load Rules**: Parse YAML rules file
3. **Extract**: Convert each transaction to flat dictionary
4. **Match**: Evaluate rules against transaction
5. **Apply**: Execute matching rule actions
6. **Update**: Convert dictionary back to transaction
7. **Write**: Output modified transactions

### Architecture

```
┌─────────────────┐
│  Beancount File │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Load Entries   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────┐
│  For Each       │────▶│  Rules YAML  │
│  Transaction    │     └──────────────┘
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Extract Fields │
│  to Dictionary  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Rule Engine    │
│  Match & Apply  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Update         │
│  Transaction    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Write Output   │
└─────────────────┘
```

---

## Transaction Processing

### Transaction Structure

Beancount transactions have this structure:

```python
Transaction(
    meta={...},           # Metadata dictionary
    date=date(...),       # Transaction date
    flag='*',             # Transaction flag
    payee='美团外卖',      # Payee
    narration='午餐',     # Description
    tags=frozenset(),     # Tags
    links=frozenset(),    # Links
    postings=[...]        # List of postings
)
```

### Posting Structure

Each transaction has postings:

```python
Posting(
    account='Expenses:Unknown',
    units=Amount(Decimal('35.50'), 'CNY'),
    cost=None,
    price=None,
    flag=None,
    meta=None
)
```

### Two-Posting Assumption

The postprocessor assumes transactions have exactly 2 postings:

1. **First posting**: Counterparty account (what you're buying/selling)
2. **Second posting**: Your account (bank/payment platform)

Example:
```beancount
2024-01-15 * "美团外卖" "午餐"
  Expenses:Unknown                    35.50 CNY  ; First posting
  Assets:Company:Alipay:StupidAlipay -35.50 CNY  ; Second posting
```

---

## Field Extraction

### Extract Transaction Fields

The postprocessor converts transactions to flat dictionaries for rule matching.

#### Native Fields

Extracted from transaction object:

- `payee` - Transaction payee (string)
- `narration` - Transaction description (string)
- `date` - Transaction date (YYYY-MM-DD string)
- `flag` - Transaction flag (string)
- `tags` - Transaction tags (set)

#### Account Fields

Extracted from postings:

- `counterpartyAccount` - First posting account
- `transactionAccount` - Second posting account

#### Metadata Fields

All metadata fields are included:

```python
{
    'payee': '美团外卖',
    'narration': '午餐',
    'date': '2024-01-15',
    'flag': '*',
    'tags': set(),
    'counterpartyAccount': 'Expenses:Unknown',
    'transactionAccount': 'Assets:Company:Alipay:StupidAlipay',
    'alipay_trade_no': '2024011522001234567890',
    'timestamp': '1705294200',
    'source': 'alipay'
}
```

### Field Types

- **Strings**: payee, narration, date, flag, accounts
- **Sets**: tags
- **Any**: metadata fields (preserved as-is)

---

## Rule Application

### Rule Matching

Rules are evaluated in order using tree-based matching:

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

Process:
1. Check if `payee` contains "美团"
2. If yes:
   - Set `counterpartyAccount` to `Expenses:Food:Delivery`
   - Check children
   - If `narration` contains "早餐", override to `Expenses:Food:Breakfast`
   - Stop processing siblings
3. If no, try next sibling rule

### Action Execution

When a rule matches, actions in `apply` are executed:

#### Set/Replace

```yaml
apply:
  counterpartyAccount: Expenses:Food:Delivery
```

Sets field to value, replacing existing value.

#### Add to Set/List

```yaml
apply:
  $add:
    tags: food
```

Adds value to set/list with deduplication.

#### Remove from Set/List

```yaml
apply:
  $remove:
    tags: uncategorized
```

Removes value from set/list.

#### Delete Field

```yaml
apply:
  $remove:
    custom_field: null
```

Deletes field from metadata.

---

## Account Updates

### Counterparty Account

The `counterpartyAccount` field updates the first posting:

**Before**:
```beancount
2024-01-15 * "美团外卖" "午餐"
  Expenses:Unknown                    35.50 CNY
  Assets:Company:Alipay:StupidAlipay -35.50 CNY
```

**Rule**:
```yaml
apply:
  counterpartyAccount: Expenses:Food:Delivery
```

**After**:
```beancount
2024-01-15 * "美团外卖" "午餐"
  Expenses:Food:Delivery              35.50 CNY
  Assets:Company:Alipay:StupidAlipay -35.50 CNY
```

### Transaction Account

The `transactionAccount` field updates the second posting:

**Before**:
```beancount
2024-01-15 * "美团外卖" "午餐"
  Expenses:Food:Delivery              35.50 CNY
  Assets:Company:Alipay:StupidAlipay -35.50 CNY
```

**Rule**:
```yaml
apply:
  transactionAccount: Assets:Bank:CCB
```

**After**:
```beancount
2024-01-15 * "美团外卖" "午餐"
  Expenses:Food:Delivery  35.50 CNY
  Assets:Bank:CCB        -35.50 CNY
```

### Metadata Updates

Metadata fields are added to transaction metadata:

**Rule**:
```yaml
apply:
  category: "food"
  $add:
    tags: delivery
```

**Result**:
```beancount
2024-01-15 * "美团外卖" "午餐"
  category: "food"
  Expenses:Food:Delivery              35.50 CNY
  Assets:Company:Alipay:StupidAlipay -35.50 CNY
  #delivery
```

---

## Examples

### Basic Categorization

**Input**:
```beancount
2024-01-15 * "美团外卖" "午餐订单"
  Expenses:Unknown                    35.50 CNY
  Assets:Company:Alipay:StupidAlipay -35.50 CNY
```

**Rules**:
```yaml
rules:
  - match:
      payee: /美团/
    apply:
      counterpartyAccount: Expenses:Food:Delivery
```

**Output**:
```beancount
2024-01-15 * "美团外卖" "午餐订单"
  Expenses:Food:Delivery              35.50 CNY
  Assets:Company:Alipay:StupidAlipay -35.50 CNY
```

### Hierarchical Categorization

**Input**:
```beancount
2024-01-15 * "美团外卖" "早餐订单"
  Expenses:Unknown                    15.00 CNY
  Assets:Company:Alipay:StupidAlipay -15.00 CNY
```

**Rules**:
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

**Output**:
```beancount
2024-01-15 * "美团外卖" "早餐订单"
  Expenses:Food:Breakfast             15.00 CNY
  Assets:Company:Alipay:StupidAlipay -15.00 CNY
```

### Adding Tags

**Input**:
```beancount
2024-01-15 * "美团外卖" "午餐订单"
  Expenses:Unknown                    35.50 CNY
  Assets:Company:Alipay:StupidAlipay -35.50 CNY
```

**Rules**:
```yaml
rules:
  - match:
      payee: /美团/
    apply:
      counterpartyAccount: Expenses:Food:Delivery
      $add:
        tags:
          - food
          - delivery
```

**Output**:
```beancount
2024-01-15 * "美团外卖" "午餐订单" #delivery #food
  Expenses:Food:Delivery              35.50 CNY
  Assets:Company:Alipay:StupidAlipay -35.50 CNY
```

### Updating Multiple Fields

**Input**:
```beancount
2024-01-15 * "美团外卖" "午餐订单"
  Expenses:Unknown                    35.50 CNY
  Assets:Company:Alipay:StupidAlipay -35.50 CNY
```

**Rules**:
```yaml
rules:
  - match:
      payee: /美团/
    apply:
      counterpartyAccount: Expenses:Food:Delivery
      category: "dining"
      flag: "*"
      $add:
        tags: food
```

**Output**:
```beancount
2024-01-15 * "美团外卖" "午餐订单" #food
  category: "dining"
  Expenses:Food:Delivery              35.50 CNY
  Assets:Company:Alipay:StupidAlipay -35.50 CNY
```

---

## Advanced Topics

### Metadata Preservation

The postprocessor preserves all existing metadata:

**Input**:
```beancount
2024-01-15 * "美团外卖" "午餐订单"
  alipay_trade_no: "2024011522001234567890"
  timestamp: "1705294200"
  Expenses:Unknown                    35.50 CNY
  Assets:Company:Alipay:StupidAlipay -35.50 CNY
```

**After processing**:
```beancount
2024-01-15 * "美团外卖" "午餐订单"
  alipay_trade_no: "2024011522001234567890"
  timestamp: "1705294200"
  Expenses:Food:Delivery              35.50 CNY
  Assets:Company:Alipay:StupidAlipay -35.50 CNY
```

### Native Field Updates

Native fields (payee, narration, flag) are updated directly:

**Rules**:
```yaml
apply:
  payee: "Meituan Delivery"
  narration: "Lunch order"
  flag: "!"
```

**Result**:
```beancount
2024-01-15 ! "Meituan Delivery" "Lunch order"
  Expenses:Food:Delivery              35.50 CNY
  Assets:Company:Alipay:StupidAlipay -35.50 CNY
```

### In-Place vs Output File

#### In-Place Update

```bash
beancount-postprocess transactions.bean rules.yaml
```

Overwrites `transactions.bean` with processed version.

#### Output File

```bash
beancount-postprocess transactions.bean rules.yaml -o output.bean
```

Writes to `output.bean`, preserves original.

### Performance Considerations

#### Transaction Count

- Small files (<1000 transactions): Instant
- Medium files (1000-10000): Seconds
- Large files (>10000): May take minutes

#### Rule Complexity

- Simple rules: Fast
- Deep trees: Slower
- Complex regex: Slower
- Many rules: Linear impact

#### Optimization Tips

1. **Put common rules first**: Reduces average evaluation time
2. **Use specific patterns**: Faster matching
3. **Limit tree depth**: Reduces recursion overhead
4. **Batch processing**: Process monthly files separately

### Error Handling

#### Invalid YAML

```bash
$ beancount-postprocess transactions.bean rules.yaml
Error: Invalid YAML syntax in rules.yaml
```

Fix: Validate YAML syntax

#### Missing Fields

If a rule references a non-existent field, it simply doesn't match:

```yaml
match:
  nonexistent_field: value
```

No error, just no match.

#### Invalid Regex

```yaml
match:
  payee: /[invalid/
```

Regex errors are caught and treated as non-matches.

### Debugging

#### Verbose Mode

```bash
beancount-postprocess transactions.bean rules.yaml -v
```

Shows:
- Which transactions are modified
- Which rules match
- Processing statistics

#### Dry Run

Process a copy first:

```bash
cp transactions.bean test.bean
beancount-postprocess test.bean rules.yaml -v
less test.bean
```

#### Incremental Testing

Test rules on small subsets:

```bash
# Extract first 10 transactions
head -50 transactions.bean > test.bean
beancount-postprocess test.bean rules.yaml -v
```

---

## Implementation Details

### Code Structure

```python
def process_beancount_file(bean_file, rules_file, output_file, verbose):
    # Load beancount file
    entries, errors, options_map = loader.load_file(bean_file)

    # Load rules
    rule_engine = RuleEngine(rules_data)

    # Process each transaction
    for entry in entries:
        if isinstance(entry, Transaction):
            # Extract to dictionary
            tx_dict = extract_transaction_fields(entry)

            # Apply rules
            rule_engine.match_and_apply(tx_dict)

            # Update transaction
            entry = update_transaction_meta(entry, tx_dict)

    # Write output
    printer.print_entries(entries, output_file)
```

### Field Extraction

```python
def extract_transaction_fields(transaction):
    tx_dict = {
        'payee': transaction.payee or '',
        'narration': transaction.narration or '',
        'date': str(transaction.date),
        'flag': transaction.flag,
        'tags': transaction.tags,
    }

    # Add metadata
    if transaction.meta:
        for key, value in transaction.meta.items():
            if not key.startswith('__'):
                tx_dict[key] = value

    # Add account fields
    if len(transaction.postings) == 2:
        tx_dict['counterpartyAccount'] = transaction.postings[0].account
        tx_dict['transactionAccount'] = transaction.postings[1].account

    return tx_dict
```

### Transaction Update

```python
def update_transaction_meta(transaction, tx_dict):
    # Update metadata
    new_meta = dict(transaction.meta) if transaction.meta else {}

    native_fields = {'payee', 'narration', 'date', 'flag', 'tags'}
    special_fields = {'transactionAccount', 'counterpartyAccount'}

    for key, value in tx_dict.items():
        if key not in native_fields | special_fields:
            new_meta[key] = value

    # Update native fields
    updates = {k: v for k, v in tx_dict.items() if k in native_fields}

    # Update postings
    postings = transaction.postings
    if 'counterpartyAccount' in tx_dict:
        postings[0] = postings[0]._replace(account=tx_dict['counterpartyAccount'])
    if 'transactionAccount' in tx_dict:
        postings[1] = postings[1]._replace(account=tx_dict['transactionAccount'])

    return transaction._replace(meta=new_meta, postings=postings, **updates)
```

---

## See Also

- [CLI Reference](CLI.md) - Command-line usage
- [Rule Engine](RULES.md) - Rule syntax and semantics
- [Examples](../config/rules.yaml) - Sample rules
