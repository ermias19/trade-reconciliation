"""Load and validate trade files.

Both the internal blotter and the custodian/counterparty confirmations use
the same columns, so they can be compared field by field.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

COLUMNS = [
    "trade_id", "trade_date", "settle_date", "counterparty", "product",
    "side", "buy_ccy", "buy_amount", "sell_ccy", "sell_amount",
]
PRODUCTS = {"FX_SPOT", "FX_FORWARD", "NDF", "IRS", "CDS", "EQUITY", "BOND"}
SIDES = {"BUY", "SELL"}


def load_trades(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"trade_id": str})
    return validate(df)


def validate(df: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    df = df[COLUMNS].copy()
    if df["trade_id"].duplicated().any():
        dupes = sorted(df.loc[df["trade_id"].duplicated(), "trade_id"].unique())
        raise ValueError(f"Duplicate trade_id values: {dupes}")
    bad_products = set(df["product"]) - PRODUCTS
    if bad_products:
        raise ValueError(f"Unknown products: {sorted(bad_products)}")
    bad_sides = set(df["side"]) - SIDES
    if bad_sides:
        raise ValueError(f"Unknown sides: {sorted(bad_sides)}")
    for col in ("trade_date", "settle_date"):
        df[col] = pd.to_datetime(df[col])
    for col in ("buy_amount", "sell_amount"):
        df[col] = df[col].astype(float)
    return df.set_index("trade_id")
