"""
Alipay (支付宝) transaction importer.

Parses CSV export files from Alipay's transaction history
(支付宝交易记录明细查询).
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
    "交易分类": "category",
    "交易对方": "counterparty_name",
    "对方账号": "counterparty_alipay_identifier",
    "商品说明": "description",
    "收/支": "trade_type",
    "收/付款方式": "alipay_account",
    "交易状态": "status",
    "交易订单号": "transaction_id",
    "商家订单号": "merchant_order_id",
    "备注": "note",
}

# Default account constants
ACCOUNT_ALIPAY_CASH = "Assets:Digital:Alipay:Cash"
ACCOUNT_ANT_FORTUNE = "Assets:Trade:AntFortune"
ACCOUNT_UNKNOWN_EXPENSES = "Expenses:Unknown"
ACCOUNT_UNKNOWN_INCOME = "Income:Unknown"
ACCOUNT_REIMBURSEMENTS = "Income:Reimbursements"

# Required columns that must exist in a valid Alipay CSV
_REQUIRED_COLUMNS = [
    "交易时间",
    "交易分类",
    "交易对方",
    "对方账号",
    "商品说明",
    "收/支",
    "金额",
    "收/付款方式",
    "交易状态",
    "交易订单号",
    "商家订单号",
    "备注",
]


class AlipayImporter(BaseImporter):
    """Import transactions from Alipay CSV exports."""

    def __init__(self, filename: str | Path) -> None:
        filename = Path(filename)
        if filename.suffix != ".csv":
            raise ValueError("Alipay importer only supports .csv files")

        with open(filename, "rb") as f:
            lines = f.readlines()
        # Filter out non-transaction lines by checking comma count
        try:
            transaction_lines = [x.decode("utf-8") for x in lines if x.count(b",") >= 6]
        except UnicodeDecodeError:
            transaction_lines = [x.decode("gbk") for x in lines if x.count(b",") >= 6]
        content = "".join(transaction_lines)
        self.content = content
        self.df = pd.read_csv(StringIO(content), skip_blank_lines=False)

        missing_columns = [c for c in _REQUIRED_COLUMNS if c not in self.df.columns]
        if missing_columns:
            raise ValueError(f"Alipay CSV missing required columns: {missing_columns}")

        # strips leading/trailing whitespace for each str column
        for col in self.df.columns:
            if pd.api.types.is_object_dtype(self.df[col]):
                self.df[col] = self.df[col].apply(
                    lambda x: x.strip() if isinstance(x, str) else x
                )

        # replace all na with empty string
        self.df = self.df.fillna("")

        # replace 金额 column with Decimal
        self.df["金额"] = self.df["金额"].apply(
            lambda x: Decimal(str(x)) if x != "" else Decimal(0)
        )

    @staticmethod
    def can_handle(path: Path) -> bool:
        """Return ``True`` if *path* looks like an Alipay CSV export."""
        if path.suffix != ".csv":
            return False
        try:
            with open(path, "rb") as f:
                head = f.read(4096)
            # Check for characteristic Alipay columns
            text = head.decode("utf-8", errors="ignore")
            return "交易时间" in text and "交易对方" in text and "收/支" in text
        except OSError:
            return False

    def parse(self) -> list[Directive]:
        """Parse all rows into beancount ``Transaction`` directives."""
        transactions: list[Directive] = []
        for _, row in self.df.iterrows():
            meta: dict[str, str] = {}
            for key, value in _HEADER_MAPPING.items():
                if row[key] != "":
                    meta[value] = row[key]

            time = dateparser.parse(row["交易时间"])
            time = time.replace(tzinfo=datetime.timezone(datetime.timedelta(hours=8)))
            meta["source"] = "alipay"
            meta["datetime"] = time.isoformat()

            amount = Decimal(row["金额"])
            status = row["交易状态"]
            trade_type = row["收/支"]
            my_ali_account = row["收/付款方式"]

            transaction_account = ACCOUNT_ALIPAY_CASH
            counterparty_account = ACCOUNT_UNKNOWN_EXPENSES
            flags = "*"
            tags = []
            skip_entry = False

            if row["商品说明"] == "亲情卡":
                tags.append("love-pay")

            if trade_type == "支出":
                counterparty_account = ACCOUNT_UNKNOWN_EXPENSES
                if status in ["交易成功", "支付成功"]:
                    # 0元+空付款方式+支付成功 = 电商占位记录（淘宝/1688分期支付），跳过
                    if (
                        amount == Decimal(0)
                        and my_ali_account == ""
                        and status == "支付成功"
                    ):
                        skip_entry = True
                elif status == "交易关闭":
                    # 已扣款后关闭（收/付款方式非空），后续会有退款记录
                    tags.append("refunded")
                else:
                    raise ValueError(f"Unknown status for 支出: {status}")

            elif trade_type == "不计收支":
                if status == "退款成功":
                    if "退款" not in row["交易分类"] and "退款" not in row["商品说明"]:
                        raise ValueError(
                            f"Unexpected refund record without refund markers: {row}"
                        )
                    tags.append("refund")
                    trade_type = "收入"
                    counterparty_account = ACCOUNT_UNKNOWN_EXPENSES

                elif status == "交易成功":
                    if "蚂蚁财富" in row["交易对方"]:
                        counterparty_account = ACCOUNT_ANT_FORTUNE
                    if "买入" in row["商品说明"] or "转入" in row["商品说明"]:
                        trade_type = "支出"
                        if counterparty_account != ACCOUNT_ANT_FORTUNE:
                            counterparty_account = ACCOUNT_UNKNOWN_EXPENSES
                    elif (
                        "卖出" in row["商品说明"]
                        or "赎回" in row["商品说明"]
                        or "转出" in row["商品说明"]
                    ):
                        trade_type = "收入"
                        if counterparty_account != ACCOUNT_ANT_FORTUNE:
                            counterparty_account = ACCOUNT_UNKNOWN_INCOME
                    elif "因公付" in my_ali_account:
                        trade_type = "支出"
                        counterparty_account = ACCOUNT_UNKNOWN_EXPENSES
                        transaction_account = ACCOUNT_REIMBURSEMENTS
                        if "&" in my_ali_account:
                            tags.append("need_review")
                    elif "充值-普通充值" in row["商品说明"]:
                        trade_type = "支出"
                        counterparty_account = ACCOUNT_ALIPAY_CASH
                        flags = "!"
                    else:
                        raise ValueError(f"Unknown case for 不计收支: {row}")

                elif status == "交易关闭":
                    skip_entry = True
                elif status in ["芝麻免押下单成功", "解冻成功"]:
                    skip_entry = True
                else:
                    raise ValueError(f"Unknown case for 不计收支: {row}")

            elif trade_type == "收入":
                counterparty_account = ACCOUNT_UNKNOWN_INCOME
                if status == "交易成功":
                    pass
                else:
                    raise ValueError(f"Unknown status for 收入: {status}")
            else:
                raise ValueError(f"Unknown trade type: {trade_type}")

            if skip_entry:
                continue

            entry = Transaction(
                data.new_metadata("unknown.beancount", 0, meta),
                date(time.year, time.month, time.day),
                flags,
                row["交易对方"],
                row["商品说明"],
                frozenset(tags),
                data.EMPTY_SET,
                [],
            )
            meta["type"] = trade_type
            if trade_type == "支出":
                data.create_simple_posting(entry, counterparty_account, amount, "CNY")
                data.create_simple_posting(entry, transaction_account, -amount, "CNY")
            elif trade_type == "收入":
                data.create_simple_posting(entry, counterparty_account, -amount, "CNY")
                data.create_simple_posting(entry, transaction_account, amount, "CNY")
            else:
                raise ValueError(f"Unknown trade type: {trade_type}, {row}")

            transactions.append(entry)

        return transactions
