# 速查表

日常使用 beancount-tools 的快速参考。

---

## 命令速查

```bash
# 导入
bct import alipay.csv -o imported.bean
bct import alipay.csv wechat.csv -o imported.bean -v
bct import alipay.csv --dry-run

# 处理
bct process imported.bean rules.yaml -o categorized.bean
bct process imported.bean rules.yaml -v

# 转换
bct convert data.xlsx
bct convert data.xlsx -o output.csv
```

---

## 规则语法速查

### 基本规则

```yaml
rules:
  - match:
      payee: /美团/
    apply:
      counterpartyAccount: Expenses:Food:Delivery
```

### 子规则

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

### 多条件 (AND)

```yaml
match:
  $all:
    - payee: /美团/
    - narration: /外卖/
```

### 多选一 (OR)

```yaml
match:
  $any:
    - payee: /美团/
    - payee: /饿了么/
```

### 取反 (NOT)

```yaml
match:
  $not:
    narration: /退款/
```

### 标签操作

```yaml
# 添加标签
apply:
  $add:
    tags: food

# 移除标签
apply:
  $remove:
    tags: uncategorized
```

---

## 匹配模式

| 写法 | 含义 | 示例 |
|------|------|------|
| `payee: 美团` | 精确匹配 | 仅匹配 "美团" |
| `payee: /美团/` | 包含 | "美团外卖" ✓ |
| `payee: /^美团/` | 开头 | "美团" ✓ "我在美团" ✗ |
| `payee: /美团$/` | 结尾 | "去美团" ✓ |
| `narration: /早餐\|午餐/` | 多选 | 匹配任一 |
| `tags: refund` | 集合包含 | tags 中有 "refund" |

---

## 常用字段

### 交易字段

| 字段 | 说明 | 类型 |
|------|------|------|
| `payee` | 交易对方 | 字符串 |
| `narration` | 商品说明 | 字符串 |
| `date` | 日期 (YYYY-MM-DD) | 字符串 |
| `flag` | 标记 (`*` / `!`) | 字符串 |
| `tags` | 标签集合 | set |

### 账户字段

| 字段 | 说明 |
|------|------|
| `counterpartyAccount` | 对方账户（第一个 posting） |
| `transactionAccount` | 己方账户（第二个 posting） |

### 元数据字段

| 字段 | 说明 | 来源 |
|------|------|------|
| `source` | 来源 (`alipay` / `wechat`) | 所有 |
| `category` | 交易分类 | 所有 |
| `transaction_id` | 交易单号 | 所有 |
| `alipay_account` | 支付宝付款方式 | Alipay |
| `wechat_account` | 微信支付方式 | WeChat |

---

## 常见规则模板

### 餐饮

```yaml
- match:
    $any:
      - payee: /美团/
      - payee: /饿了么/
  apply:
    counterpartyAccount: Expenses:Food:Delivery
```

### 交通

```yaml
- match:
    $any:
      - payee: /滴滴/
      - payee: /高德/
  apply:
    counterpartyAccount: Expenses:Transport:Taxi
```

### 退款

```yaml
- match:
    tags: refund
  apply:
    flag: "!"
```

### 兜底

```yaml
- apply:
    $add:
      tags: need_review
```

---

## 工作流

```bash
# 1. 导入
bct import alipay.csv -o imported.bean -v

# 2. 分类
bct process imported.bean rules.yaml -o categorized.bean -v

# 3. 审核
less categorized.bean

# 4. 验证
bean-check categorized.bean

# 5. 合并
cat categorized.bean >> main.bean
```

---

## 排错

| 问题 | 解决 |
|------|------|
| 没导入交易 | 检查文件格式，用 `-v` 和 `--dry-run` |
| 规则不生效 | 用 `-v` 看匹配情况，验证 YAML 语法 |
| 编码错误 | 支付宝自动处理 GBK，微信用 UTF-8 |
| 账户错误 | 检查规则顺序（首中即停） |
