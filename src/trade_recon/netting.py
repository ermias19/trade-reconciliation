"""FX settlement netting.

Instead of paying and receiving every FX trade separately, trades with the
same counterparty, currency and value date are netted into one payment per
currency. This cuts the number of payments and settlement risk.
NDFs are excluded: they are cash-settled on the net difference, not by
exchanging the two currencies.
"""

from __future__ import annotations

import pandas as pd

FX_PRODUCTS = {"FX_SPOT", "FX_FORWARD"}


def net_fx_settlements(trades: pd.DataFrame) -> pd.DataFrame:
    fx = trades[trades["product"].isin(FX_PRODUCTS)]
    receive = fx[["counterparty", "settle_date", "buy_ccy", "buy_amount"]].rename(
        columns={"buy_ccy": "currency", "buy_amount": "amount"})
    pay = fx[["counterparty", "settle_date", "sell_ccy", "sell_amount"]].rename(
        columns={"sell_ccy": "currency", "sell_amount": "amount"})
    pay = pay.assign(amount=-pay["amount"])
    flows = pd.concat([receive, pay])
    gross = flows.groupby(["counterparty", "settle_date", "currency"]).size().rename("gross_flows")
    net = flows.groupby(["counterparty", "settle_date", "currency"])["amount"].sum().rename("net_amount")
    out = pd.concat([net, gross], axis=1).reset_index()
    out["direction"] = out["net_amount"].map(lambda x: "RECEIVE" if x > 0 else ("PAY" if x < 0 else "FLAT"))
    return out.sort_values(["settle_date", "counterparty", "currency"]).reset_index(drop=True)
