# Beancount Tools

> Beancount 导入工具与规则化记账处理器。

## 功能一览

| 功能 | 说明 |
|------|------|
| **多格式导入** | 支持支付宝 CSV、微信支付 CSV / XLSX 等格式 |
| **自动去重** | 基于订单号和时间戳识别重复交易 |
| **规则引擎** | 树形 YAML 规则，自动分类、打标签、修改账户 |
| **文件转换** | XLSX → UTF-8 CSV 批量转换 |
| **统一 CLI** | 单一入口 `bct`，子命令设计，简洁高效 |

## 快速安装

```bash
# 推荐：使用 uv
uv pip install -e .

# 或者使用 pip
pip install -e .
```

安装后将获得 `bct` 命令：

```bash
bct --version        # 查看版本
bct --help           # 查看帮助
```

## 30 秒上手

```bash
# 1. 导入支付宝账单
bct import 支付宝交易记录.csv -o imported.bean

# 2. 用规则自动分类
bct process imported.bean rules.yaml -o categorized.bean

# 3. 审核后合并到主账本
cat categorized.bean >> main.bean
```

## 完整工作流

```
┌─────────────────┐
│  导出账单文件     │   ← 从支付宝/微信下载
│  (CSV / XLSX)    │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────┐
│  bct import                  │   ← 解析交易、自动检测格式
│  → 生成 Beancount 交易       │     账户暂为 Expenses:Unknown
└────────┬────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│  bct process                 │   ← 应用 YAML 规则
│  → 分类账户、添加标签         │     替换 Unknown 为具体类别
└────────┬────────────────────┘
         │
         ▼
┌─────────────────┐
│  categorized.bean│   ← 审核后追加到主账本
└─────────────────┘
```

## CLI 命令

### `bct import` — 导入交易

```bash
# 单文件导入
bct import alipay.csv -o imported.bean

# 多文件批量导入
bct import alipay.csv wechat.csv -o imported.bean

# 预览（不写文件）
bct import alipay.csv --dry-run

# 追加模式（不覆盖已有内容）
bct import alipay.csv -o imported.bean --append

# 详细输出
bct import alipay.csv -o imported.bean -v
```

### `bct process` — 规则处理

```bash
# 输出到新文件
bct process imported.bean rules.yaml -o categorized.bean

# 原地更新
bct process imported.bean rules.yaml

# 详细模式，查看哪些规则匹配了
bct process imported.bean rules.yaml -o categorized.bean -v
```

### `bct convert` — 文件转换

```bash
# XLSX 转 CSV
bct convert data.xlsx

# 指定输出路径
bct convert data.xlsx -o output.csv

# 批量转换
bct convert *.xlsx -o csv_output/
```

## 支持的文件格式

| 平台 | 格式 | 导入器 |
|------|------|--------|
| 支付宝 (Alipay) | CSV | `AlipayImporter` |
| 微信支付 (WeChat Pay) | CSV, XLSX | `WeChatImporter` |

## 规则引擎入门

规则文件使用 YAML 格式，核心是 `match` + `apply`：

```yaml
rules:
  # 按交易对方分类
  - match:
      payee: /美团/
    apply:
      counterpartyAccount: Expenses:Food:Delivery

  # 带子规则的层级分类
  - match:
      payee: /滴滴/
    apply:
      counterpartyAccount: Expenses:Transport:Taxi
    children:
      - match:
          narration: /快车/
        apply:
          counterpartyAccount: Expenses:Transport:Taxi:Express

  # 兜底：未匹配的交易打标签
  - apply:
      $add:
        tags: need_review
```

### 匹配模式

| 写法 | 含义 |
|------|------|
| `payee: 美团` | 精确匹配 |
| `payee: /美团/` | 正则搜索（包含即匹配） |
| `payee: /^美团/` | 以「美团」开头 |
| `tags: refund` | tags 集合包含 "refund" |

### 逻辑运算符

```yaml
# OR：任一匹配即可
match:
  $any:
    - payee: /美团/
    - payee: /饿了么/

# AND：全部满足
match:
  $all:
    - payee: /美团/
    - narration: /外卖/

# NOT：取反
match:
  $not:
    narration: /退款/
```

→ 完整规则语法请参考 [规则引擎文档](docs/RULES.md)

## 项目结构

```
beancount-tools/
├── pyproject.toml               # 项目配置、依赖
├── src/beancount_tools/
│   ├── __init__.py              # 公共 API
│   ├── py.typed                 # PEP 561 类型标记
│   ├── cli/                     # Click CLI
│   │   ├── __init__.py
│   │   └── main.py              # bct 命令组
│   ├── importers/               # 导入器
│   │   ├── __init__.py          # 注册表 + detect_importer()
│   │   ├── base.py              # BaseImporter ABC
│   │   ├── alipay.py            # 支付宝
│   │   └── wechat.py            # 微信支付
│   ├── processing/              # 交易处理
│   │   ├── __init__.py
│   │   ├── processor.py         # 规则应用引擎
│   │   └── deduplicate.py       # 去重逻辑
│   ├── rules/                   # 规则引擎
│   │   ├── __init__.py
│   │   └── engine.py            # RuleEngine
│   └── utils/                   # 工具函数
│       ├── __init__.py
│       ├── helpers.py            # BQL 结果解析等
│       └── convert.py            # XLSX → CSV
├── docs/                        # 文档
│   ├── CLI.md
│   ├── RULES.md
│   ├── POSTPROCESSOR.md
│   ├── QUICKREF.md
│   └── example/                 # 示例规则文件
└── tools/                       # 独立脚本
    └── xlsx_to_csv.py
```

## 编程接口 (API)

除了 CLI，也可以在 Python 中直接使用：

```python
from beancount_tools import detect_importer, RuleEngine, process_beancount_file

# 1. 导入交易
importer = detect_importer("alipay.csv")
transactions = importer.parse()

# 2. 应用规则
engine = RuleEngine(open("rules.yaml").read())
for tx in transactions:
    tx_dict = extract_transaction_fields(tx)
    engine.match_and_apply(tx_dict)

# 3. 或者直接一步到位
process_beancount_file("imported.bean", "rules.yaml", output_file="out.bean")
```

## 开发

```bash
# 安装开发依赖
uv pip install -e .

# 代码格式化
ruff format src/
ruff check src/ --fix

# 类型检查
mypy src/beancount_tools/
```

### 添加新导入器

1. 在 `src/beancount_tools/importers/` 下新建文件
2. 继承 `BaseImporter`，实现 `__init__`、`parse`、`can_handle`
3. 在 `importers/__init__.py` 的 `IMPORTERS` 列表中注册
4. 更新文档

```python
from beancount_tools.importers.base import BaseImporter

class MyBankImporter(BaseImporter):
    @staticmethod
    def can_handle(path):
        return path.suffix == ".csv" and "mybank" in path.name

    def __init__(self, filename):
        # 加载和校验文件 ...

    def parse(self):
        # 返回 beancount Transaction 列表 ...
```

## 文档

| 文档 | 内容 |
|------|------|
| [CLI 参考](docs/CLI.md) | 所有命令、选项、示例 |
| [规则引擎](docs/RULES.md) | 完整规则语法与实战案例 |
| [后处理器](docs/POSTPROCESSOR.md) | 处理流程与内部机制 |
| [速查表](docs/QUICKREF.md) | 日常使用快速参考 |

## 许可证

MIT
