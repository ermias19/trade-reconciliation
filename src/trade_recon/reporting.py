"""Build a regulatory trade reporting extract for derivatives.

Under EMIR (EU/UK) and Dodd-Frank (US), derivative trades must be reported to
a trade repository. FX spot is not a derivative, so it is excluded. This
produces a simplified extract with the core fields a report needs and flags
products that may fall under a mandatory clearing obligation. It is a
learning tool, not a full regulatory schema.
"""

from __future__ import annotations

import hashlib

import pandas as pd

DERIVATIVES = {"FX_FORWARD", "NDF", "IRS", "CDS"}
CLEARING_CANDIDATES = {"IRS", "CDS"}


def make_uti(trade_id: str, trade_date: pd.Timestamp, reporter_lei: str) -> str:
    """A deterministic Unique Transaction Identifier: reporter LEI + hash."""
    digest = hashlib.sha1(f"{trade_id}|{trade_date.date()}".encode()).hexdigest()[:20].upper()
    return f"{reporter_lei}{digest}"


def regulatory_extract(trades: pd.DataFrame, reporter_lei: str, regimes=("EMIR", "DODD-FRANK")) -> pd.DataFrame:
    if len(reporter_lei) != 20:
        raise ValueError("An LEI is 20 characters long")
    deriv = trades[trades["product"].isin(DERIVATIVES)]
    rows = []
    for tid, t in deriv.iterrows():
        rows.append({
            "uti": make_uti(tid, t["trade_date"], reporter_lei),
            "trade_id": tid,
            "regimes": "/".join(regimes),
            "counterparty": t["counterparty"],
            "product": t["product"],
            "notional": t["buy_amount"],
            "notional_ccy": t["buy_ccy"],
            "trade_date": t["trade_date"].date(),
            "settle_or_maturity": t["settle_date"].date(),
            "clearing": "CHECK OBLIGATION" if t["product"] in CLEARING_CANDIDATES else "NOT REQUIRED",
        })
    return pd.DataFrame(rows)
