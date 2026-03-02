"""
WeChat Pay (微信支付) transaction importer.

Parses CSV and XLSX export files from WeChat Pay's bill history
(微信支付账单明细).
"""

from __future__ import annotations

import datetime
from datetime import date
from decimal import Decimal
from io import StringIO
from pathlib import Path

import dateparser
import pandas as pd
from beancount.core import data
from beancount.core.data import Directive, Transaction

from .base import BaseImporter

# Column name → metadata key mapping
_HEADER_MAPPING: dict[str, str] = {
    "交易类型": "category",
    "交易对方": "counterparty_name",
    "商品": "description",
    "收/支": "trade_type",
    "支付方式": "wechat_account",
    "当前状态": "status",
    "交易单号": "transaction_id",
    "商户单号": "merchant_order_id",
    "备注": "note",
}

# Account constants
ACCOUNT_WECHAT_CASH = "Assets:Digital:WeChat:Cash"
ACCOUNT_WECHAT_LICAI = "Assets:Digital:WeChat:LiCai"
ACCOUNT_UNKNOWN_EXPENSES = "Expenses:Unknown"
ACCOUNT_UNKNOWN_INCOME = "Income:Unknown"

# --- Valid statuses per trade direction ---
INCOME_OK_STATUSES = {"已存入零钱", "已收钱", "已到账"}
EXPENSE_OK_STATUSES = {"支付成功", "对方已收钱", "已转账", "充值成功"}
NEUTRAL_OK_STATUSES = {"支付成功", "提现已到账", "充值完成"}


