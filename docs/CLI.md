# CLI 参考手册

`beancount-tools` 提供统一的命令行入口 **`bct`**，包含三个子命令。

```
bct
├── import   – 导入交易
├── process  – 规则处理
└── convert  – 文件转换
```

---

## 全局选项

```bash
bct -V / --version   # 显示版本号
bct -h / --help      # 显示帮助信息
```

---

## bct import

从支付宝 / 微信支付导出的账单文件中解析交易。

### 用法

```bash
bct import [选项] 文件...
```

### 选项

| 选项 | 说明 |
|------|------|
| `-o, --output PATH` | 输出 .bean 文件。省略则输出到 stdout |
| `--dry-run` | 预览模式，不写入文件 |
| `--append` | 追加到已有文件而非覆盖 |
| `-v, --verbose` | 显示详细处理信息 |
| `-h, --help` | 显示帮助 |

### 示例

```bash
# 导入单个文件
bct import 支付宝交易记录.csv -o imported.bean

# 批量导入多个来源
bct import alipay_jan.csv wechat_jan.csv -o jan.bean -v

# 预览（不写文件）
bct import alipay.csv --dry-run

# 追加到已有文件
bct import alipay_feb.csv -o imported.bean --append
```

### 支持的文件格式

| 平台 | 格式 | 说明 |
|------|------|------|
| 支付宝 | `.csv` | 支付宝交易记录明细查询导出 |
| 微信支付 | `.csv` | 微信支付账单明细（UTF-8） |
| 微信支付 | `.xlsx` | 微信支付账单明细（Excel） |

### 导入结果说明

导入后的交易使用占位账户（如 `Expenses:Unknown`），可通过 `bct process` 进行分类。

```beancount
2024-01-15 * "美团外卖" "午餐订单"
  source: "alipay"
  transaction_id: "2024011522001234567890"
  Expenses:Unknown                    35.50 CNY
  Assets:Digital:Alipay:Cash         -35.50 CNY
```

### 自动检测机制

`bct import` 按以下逻辑自动选择导入器：

1. 对每个注册的导入器调用 `can_handle(path)`，检测文件头特征
2. 第一个返回 `True` 的导入器被选中
3. 如果 `can_handle` 全部失败，退而逐个尝试构造函数
4. 都失败则报错

### 退出码

| 码 | 含义 |
|----|------|
| `0` | 成功 |
| `1` | 无法导入（文件不存在 / 格式不支持 / 解析错误） |

---

## bct process

对已导入的 .bean 文件应用 YAML 规则，进行自动分类。

### 用法

```bash
bct process [选项] BEAN_FILE RULES_FILE
```

### 选项

| 选项 | 说明 |
|------|------|
| `-o, --output PATH` | 输出文件。省略则原地更新 |
| `-v, --verbose` | 显示匹配详情和统计 |
| `-h, --help` | 显示帮助 |

### 示例

```bash
# 输出到新文件
bct process imported.bean rules.yaml -o categorized.bean

# 原地更新（覆盖原文件）
bct process imported.bean rules.yaml

# 详细模式，查看哪些交易被修改
bct process imported.bean rules.yaml -v
```

### 处理流程

1. 加载 .bean 文件中的所有记录
2. 加载 YAML 规则
3. 对每笔 Transaction，提取为字典 → 匹配规则 → 应用修改
4. 将修改后的记录写回

### 规则文件格式

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

→ 完整语法请参考 [规则引擎文档](RULES.md)

### 退出码

| 码 | 含义 |
|----|------|
| `0` | 成功 |
| `1` | 文件不存在 / YAML 语法错误 / 处理失败 |

---

## bct convert

将 XLSX 文件转换为 UTF-8 CSV，方便后续导入。

### 用法

```bash
bct convert [选项] 文件...
```

### 选项

| 选项 | 说明 |
|------|------|
| `-o, --output PATH` | 输出 CSV 文件或目录 |
| `-h, --help` | 显示帮助 |

### 示例

```bash
# 转换单个文件（输出为同名 .csv）
bct convert wechat_bill.xlsx

# 指定输出路径
bct convert wechat_bill.xlsx -o bill.csv

# 批量转换到指定目录
bct convert *.xlsx -o csv_output/
```

---

## 旧命令兼容

以下旧命令仍可使用，但推荐迁移到 `bct`：

| 旧命令 | 等价新命令 |
|--------|-----------|
| `beancount-import` | `bct import` |
| `beancount-postprocess` | `bct process` |

---

## 完整工作流示例

```bash
# 1. 将 XLSX 转为 CSV（如果需要）
bct convert wechat_bill.xlsx -o wechat.csv

# 2. 导入交易
bct import alipay.csv wechat.csv -o jan_imported.bean -v

# 3. 应用分类规则
bct process jan_imported.bean rules.yaml -o jan_categorized.bean -v

# 4. 审核
less jan_categorized.bean

# 5. 验证语法
bean-check jan_categorized.bean

# 6. 合并到主账本
cat jan_categorized.bean >> main.bean
```

---

## 常见问题

### 没有导入任何交易

- 检查文件格式是否正确（支付宝需要 CSV，微信支持 CSV 和 XLSX）
- 使用 `-v` 查看详细错误信息
- 使用 `--dry-run` 检查是否能检测到交易

### 规则不生效

- 使用 `-v` 查看哪些规则匹配了
- 确认 YAML 语法正确（在线校验）
- 检查字段名是否与交易元数据匹配
- 从简单规则开始测试

### 编码错误

- 支付宝 CSV 默认使用 GBK 编码，工具会自动尝试 UTF-8 和 GBK
- 微信 CSV 通常使用 UTF-8-BOM

---

## 参考

- [规则引擎](RULES.md) — 完整规则语法
- [后处理器](POSTPROCESSOR.md) — 处理流程详情
- [速查表](QUICKREF.md) — 日常命令速查
