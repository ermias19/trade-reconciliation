"""Flag trades whose settlement is at risk.

A trade that settles late can trigger interest claims from the counterparty,
so anything settling soon that still has an open break needs attention first.
"""

from __future__ import annotations

import pandas as pd

from .reconcile import Break


def business_days_between(start: pd.Timestamp, end: pd.Timestamp) -> int:
    """Business days from start to end (weekends excluded, holidays ignored)."""
    if end < start:
        return -len(pd.bdate_range(end, start)) + 1
    return len(pd.bdate_range(start, end)) - 1


def settlement_risk(trades: pd.DataFrame, breaks: list[Break], as_of: str | pd.Timestamp,
                    horizon_days: int = 2) -> pd.DataFrame:
    """Trades settling within horizon_days business days that still have breaks,
    plus any trade already past its settlement date with a break."""
    as_of = pd.Timestamp(as_of)
    open_breaks: dict[str, list[str]] = {}
    for b in breaks:
        open_breaks.setdefault(b.trade_id, []).append(b.field or b.kind)

    rows = []
    for tid, fields in open_breaks.items():
        if tid not in trades.index:
            continue
        settle = trades.loc[tid, "settle_date"]
        days = business_days_between(as_of, settle)
        if days <= horizon_days:
            status = "OVERDUE" if days < 0 else "AT RISK"
            rows.append({"trade_id": tid, "counterparty": trades.loc[tid, "counterparty"],
                         "settle_date": settle.date(), "business_days_left": days,
                         "status": status, "open_breaks": ", ".join(fields)})
    cols = ["trade_id", "counterparty", "settle_date", "business_days_left", "status", "open_breaks"]
    return pd.DataFrame(rows, columns=cols).sort_values("business_days_left").reset_index(drop=True)