class WeChatImporter(BaseImporter):
    """Import transactions from WeChat Pay CSV / XLSX exports."""

    def __init__(self, filename: str | Path) -> None:
        filename = Path(filename)

        if filename.suffix == ".csv":
            self.df = self._load_csv(filename)
        elif filename.suffix == ".xlsx":
            self.df = self._load_xlsx(filename)
        else:
            raise ValueError(
                f"Unsupported file format: {filename.suffix}. "
                "WeChat Importer supports .csv and .xlsx files."
            )

        # Strip whitespace for string columns (pandas uses dtype 'object' for strings)
        for col in self.df.columns:
            if self.df[col].dtype == object:
                self.df[col] = self.df[col].str.strip()

        # Replace all NA with empty string
        self.df = self.df.fillna("")

        # Parse amount: strip ¥ prefix, convert to Decimal
        self.df["金额(元)"] = self.df["金额(元)"].apply(
            lambda x: Decimal(str(x).strip("¥"))
            if str(x).strip() not in ("", "¥")
            else Decimal(0)
        )

    @staticmethod
    def _load_csv(filename: Path) -> pd.DataFrame:
        """Load WeChat CSV bill, skipping the metadata header lines (lines 1-16).

        WeChat CSV structure:
          Lines 1-15: metadata (昵称, 时间范围, 统计, 注释等)
          Line 16: separator "------...------"
          Line 17: column headers  (交易时间,交易类型,...,备注)
          Line 18+: data rows
        """
        with open(filename, "r", encoding="utf-8-sig") as f:
            lines = f.readlines()

        # Find the header line containing column names
        header_idx = None
        for i, line in enumerate(lines):
            if line.strip().startswith("交易时间"):
                header_idx = i
                break

        if header_idx is None:
            raise ValueError(
                f"Cannot find '交易时间' column header in {filename}. "
                "Not a valid WeChat bill CSV."
            )

        content = "".join(lines[header_idx:])
        return pd.read_csv(StringIO(content))

    @staticmethod
    def _load_xlsx(filename: Path) -> pd.DataFrame:
        """Load WeChat XLSX bill, filtering out metadata rows."""
        df = pd.read_excel(filename)
        df = df.dropna(thresh=10)
        df = df.reset_index(drop=True)
        df.columns = df.iloc[0]
        df = df.drop(0)
        return df

    @staticmethod
    def can_handle(path: Path) -> bool:
        """Return ``True`` if *path* looks like a WeChat Pay export."""
        if path.suffix not in (".csv", ".xlsx"):
            return False
        try:
            with open(path, "rb") as f:
                head = f.read(8192)
            text = head.decode("utf-8", errors="ignore")
            return "微信" in text or ("交易时间" in text and "交易类型" in text)
        except OSError:
            return False

    def parse(self) -> list[Directive]:
        """Parse all rows into beancount ``Transaction`` directives."""
        transactions: list[Directive] = []
        for idx, row in self.df.iterrows():
            entry = self._parse_row(row, str(idx))
            if entry is not None:
                transactions.append(entry)
        return transactions

    def _parse_row(self, row: pd.Series, idx: str) -> Directive | None:
        """Parse a single CSV/XLSX row into a beancount Transaction.

        Returns None for transactions that should be skipped (e.g. cancelled).
        Raises ValueError for unrecognized patterns so new patterns can be identified.
        """
        # ---- Build metadata ----
        meta = {}
        for col_name, meta_key in _HEADER_MAPPING.items():
            val = str(row.get(col_name, "")).strip()
            if val and val != "/":
                meta[meta_key] = val

        # Parse timestamp
        time_str = str(row["交易时间"]).strip()
        if not time_str:
            return None  # skip blank rows
        time = dateparser.parse(time_str)
        if time is None:
            raise ValueError(f"Row {idx}: cannot parse datetime '{time_str}'")
        time = time.replace(tzinfo=datetime.timezone(datetime.timedelta(hours=8)))
        meta["source"] = "wechat"
        meta["datetime"] = time.isoformat()

        # ---- Extract fields ----
        status = str(row["当前状态"]).strip()
        amount = row["金额(元)"]
        trade_type = str(row["收/支"]).strip()
        category = str(row["交易类型"]).strip()
        payee = str(row["交易对方"]).strip()
        narration = str(row["商品"]).strip()

        transaction_account = ACCOUNT_WECHAT_CASH
        counterparty_account = ACCOUNT_UNKNOWN_EXPENSES
        flags = "*"
        tags = []

        # ---- Tag special transactions ----
        if narration == "亲属卡":
            tags.append("love-pay")

        # ---- Determine direction & accounts based on trade type ----
        if trade_type == "收入":
            counterparty_account = ACCOUNT_UNKNOWN_INCOME
            if status in INCOME_OK_STATUSES:
                pass
            elif status == "已全额退款" or "已退款" in status:
                tags.append("refund")
                # Refunds reduce expenses, counterparty should be expense account
                counterparty_account = ACCOUNT_UNKNOWN_EXPENSES
            else:
                raise ValueError(
                    f"Row {idx}: unknown status '{status}' for income transaction.\n"
                    f"  Category='{category}', Payee='{payee}'\n"
                    f"  Please update INCOME_OK_STATUSES if this is a valid status."
                )

        elif trade_type == "支出":
            if status in EXPENSE_OK_STATUSES:
                pass
            elif status == "已全额退款" or "已退款" in status:
                tags.append("refunded")
            else:
                raise ValueError(
                    f"Row {idx}: unknown status '{status}' for expense transaction.\n"
                    f"  Category='{category}', Payee='{payee}'\n"
                    f"  Please update EXPENSE_OK_STATUSES if this is a valid status."
                )

        elif trade_type == "/":
            # Neutral transaction (internal transfer between own accounts)
            tags.append("internal-transfer")
            result = self._handle_neutral(category, status, idx)
            trade_type = result["direction"]
            transaction_account = result["transaction_account"]
            counterparty_account = result["counterparty_account"]

        else:
            raise ValueError(
                f"Row {idx}: unknown trade type '{trade_type}'.\n"
                f"  Category='{category}', Payee='{payee}'"
            )

        # ---- Create beancount Transaction ----
        # Set type BEFORE creating Transaction so it's included in metadata
        meta["type"] = trade_type

        entry = Transaction(
            data.new_metadata("unknown.beancount", 0, meta),
            date(time.year, time.month, time.day),
            flags,
            payee,
            narration,
            tags,
            data.EMPTY_SET,
            [],
        )

        if trade_type == "支出":
            data.create_simple_posting(entry, counterparty_account, amount, "CNY")
            data.create_simple_posting(entry, transaction_account, -amount, "CNY")
        elif trade_type == "收入":
            data.create_simple_posting(entry, counterparty_account, -amount, "CNY")
            data.create_simple_posting(entry, transaction_account, amount, "CNY")
        else:
            raise ValueError(f"Row {idx}: unresolved trade type '{trade_type}'")

        return entry

    def _handle_neutral(self, category: str, status: str, idx: str) -> dict[str, str]:
        """Handle neutral transactions (收/支 = /).

        Neutral transactions are internal transfers between the user's own accounts
        (WeChat Cash ↔ Bank, WeChat Cash ↔ LiCai/零钱通).

        Known categories from wechat_full_pattern_report.md:
          - 零钱充值         : Bank → WeChat Cash
          - 零钱提现         : WeChat Cash → Bank
          - 购买理财通       : WeChat Cash → LiCai
          - 转入零钱通-来自零钱: WeChat Cash → LiCai
          - 零钱通转出-到零钱  : LiCai → WeChat Cash
          - 零钱通转出-到{银行名}({后4位}): LiCai → Bank

        Returns:
            dict with: direction ("收入"/"支出"), transaction_account, counterparty_account

        Raises:
            ValueError for unrecognized category/status combinations.
        """
        if status not in NEUTRAL_OK_STATUSES:
            raise ValueError(
                f"Row {idx}: unknown status '{status}' for neutral transaction.\n"
                f"  Category='{category}'\n"
                f"  Please update NEUTRAL_OK_STATUSES if this is a valid status."
            )

        # 零钱充值: Bank → WeChat Cash (money enters WeChat)
        if category == "零钱充值":
            return {
                "direction": "收入",
                "transaction_account": ACCOUNT_WECHAT_CASH,
                # counterparty → resolved to bank by pay_account rules
                "counterparty_account": ACCOUNT_UNKNOWN_EXPENSES,
            }

        # 零钱提现: WeChat Cash → Bank (money leaves WeChat)
        if category == "零钱提现":
            return {
                "direction": "支出",
                "transaction_account": ACCOUNT_WECHAT_CASH,
                # counterparty → resolved to bank by pay_account rules
                "counterparty_account": ACCOUNT_UNKNOWN_EXPENSES,
            }

        # 购买理财通: WeChat Cash → LiCai
        if "购买理财通" in category:
            return {
                "direction": "支出",
                "transaction_account": ACCOUNT_WECHAT_CASH,
                "counterparty_account": ACCOUNT_WECHAT_LICAI,
            }

        # 转入零钱通-来自零钱: WeChat Cash → LiCai
        if "转入零钱通" in category:
            return {
                "direction": "支出",
                "transaction_account": ACCOUNT_WECHAT_CASH,
                "counterparty_account": ACCOUNT_WECHAT_LICAI,
            }

        # 零钱通转出-到零钱: LiCai → WeChat Cash
        if category == "零钱通转出-到零钱":
            return {
                "direction": "收入",
                "transaction_account": ACCOUNT_WECHAT_CASH,
                "counterparty_account": ACCOUNT_WECHAT_LICAI,
            }

        # 零钱通转出-到{银行名}({后4位}): LiCai → Bank
        if category.startswith("零钱通转出-到"):
            return {
                "direction": "支出",
                "transaction_account": ACCOUNT_WECHAT_LICAI,
                # counterparty → resolved to bank by pay_account rules (matching category)
                "counterparty_account": ACCOUNT_UNKNOWN_EXPENSES,
            }

        raise ValueError(
            f"Row {idx}: unknown neutral transaction category '{category}'.\n"
            f"  Please update _handle_neutral() to handle this new category."
        )
