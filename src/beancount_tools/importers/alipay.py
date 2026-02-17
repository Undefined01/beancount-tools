import datetime
from datetime import date
from decimal import Decimal
from io import StringIO
from pathlib import Path

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

account_alipay_balance = "Assets:Digital:Alipay:Balance"
account_ant_wealth = "Assets:Trade:AntWealth"
account_unknown_expenses = "Expenses:Unknown"


class AlipayImporter(Base):

    def __init__(self, filename):
        filename = Path(filename)
        assert filename.suffix == ".csv", "Alipay Importer only supports .csv files"

        with open(filename, "rb") as f:
            lines = f.readlines()
        # Filter out non-transaction lines (e.g., summary lines) by checking the number of commas
        transaction_lines = [x.decode("gbk") for x in lines if x.count(b",") >= 6]
        content = "".join(transaction_lines)
        self.content = content
        self.df = pd.read_csv(StringIO(content), skip_blank_lines=False)

        # strips leading/trailing whitespace for each str column
        for col in self.df.columns:
            if self.df[col].dtype == "str":
                self.df[col] = self.df[col].str.strip()

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
            transaction_account = account_alipay_balance
            counterparty_account = account_unknown_expenses
            flags = "*"
            tags = []

            if row["商品说明"] == "亲情卡":
                tags.append("love-pay")
            if trade_type == "支出" or trade_type == "":
                if status in [
                    "交易成功",
                    "支付成功",
                    "代付成功",
                    "亲情卡付款成功",
                    "等待确认收货",
                    "等待对方发货",
                    "充值成功",
                ]:
                    pass
                elif status == "交易关闭":
                    pass
                else:
                    raise ValueError(f"Unknown status for 支出: {status}")
            elif trade_type == "不计收支":
                if "退款" in row["交易分类"]:
                    assert "退款" in status
                    assert "退款" in row["商品说明"]
                    tags.append("refund")
                    trade_type = "收入"

                elif status in ["交易成功", "收款成功"]:
                    if "蚂蚁财富" in row["交易对方"]:
                        counterparty_account = account_ant_wealth
                    if "买入" in row["商品说明"] or "转入" in row["商品说明"]:
                        trade_type = "支出"
                    elif (
                        "卖出" in row["商品说明"]
                        or "赎回" in row["商品说明"]
                        or "转出" in row["商品说明"]
                    ):
                        trade_type = "收入"
                    elif "因公付" in my_ali_account:
                        trade_type = "支出"
                        meta["original_amount"] = str(amount)
                        amount = 0
                    elif "充值-普通充值" in row["商品说明"]:
                        trade_type = "支出"
                        flags = "!"
                    else:
                        raise ValueError(f"Unknown case for 不计收支: {row}")

                elif status in ["提取成功", "还款成功"]:
                    trade_type = "支出"
                elif status == "交易关闭" and my_ali_account == "":
                    trade_type = "支出"
                elif status == "芝麻免押下单成功":
                    trade_type = "支出"
                    flags = "!"
                elif status == "解冻成功":
                    trade_type = "收入"
                    flags = "!"
                else:
                    raise ValueError(f"Unknown case for 不计收支: {row}")

            elif trade_type == "收入":
                if status in ["交易成功", "收款成功", "退款成功"]:
                    pass
                elif status in ["等待对方确认收货", "交易关闭"]:
                    pass
                else:
                    raise ValueError(f"Unknown status for 收入: {status}")
            else:
                raise ValueError(f"Unknown trade type: {trade_type}")

            entry = Transaction(
                data.new_metadata("unknown.beancount", 0, meta),
                date(time.year, time.month, time.day),
                flags,
                row["交易对方"],
                row["商品说明"],
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
