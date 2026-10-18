"""Monitor corporate actions on portfolio positions.

For each event on a security we hold, work out the entitlement (cash for a
dividend, new shares for a split) and flag voluntary events, such as tenders
or rights issues, whose election deadline is coming up, so portfolio managers
can decide in time.
"""

from __future__ import annotations

import pandas as pd

MANDATORY = {"DIVIDEND", "SPLIT"}
VOLUNTARY = {"TENDER", "RIGHTS", "DIVIDEND_OPTION"}


def load_events(path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["ex_date", "pay_date", "election_deadline"])
    unknown = set(df["event_type"]) - MANDATORY - VOLUNTARY
    if unknown:
        raise ValueError(f"Unknown event types: {sorted(unknown)}")
    return df


def entitlements(positions: pd.DataFrame, events: pd.DataFrame, as_of, horizon_days: int = 10) -> pd.DataFrame:
    """events: security, event_type, ex_date, pay_date, election_deadline, rate.
    rate is cash per share for dividends, new shares per old share for splits,
    and the offer price for tenders and rights."""
    as_of = pd.Timestamp(as_of)
    held = positions.groupby(["portfolio", "security"])["quantity"].sum().reset_index()
    df = events.merge(held, on="security", how="inner")
    df["entitlement"] = df.apply(_entitlement, axis=1)
    df["needs_election"] = df["event_type"].isin(VOLUNTARY)
    days_left = (df["election_deadline"] - as_of).dt.days
    df["action"] = "INFO"
    df.loc[df["needs_election"] & (days_left <= horizon_days), "action"] = "ELECTION DUE"
    df.loc[df["needs_election"] & (days_left < 0), "action"] = "DEADLINE MISSED"
    cols = ["portfolio", "security", "event_type", "ex_date", "pay_date",
            "election_deadline", "quantity", "entitlement", "action"]
    priority = df["action"].map({"DEADLINE MISSED": 0, "ELECTION DUE": 1, "INFO": 2})
    return df.assign(_p=priority).sort_values(["_p", "election_deadline", "ex_date"])[cols].reset_index(drop=True)


def _entitlement(row) -> str:
    if row["event_type"] == "DIVIDEND":
        return f"cash {row['quantity'] * row['rate']:,.2f}"
    if row["event_type"] == "SPLIT":
        return f"+{row['quantity'] * (row['rate'] - 1):,.0f} shares"
    return f"elect on {row['quantity']:,.0f} shares at {row['rate']}"
