import datetime
from datetime import date
from decimal import Decimal
from pathlib import Path

import dateparser
import pandas as pd
from beancount.core import data
from beancount.core.data import Transaction

from .base import Base

header_mapping = {
    "交易类型": "category",
    "支付方式": "transaction_wechat_account",
    "交易单号": "transaction_id",
    "商户单号": "merchant_order_id",
    "备注": "note",
}

account_wechat_balance = "Assets:Digital:WeChat:Balance"
account_unknown_expenses = "Expenses:Unknown"


class WeChatImporter(Base):

    def __init__(self, filename):
        # Load xlsx file, skip the lines that has less than 5 columns (e.g., summary lines), and converts to pandas dataframe for easier processing
        # The column headings are in the first filtered line
        filename = Path(filename)
        assert filename.suffix == ".xlsx", "WeChat Importer only supports .xlsx files"

        df = pd.read_excel(filename)
        df = df.dropna(thresh=10)  # Keep only lines with at least 5 non-NA values
        df = df.reset_index(drop=True)
        df.columns = df.iloc[0]  # Set the first filtered line as column headings
        df = df.drop(0)  # Drop the first filtered line which is now the header
        self.df = df

        # strips leading/trailing whitespace for each str column
        for col in self.df.columns:
            if self.df[col].dtype == "str":
                self.df[col] = self.df[col].str.strip()

        # replace all na with empty string
        self.df = self.df.fillna("")

        # replace 金额 column with Decimal
        self.df["金额(元)"] = self.df["金额(元)"].apply(
            lambda x: Decimal(x.strip("¥")) if x != "" else Decimal(0)
        )

    def parse(self):
        transactions = []
        for _, row in self.df.iterrows():
            meta = {}
            for key, value in header_mapping.items():
                if row[key] != "":
                    meta[value] = row[key]

            time = dateparser.parse(row["交易时间"])
            time = time.replace(tzinfo=datetime.timezone(datetime.timedelta(hours=8)))
            meta["source"] = "wechat"
            meta["datetime"] = time.isoformat()

            status = row["当前状态"]
            amount = row["金额(元)"]
            trade_type = row["收/支"]
            transaction_account = account_wechat_balance
            counterparty_account = account_unknown_expenses
            flags = "*"
            tags = []

            if row["商品"] == "亲属卡":
                tags.append("love-pay")

            if trade_type == "收入":
                if status in ["已存入零钱", "已收钱", "提现已到账"]:
                    pass
                elif status in ["已全额退款"] or "已退款" in status:
                    tags.append("refund")
                else:
                    raise ValueError(
                        f"Unknown status for income transaction: {status}, {row}"
                    )
            elif trade_type == "支出":
                if status in ["支付成功", "对方已收钱", "已转账", "充值成功"]:
                    pass
                elif status in ["交易关闭", "已全额退款"] or "已退款" in status:
                    tags.append("refund")
                else:
                    raise ValueError(
                        f"Unknown status for expense transaction: {status}, {row}"
                    )
            elif trade_type == "/":
                if status in ["支付成功", "提现已到账", "充值完成"]:
                    if row["交易类型"] in "零钱充值" or "购买" in row["交易类型"]:
                        trade_type = "收入"
                        counterparty_account = account_wechat_balance
                    elif (
                        row["交易类型"] == "零钱提现" or "转入零钱通" in row["交易类型"]
                    ):
                        trade_type = "支出"
                        counterparty_account = account_wechat_balance
                    else:
                        raise ValueError(f"Unknown trade type: {trade_type}, {row}")
                else:
                    raise ValueError(
                        f"Unknown status for unknown trade type transaction: {status}, {row}"
                    )
            else:
                raise ValueError(f"Unknown trade type: {trade_type}, {row}")

            entry = Transaction(
                data.new_metadata("unknown.beancount", 0, meta),
                date(time.year, time.month, time.day),
                flags,
                row["交易对方"],
                row["商品"],
                tags,
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
