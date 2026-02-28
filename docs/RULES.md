# 规则引擎文档

beancount-tools 规则引擎完整指南。

## 目录

- [快速入门](#快速入门)
- [核心概念](#核心概念)
- [规则结构](#规则结构)
- [match 条件](#match-条件)
- [apply 动作](#apply-动作)
- [树形语义](#树形语义)
- [实战示例](#实战示例)
- [最佳实践](#最佳实践)
- [从 v1 迁移](#从-v1-迁移)

---

## 快速入门

### 第一条规则

假设你有一笔支付宝交易，交易对方（payee）是「美团」，你希望把它归类到 `Expenses:Food:Delivery`。只需编写如下规则：

```yaml
rules:
  - match:
      payee: 美团
    apply:
      counterpartyAccount: Expenses:Food:Delivery
```

这条规则的含义是：
1. **match** — 当 `payee` 字段**精确等于** `美团` 时匹配
2. **apply** — 把对方账户设为 `Expenses:Food:Delivery`

### 使用正则匹配

如果 payee 不总是精确的「美团」，而可能是「美团外卖」「美团平台」等，使用 `/pattern/` 做正则搜索：

```yaml
rules:
  - match:
      payee: /美团/
    apply:
      counterpartyAccount: Expenses:Food:Delivery
```

`/美团/` 表示：只要 payee 中**包含**「美团」就匹配。

### 运行规则

```bash
# 对已导入的 bean 文件应用规则
beancount-postprocess imported.bean rules.yaml -o categorized.bean -v
```

### 完整的入门流程

```
原始账单 CSV
    ↓  beancount-import
导入后 .bean 文件（账户为 Expenses:Unknown 等）
    ↓  beancount-postprocess + rules.yaml
分类后 .bean 文件（账户已被规则更新）
    ↓  人工审核
追加到主账本
```

---

## 核心概念

| 概念 | 说明 |
|------|------|
| **树形结构** | 规则可以有 `children`，形成父子层级 |
| **Stop-on-Match** | 同级规则中，第一个匹配的规则生效后，后续兄弟不再尝试 |
| **条件继承** | 子规则自动继承父规则的 `match` 条件 |
| **$ 前缀运算符** | 逻辑运算符和动作运算符均以 `$` 开头（类似 MongoDB） |
| **精确匹配** | 纯字符串 = 精确匹配；`/pattern/` = 正则搜索 |
| **集合包含** | 对 set 类型字段（如 tags），匹配语义为「包含」 |

---

## 规则结构

### 顶层

```yaml
rules:
  - match: {...}
    apply: {...}
    children: [...]
  - match: {...}
    apply: {...}
```

`rules` 是一个列表，每个元素是一个**规则节点**。

### 规则节点

每个节点有三个可选部分：

```yaml
- description: "可选的描述文字"
  match:          # 匹配条件（可选，省略则始终匹配）
    field: pattern
  apply:          # 动作（可选）
    field: value
  children:       # 子规则（可选）
    - match: {...}
      apply: {...}
```

- `description` — 仅供阅读，引擎忽略
- `match` — 决定本节点是否匹配
- `apply` — 匹配成功时执行的操作
- `children` — 匹配成功后继续深入匹配的子规则列表

---

## match 条件

### 基本字段匹配

```yaml
match:
  payee: 美团
```

一个 match 中可写多个字段，它们之间是**隐式 AND**（全部满足才算匹配）：

```yaml
match:
  payee: 蚂蚁财富
  source: alipay
```

等价于：payee 精确等于 `蚂蚁财富` **并且** source 精确等于 `alipay`。

### 匹配类型

#### 精确匹配（纯字符串）

纯字符串做**精确匹配**，大小写敏感，不能多不能少：

```yaml
match:
  payee: 美团          # 仅匹配 payee 恰好等于 "美团"
  source: alipay       # 仅匹配 source 恰好等于 "alipay"
```

> ⚠ `payee: 美团` **不会**匹配 「美团外卖」或「我在美团买的」。

#### 正则匹配（`/pattern/`）

用 `/pattern/` 包裹做 **正则搜索**（`re.search`），只要字段值中有子串匹配该正则即可：

```yaml
match:
  payee: /美团/              # payee 中包含 "美团"
  payee: /^美团/             # payee 以 "美团" 开头
  payee: /美团$/             # payee 以 "美团" 结尾
  payee: /^美团$/            # payee 精确等于 "美团"（等同纯字符串）
  narration: /早餐|午餐|晚餐/  # narration 中包含 早餐、午餐 或 晚餐
  date: /^2024-01/           # 2024 年 1 月的交易
```

#### 集合字段匹配（tags 等）

对于 set/frozenset 类型的字段（如 `tags`），匹配语义是**包含**：

```yaml
match:
  tags: refund    # tags 集合中包含 "refund"
```

如需判断 tags 同时包含多个值，结合 `$all`：

```yaml
match:
  $all:
    - tags: food
    - tags: delivery
```

如需判断 tags 包含其中之一，结合 `$any`：

```yaml
match:
  $any:
    - tags: refund
    - tags: cancelled
```

### 逻辑运算符

运算符以 `$` 为前缀，放在 match 对象的键中。

#### $all（AND）

所有子条件必须全部满足：

```yaml
match:
  $all:
    - payee: /美团/
    - narration: /外卖/
```

#### $any（OR）

至少一个子条件满足即可：

```yaml
match:
  $any:
    - payee: /美团/
    - payee: /饿了么/
    - payee: /Uber Eats/
```

#### $not（取反）

否定一个子条件：

```yaml
match:
  $not:
    narration: /退款/
```

#### 混合写法

`$any`、`$all`、`$not` 可以和普通字段条件**写在同一个 match 对象**中，语义是它们之间进行 **AND** 运算：

```yaml
match:
  $any:
    - payee: /美团/
    - payee: /饿了么/
  narration: /外卖/
```

等价语义：`(payee 包含 美团 OR payee 包含 饿了么) AND (narration 包含 外卖)`

更复杂的例子：

```yaml
match:
  $any:
    - payee: /美团/
    - payee: /饿了么/
  $not:
    narration: /退款/
  source: alipay
```

语义：`(美团 OR 饿了么) AND (NOT 退款) AND (source = alipay)`

#### 嵌套组合

运算符可以任意嵌套：

```yaml
match:
  $all:
    - $any:
        - payee: /美团/
        - payee: /饿了么/
    - $not:
        narration: /退款/
```

### 空 match

省略 `match` 或写 `match: {}` 表示**始终匹配**，常用于兜底规则：

```yaml
- apply:
    $add:
      tags: need_review
```

### 可用字段

#### 交易字段

| 字段 | 说明 |
|------|------|
| `payee` | 交易对方 |
| `narration` | 交易描述 / 商品说明 |
| `date` | 交易日期（YYYY-MM-DD） |
| `flag` | 交易标记（`*`、`!` 等） |
| `tags` | 标签集合（set 类型，匹配语义为「包含」） |

#### 账户字段

| 字段 | 说明 |
|------|------|
| `counterpartyAccount` | 第一个 posting 的账户（通常是对方 / 消费类别） |
| `transactionAccount` | 第二个 posting 的账户（通常是自己的付款账户） |

#### 元数据字段

任何 importer 写入的 metadata 字段都可以匹配：

```yaml
match:
  source: alipay
  category: /餐饮美食/
  alipay_account: /工商银行/
```

---

## apply 动作

### 设置 / 替换字段

直接设置字段值，如果已有则覆盖：

```yaml
apply:
  counterpartyAccount: Expenses:Food:Delivery
  flag: "!"
```

### $add — 添加到集合或列表

使用 `$add` 运算符向 set/list 字段添加值（自动去重）：

```yaml
apply:
  $add:
    tags: food
```

添加多个值：

```yaml
apply:
  $add:
    tags:
      - food
      - delivery
```

### $remove — 从集合或列表移除

使用 `$remove` 运算符移除值：

```yaml
apply:
  $remove:
    tags: uncategorized
```

值为 `null` 时删除整个字段：

```yaml
apply:
  $remove:
    custom_field: null
```

### 混合使用

`$add`、`$remove` 可以和普通设置在同一个 apply 中：

```yaml
apply:
  counterpartyAccount: Expenses:Food:Delivery
  flag: "*"
  $add:
    tags: food
  $remove:
    tags: unknown
```

### 常用字段速查

| 字段 | 用途 | 示例 |
|------|------|------|
| `counterpartyAccount` | 设置消费/收入类别账户 | `Expenses:Food:Dining` |
| `transactionAccount` | 设置付款来源账户 | `Assets:Bank:CN:ICBC-1234` |
| `payee` | 修改交易对方名称 | `美团外卖` |
| `narration` | 修改交易描述 | `午餐订单` |
| `flag` | 设置交易标记 | `!`（需复核） |
| `$add: {tags: ...}` | 添加标签 | `need_review` |

---

## 树形语义

### Stop-on-Match（首中即停）

同一层级的规则从上到下依次尝试，**第一个匹配的规则生效后，后续兄弟不再尝试**：

```yaml
rules:
  - match:
      payee: /美团/
    apply:
      counterpartyAccount: Expenses:Food:Delivery    # ← 匹配此条

  - match:
      payee: /饿了么/
    apply:
      counterpartyAccount: Expenses:Food:Delivery    # ← 不会到达

  - match:
      narration: /外卖/
    apply:
      counterpartyAccount: Expenses:Food:Unknown     # ← 不会到达
```

如果 payee 是「美团」，只有第一条规则生效。

### 子规则（children）

父规则匹配后，先执行父规则的 apply，再进入 children 继续匹配：

```yaml
rules:
  - match:
      payee: /美团/
    apply:
      counterpartyAccount: Expenses:Food:Delivery   # ① 先设为外卖
    children:
      - match:
          narration: /早餐/
        apply:
          counterpartyAccount: Expenses:Food:Breakfast  # ② 如果是早餐，覆盖
      - match:
          narration: /午餐/
        apply:
          counterpartyAccount: Expenses:Food:Lunch      # ② 或午餐
```

执行流程：
1. payee 包含 「美团」→ 设为 `Expenses:Food:Delivery`
2. 进入 children
3. narration 包含「早餐」→ 覆盖为 `Expenses:Food:Breakfast`
4. 停止（children 中也是 stop-on-match）

### 条件继承

子规则自动继承父规则的 match 条件：

```yaml
rules:
  - match:
      payee: /美团/
    children:
      - match:
          narration: /早餐/
        apply:
          counterpartyAccount: Expenses:Food:Breakfast
```

子规则的实际条件是：`payee 包含 美团 AND narration 包含 早餐`。

### 执行流程总结

```
对于每个同级节点列表：
  依次尝试每个节点
    ├─ 计算 effective_match = parent_match AND current_match
    ├─ 如果匹配成功
    │   ├─ 执行 apply 动作
    │   ├─ 递归处理 children
    │   └─ **停止处理同级后续节点**
    └─ 如果不匹配
        └─ 尝试下一个同级节点
```

---

## 实战示例

### 支付账户识别

根据支付方式字段确定付款来源账户（注意用 `/pattern/` 做正则匹配，因为支付宝的组合支付方式如 `工商银行储蓄卡(1921)&红包`）：

```yaml
rules:
  - description: "因公付（优先匹配，防止被银行卡覆盖）"
    match:
      alipay_account: /因公付/
    apply:
      transactionAccount: Income:Reimbursements

  - match:
      alipay_account: /工商银行储蓄卡\(1921\)/
    apply:
      transactionAccount: Assets:Bank:CN:ICBC-1921

  - match:
      alipay_account: /余额宝/
    apply:
      transactionAccount: Assets:Digital:Alipay:YuEBao
```

### 交通出行分类

```yaml
rules:
  - description: "哈啰出行"
    match:
      payee: /哈啰出行/
    children:
      - match:
          narration: /哈啰单车/
        apply:
          counterpartyAccount: Expenses:Transport:Bike

      - match:
          narration: /哈啰骑行卡券/
        apply:
          counterpartyAccount: Expenses:Transport:Bike

      - apply:
          counterpartyAccount: Expenses:Transport:Bike
          $add:
            tags: need_review
```

### 多平台外卖

```yaml
rules:
  - match:
      $any:
        - payee: /美团/
        - payee: /饿了么/
    apply:
      counterpartyAccount: Expenses:Food:Delivery
    children:
      - match:
          narration: /早餐/
        apply:
          counterpartyAccount: Expenses:Food:Breakfast
      - match:
          narration: /午餐/
        apply:
          counterpartyAccount: Expenses:Food:Lunch
```

### 微信退款处理

```yaml
rules:
  - match:
      category: /-退款$/
    apply:
      $add:
        tags: refund
    children:
      - match:
          $any:
            - payee: /美团/
            - category: /^美团/
        apply:
          counterpartyAccount: Expenses:Food:Dining:Takeout

      - match:
          $any:
            - payee: /滴滴/
            - category: /^滴滴/
        apply:
          counterpartyAccount: Expenses:Transport:Taxi

      - apply:
          $add:
            tags: need_review
```

### 混合条件示例

```yaml
rules:
  - match:
      $all:
        - source: wechat
        - $not:
            category: /^零钱提现$|^零钱充值$/
    children:
      - match:
          wechat_account: /工商银行储蓄卡\(5692\)/
        apply:
          transactionAccount: Assets:Bank:CN:ICBC-5692
```

### 兜底规则

放在所有规则最后，为未匹配的交易打上标签：

```yaml
rules:
  # ... 具体规则 ...

  - apply:
      $add:
        tags: need_review
```

### 按来源分流

```yaml
rules:
  - match:
      source: wechat
    children:
      # 微信专用规则...
      - match:
          category: /^商户消费$/
        children:
          - match:
              payee: /^美团$/
            apply:
              counterpartyAccount: Expenses:Food:Dining:Takeout

  - match:
      source: alipay
    children:
      # 支付宝专用规则...
      - match:
          payee: /蚂蚁财富/
        apply:
          counterpartyAccount: Assets:Trade:AntFortune
```

---

## 最佳实践

### 规则组织

1. **顺序很重要**：具体规则在前，兜底规则在后
2. **按类别分组**：相关规则放在一起，用注释分隔
3. **善用注释**：复杂规则加 `description` 和 YAML 注释
4. **账户命名一致**：遵循 beancount 命名惯例，层级 3-4 级为宜

```yaml
rules:
  # === 投资理财 ===
  - match:
      payee: /蚂蚁财富/
    apply:
      counterpartyAccount: Assets:Trade:AntFortune

  # === 餐饮外卖 ===
  - match:
      payee: /美团/
    apply:
      counterpartyAccount: Expenses:Food:Delivery

  # === 交通出行 ===
  - match:
      payee: /滴滴/
    apply:
      counterpartyAccount: Expenses:Transport:Taxi

  # === 兜底 ===
  - apply:
      $add:
        tags: need_review
```

### 匹配模式选择

| 场景 | 推荐写法 |
|------|---------|
| 字段值固定不变 | `payee: 美团`（精确匹配） |
| 字段值有变体 | `payee: /美团/`（正则搜索，包含即可） |
| 以某词开头 | `payee: /^美团/` |
| 以某词结尾 | `category: /-退款$/` |
| 多选一 | `payee: /美团\|饿了么/` 或用 `$any` |
| 组合支付方式 | `alipay_account: /工商银行/`（正则搜索） |

### 性能建议

1. **高频规则在前**：减少平均评估次数
2. **用具体条件**：避免过于宽泛的正则
3. **控制树深度**：一般不超过 3 层
4. **简化正则**：简单模式比复杂正则更快

### 调试技巧

```bash
# 使用 verbose 模式查看匹配情况
beancount-postprocess imported.bean rules.yaml -v

# 先用小文件测试
head -20 imported.bean > test.bean
beancount-postprocess test.bean rules.yaml -o test_out.bean -v
```

---

## 参考

- [CLI Reference](CLI.md) — 命令行使用
- [Postprocessor](POSTPROCESSOR.md) — 处理流程详情
