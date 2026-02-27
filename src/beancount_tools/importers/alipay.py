import datetime
from datetime import date
from decimal import Decimal
from io import StringIO
from pathlib import Path
import re

import dateparser
import pandas as pd
from beancount.core import data
from beancount.core.data import Transaction

from .base import Base

header_mapping = {
    "交易分类": "category",
    "对方账号": "counterparty_ali_account",
    "收/付款方式": "transaction_ali_account",
    "交易订单号": "transaction_id",
    "商家订单号": "merchant_order_id",
    "备注": "note",
}

account_alipay_cash = "Assets:Digital:Alipay:Cash"
account_ant_fortune = "Assets:Trade:AntFortune"
account_unknown_expenses = "Expenses:Other"
account_unknown_income = "Income:Gift"
account_reimbursements = "Income:Reimbursements"


class AlipayImporter(Base):

    def __init__(self, filename):
        filename = Path(filename)
        assert filename.suffix == ".csv", "Alipay Importer only supports .csv files"

        with open(filename, "rb") as f:
            lines = f.readlines()
        # Filter out non-transaction lines (e.g., summary lines) by checking the number of commas
        try:
            transaction_lines = [x.decode("utf-8") for x in lines if x.count(b",") >= 6]
        except UnicodeDecodeError:
            transaction_lines = [x.decode("gbk") for x in lines if x.count(b",") >= 6]
        content = "".join(transaction_lines)
        self.content = content
        self.df = pd.read_csv(StringIO(content), skip_blank_lines=False)

        required_columns = [
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
        missing_columns = [c for c in required_columns if c not in self.df.columns]
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

    def parse(self):
        transactions = []
        for _, row in self.df.iterrows():
            meta = {}
            for key, value in header_mapping.items():
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

            transaction_account = account_alipay_cash
            counterparty_account = account_unknown_expenses
            flags = "*"
            tags = []
            skip_entry = False

            if row["商品说明"] == "亲情卡":
                tags.append("love-pay")

            if trade_type == "支出":
                counterparty_account = account_unknown_expenses
                if status in ["交易成功", "支付成功"]:
                    pass
                elif status == "交易关闭":
                    pass
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
                    counterparty_account = account_unknown_expenses

                elif status == "交易成功":
                    if "蚂蚁财富" in row["交易对方"]:
                        counterparty_account = account_ant_fortune
                    if "买入" in row["商品说明"] or "转入" in row["商品说明"]:
                        trade_type = "支出"
                        if counterparty_account != account_ant_fortune:
                            counterparty_account = account_unknown_expenses
                    elif (
                        "卖出" in row["商品说明"]
                        or "赎回" in row["商品说明"]
                        or "转出" in row["商品说明"]
                    ):
                        trade_type = "收入"
                        if counterparty_account != account_ant_fortune:
                            counterparty_account = account_unknown_income
                    elif "因公付" in my_ali_account:
                        trade_type = "支出"
                        counterparty_account = account_unknown_expenses
                        transaction_account = account_reimbursements
                        if "&" in my_ali_account:
                            tags.append("need-review")
                    elif "充值-普通充值" in row["商品说明"]:
                        trade_type = "支出"
                        counterparty_account = account_unknown_expenses
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
                counterparty_account = account_unknown_income
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
