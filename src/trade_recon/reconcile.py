"""Match our trades against a confirmation file and report every break."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

# Fields compared on every matched trade, and how they are compared.
TEXT_FIELDS = ["counterparty", "product", "side", "buy_ccy", "sell_ccy"]
DATE_FIELDS = ["trade_date", "settle_date"]
AMOUNT_FIELDS = ["buy_amount", "sell_amount"]


@dataclass(frozen=True)
class Break:
    trade_id: str
    kind: str          # MISSING_IN_CONFIRMATION, MISSING_IN_BLOTTER or FIELD_MISMATCH
    field: str | None
    ours: object
    theirs: object

    def as_dict(self) -> dict:
        return {"trade_id": self.trade_id, "kind": self.kind, "field": self.field,
                "ours": self.ours, "theirs": self.theirs}


def reconcile(ours: pd.DataFrame, theirs: pd.DataFrame, amount_tolerance: float = 0.01) -> list[Break]:
    """Compare two validated trade tables indexed by trade_id.

    amount_tolerance is an absolute difference allowed on amounts, to ignore
    rounding (e.g. 0.01 for cents).
    """
    breaks: list[Break] = []
    for tid in sorted(ours.index.difference(theirs.index)):
        breaks.append(Break(tid, "MISSING_IN_CONFIRMATION", None, "present", None))
    for tid in sorted(theirs.index.difference(ours.index)):
        breaks.append(Break(tid, "MISSING_IN_BLOTTER", None, None, "present"))

    for tid in sorted(ours.index.intersection(theirs.index)):
        a, b = ours.loc[tid], theirs.loc[tid]
        for field in TEXT_FIELDS:
            if str(a[field]).strip().upper() != str(b[field]).strip().upper():
                breaks.append(Break(tid, "FIELD_MISMATCH", field, a[field], b[field]))
        for field in DATE_FIELDS:
            if a[field] != b[field]:
                breaks.append(Break(tid, "FIELD_MISMATCH", field, a[field].date(), b[field].date()))
        for field in AMOUNT_FIELDS:
            if abs(a[field] - b[field]) > amount_tolerance:
                breaks.append(Break(tid, "FIELD_MISMATCH", field, a[field], b[field]))
    return breaks


def breaks_table(breaks: list[Break]) -> pd.DataFrame:
    return pd.DataFrame([b.as_dict() for b in breaks],
                        columns=["trade_id", "kind", "field", "ours", "theirs"])
