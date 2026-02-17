# Rule Engine Documentation

Complete guide to writing categorization rules for beancount-tools.

## Table of Contents

- [Overview](#overview)
- [Rule Structure](#rule-structure)
- [When Conditions](#when-conditions)
- [Then Actions](#then-actions)
- [Tree Semantics](#tree-semantics)
- [Examples](#examples)
- [Best Practices](#best-practices)

---

## Overview

The rule engine uses tree-based rules to categorize transactions. Rules match transaction fields and apply actions to update accounts, add metadata, or modify transaction properties.

### Key Concepts

- **Tree-based**: Rules can have children for hierarchical matching
- **Stop-on-match**: First matching rule at each level stops sibling processing
- **Inheritance**: Child rules inherit parent conditions
- **Pattern matching**: Supports regex and substring matching

### Basic Example

```yaml
rules:
  - when:
      payee: /美团/
    then:
      counterpartyAccount: Expenses:Food:Delivery
```

This rule:
1. Matches transactions where payee contains "美团"
2. Sets the counterparty account to `Expenses:Food:Delivery`

---

## Rule Structure

### Top Level

```yaml
rules:
  - when: {...}
    then: {...}
    children: [...]
  - when: {...}
    then: {...}
```

### Rule Node

Each rule node has three optional parts:

```yaml
- when:        # Condition (optional, defaults to always match)
    field: pattern
  then:        # Actions (optional)
    field: value
  children:    # Child rules (optional)
    - when: {...}
      then: {...}
```

---

## When Conditions

The `when` clause specifies matching conditions.

### Atomic Conditions

Match a single field against a pattern:

```yaml
when:
  payee: /美团/
  narration: 外卖
```

Multiple fields use implicit AND logic (all must match).

### Pattern Types

#### Substring Match

Case-insensitive substring matching:

```yaml
when:
  payee: 美团        # Matches if payee contains "美团"
  narration: 外卖    # Matches if narration contains "外卖"
```

#### Regex Match

Use `/pattern/` for regex:

```yaml
when:
  payee: /^美团/              # Starts with "美团"
  narration: /早餐|午餐|晚餐/  # Contains 早餐, 午餐, or 晚餐
  date: /2024-01-.*/          # January 2024
```

### Logical Operators

#### All (AND)

All conditions must match:

```yaml
when:
  all:
    - payee: /美团/
    - narration: /外卖/
```

Equivalent to:
```yaml
when:
  payee: /美团/
  narration: /外卖/
```

#### Any (OR)

At least one condition must match:

```yaml
when:
  any:
    - payee: /美团/
    - payee: /饿了么/
    - payee: /Uber Eats/
```

#### Not

Negates a condition:

```yaml
when:
  not:
    payee: /退款/
```

#### Complex Logic

Combine operators:

```yaml
when:
  all:
    - any:
        - payee: /美团/
        - payee: /饿了么/
    - not:
        narration: /退款/
```

Matches: (美团 OR 饿了么) AND NOT 退款

### Available Fields

#### Transaction Fields

- `payee` - Transaction payee
- `narration` - Transaction description
- `date` - Transaction date (YYYY-MM-DD format)
- `flag` - Transaction flag (*, !, etc.)
- `tags` - Transaction tags (set)

#### Account Fields

- `counterpartyAccount` - First posting account
- `transactionAccount` - Second posting account

#### Metadata Fields

Any metadata field can be matched:

```yaml
when:
  alipay_trade_no: /^2024/
  timestamp: /^1705/
  source: alipay
```

### Empty When

Omitting `when` matches all transactions:

```yaml
- then:
    counterpartyAccount: Expenses:Unknown
```

---

## Then Actions

The `then` clause specifies actions to apply when conditions match.

### Set/Replace

Set or replace a field value:

```yaml
then:
  counterpartyAccount: Expenses:Food:Delivery
  flag: "*"
  custom_field: "processed"
```

### Add to List/Set

Use `+` prefix to add to a list or set:

```yaml
then:
  +tags: food
  +tags: delivery
```

Result: Adds "food" and "delivery" to transaction tags.

### Remove from List/Set

Use `-` prefix to remove:

```yaml
then:
  -tags: uncategorized
```

### Delete Field

Use `-` with null value:

```yaml
then:
  -custom_field: null
```

### Special Fields

#### counterpartyAccount

Updates the first posting account:

```yaml
then:
  counterpartyAccount: Expenses:Food:Breakfast
```

#### transactionAccount

Updates the second posting account:

```yaml
then:
  transactionAccount: Assets:Bank:CCB
```

#### payee

Updates transaction payee:

```yaml
then:
  payee: "美团外卖"
```

#### narration

Updates transaction description:

```yaml
then:
  narration: "午餐订单"
```

#### flag

Updates transaction flag:

```yaml
then:
  flag: "!"  # Mark for review
```

#### tags

Adds or removes tags:

```yaml
then:
  +tags: reviewed
  -tags: pending
```

---

## Tree Semantics

### Stop-on-Match

When a rule matches, its siblings are not evaluated:

```yaml
rules:
  - when:
      payee: /美团/
    then:
      counterpartyAccount: Expenses:Food:Delivery
  - when:
      payee: /饿了么/
    then:
      counterpartyAccount: Expenses:Food:Delivery
  - when:
      narration: /外卖/
    then:
      counterpartyAccount: Expenses:Food:Unknown
```

If payee is "美团", only the first rule applies. The third rule is never evaluated.

### Child Rules

Child rules are evaluated after parent actions:

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
      - when:
          narration: /午餐/
        then:
          counterpartyAccount: Expenses:Food:Lunch
```

Process:
1. Match payee "美团" → Set to `Expenses:Food:Delivery`
2. Check children
3. If narration contains "早餐" → Override to `Expenses:Food:Breakfast`
4. Stop (stop-on-match for children)

### Condition Inheritance

Child rules inherit parent conditions:

```yaml
rules:
  - when:
      payee: /美团/
    children:
      - when:
          narration: /早餐/
        then:
          counterpartyAccount: Expenses:Food:Breakfast
```

Child condition is effectively: `payee: /美团/ AND narration: /早餐/`

### Execution Order

1. Evaluate `when` condition (including inherited conditions)
2. If match:
   - Execute `then` actions
   - Recursively process `children`
   - Stop processing siblings
3. If no match, try next sibling

---

## Examples

### Basic Categorization

```yaml
rules:
  - when:
      payee: /美团/
    then:
      counterpartyAccount: Expenses:Food:Delivery

  - when:
      payee: /滴滴/
    then:
      counterpartyAccount: Expenses:Transport:Taxi

  - when:
      payee: /中国移动/
    then:
      counterpartyAccount: Expenses:Utilities:Phone
```

### Hierarchical Categories

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
      - when:
          narration: /午餐/
        then:
          counterpartyAccount: Expenses:Food:Lunch
      - when:
          narration: /晚餐/
        then:
          counterpartyAccount: Expenses:Food:Dinner
```

### Multiple Conditions

```yaml
rules:
  - when:
      all:
        - payee: /美团/
        - narration: /外卖/
        - not:
            narration: /退款/
    then:
      counterpartyAccount: Expenses:Food:Delivery
      +tags: food
      +tags: delivery
```

### Date-Based Rules

```yaml
rules:
  - when:
      date: /2024-01-.*/
    then:
      +tags: january
      +tags: "2024"

  - when:
      all:
        - date: /2024-01-.*/
        - payee: /美团/
    then:
      counterpartyAccount: Expenses:Food:Delivery
      +tags: new-year-promo
```

### Metadata-Based Rules

```yaml
rules:
  - when:
      source: alipay
    then:
      +tags: alipay
    children:
      - when:
          category: /转账/
        then:
          counterpartyAccount: Assets:Transfer
      - when:
          category: /退款/
        then:
          +tags: refund
```

### Income Categorization

```yaml
rules:
  - when:
      counterpartyAccount: Income:Unknown
    children:
      - when:
          payee: /工资/
        then:
          counterpartyAccount: Income:Salary
      - when:
          payee: /奖金/
        then:
          counterpartyAccount: Income:Bonus
      - when:
          narration: /利息/
        then:
          counterpartyAccount: Income:Interest
```

### Complex Hierarchy

```yaml
rules:
  # Food expenses
  - when:
      any:
        - payee: /美团/
        - payee: /饿了么/
        - payee: /Uber Eats/
    then:
      counterpartyAccount: Expenses:Food:Delivery
      +tags: food
    children:
      - when:
          narration: /早餐/
        then:
          counterpartyAccount: Expenses:Food:Breakfast
      - when:
          narration: /午餐/
        then:
          counterpartyAccount: Expenses:Food:Lunch
      - when:
          narration: /晚餐/
        then:
          counterpartyAccount: Expenses:Food:Dinner
      - when:
          narration: /夜宵/
        then:
          counterpartyAccount: Expenses:Food:Snack

  # Transport
  - when:
      any:
        - payee: /滴滴/
        - payee: /Uber/
        - payee: /出租车/
    then:
      counterpartyAccount: Expenses:Transport:Taxi
      +tags: transport

  # Shopping
  - when:
      any:
        - payee: /淘宝/
        - payee: /京东/
        - payee: /拼多多/
    then:
      counterpartyAccount: Expenses:Shopping:Online
      +tags: shopping
    children:
      - when:
          narration: /图书/
        then:
          counterpartyAccount: Expenses:Education:Books
          +tags: education
      - when:
          narration: /电子产品/
        then:
          counterpartyAccount: Expenses:Electronics
```

### Refund Handling

```yaml
rules:
  - when:
      any:
        - narration: /退款/
        - tags: refund
    then:
      +tags: refund
      flag: "!"
    children:
      - when:
          payee: /美团/
        then:
          counterpartyAccount: Expenses:Food:Delivery
      - when:
          payee: /淘宝/
        then:
          counterpartyAccount: Expenses:Shopping:Online
```

### Catch-All Rules

```yaml
rules:
  # Specific rules first
  - when:
      payee: /美团/
    then:
      counterpartyAccount: Expenses:Food:Delivery

  # ... more specific rules ...

  # Catch-all for expenses
  - when:
      counterpartyAccount: Expenses:Unknown
    then:
      counterpartyAccount: Expenses:Uncategorized
      flag: "!"
      +tags: needs-review

  # Catch-all for income
  - when:
      counterpartyAccount: Income:Unknown
    then:
      counterpartyAccount: Income:Other
      flag: "!"
      +tags: needs-review
```

---

## Best Practices

### Rule Organization

1. **Order matters**: Put specific rules before general ones
2. **Group by category**: Keep related rules together
3. **Use comments**: Document complex rules
4. **Consistent naming**: Use consistent account naming scheme

```yaml
rules:
  # === Food & Dining ===
  - when:
      payee: /美团/
    then:
      counterpartyAccount: Expenses:Food:Delivery

  # === Transportation ===
  - when:
      payee: /滴滴/
    then:
      counterpartyAccount: Expenses:Transport:Taxi

  # === Utilities ===
  - when:
      payee: /中国移动/
    then:
      counterpartyAccount: Expenses:Utilities:Phone
```

### Pattern Writing

1. **Start simple**: Use substring matching first
2. **Add regex when needed**: For complex patterns
3. **Test patterns**: Verify they match intended transactions
4. **Avoid over-matching**: Be specific enough

```yaml
# Good: Specific pattern
when:
  payee: /^美团外卖/

# Bad: Too broad
when:
  payee: /美/
```

### Account Naming

1. **Hierarchical**: Use colon-separated hierarchy
2. **Consistent**: Follow beancount conventions
3. **Descriptive**: Clear category names
4. **Not too deep**: 3-4 levels maximum

```yaml
# Good
counterpartyAccount: Expenses:Food:Delivery

# Bad: Too deep
counterpartyAccount: Expenses:Food:Delivery:Lunch:Weekday:Office
```

### Performance

1. **Put common rules first**: Reduces evaluation time
2. **Use specific conditions**: Faster than broad patterns
3. **Limit tree depth**: Deep trees are slower
4. **Avoid complex regex**: Simple patterns are faster

### Testing

1. **Test incrementally**: Add rules one at a time
2. **Use verbose mode**: See which rules match
3. **Start with small files**: Test on subset of transactions
4. **Validate output**: Check categorized transactions

```bash
# Test new rules
beancount-postprocess test.bean rules.yaml -v

# Review output
less test.bean
```

### Maintenance

1. **Version control**: Track rules.yaml in git
2. **Document changes**: Add comments for complex rules
3. **Review regularly**: Update rules as spending patterns change
4. **Refactor**: Simplify rules periodically

### Common Patterns

#### Default with Overrides

```yaml
rules:
  - when:
      payee: /美团/
    then:
      counterpartyAccount: Expenses:Food:Delivery
      +tags: food
    children:
      # Override for specific cases
      - when:
          narration: /充值/
        then:
          counterpartyAccount: Assets:Prepaid:Meituan
          -tags: food
          +tags: prepaid
```

#### Multi-Level Categorization

```yaml
rules:
  - when:
      payee: /美团/
    then:
      +tags: meituan
    children:
      - when:
          narration: /外卖/
        then:
          counterpartyAccount: Expenses:Food:Delivery
      - when:
          narration: /电影/
        then:
          counterpartyAccount: Expenses:Entertainment:Movies
      - when:
          narration: /酒店/
        then:
          counterpartyAccount: Expenses:Travel:Hotel
```

#### Conditional Tagging

```yaml
rules:
  - when:
      payee: /美团/
    then:
      counterpartyAccount: Expenses:Food:Delivery
    children:
      - when:
          narration: /工作餐/
        then:
          +tags: work
          +tags: reimbursable
```

---

## Troubleshooting

### Rules Not Matching

**Problem**: Expected rule doesn't apply

**Debug steps**:
1. Use `--verbose` to see which rules match
2. Check pattern syntax (regex needs `/pattern/`)
3. Verify field names are correct
4. Test pattern in isolation
5. Check for typos in field values

### Wrong Rule Matches

**Problem**: Unexpected rule applies

**Debug steps**:
1. Check rule order (first match wins)
2. Review parent conditions (inheritance)
3. Make patterns more specific
4. Use `not` to exclude cases

### Performance Issues

**Problem**: Processing is slow

**Solutions**:
1. Reduce tree depth
2. Simplify regex patterns
3. Put common rules first
4. Limit number of rules

---

## See Also

- [CLI Reference](CLI.md) - Command-line usage
- [Postprocessor](POSTPROCESSOR.md) - Processing details
- [Examples](../config/rules.yaml) - Sample rules file
