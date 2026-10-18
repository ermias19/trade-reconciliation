"""Track currency hedges for each portfolio.

A portfolio holding emerging-markets assets is exposed to those currencies.
FX forwards and NDFs that sell the currency forward hedge that exposure.
The hedge ratio is hedged amount / exposure; outside the target band the
position is flagged for the portfolio manager.
"""

from __future__ import annotations

import pandas as pd

HEDGE_PRODUCTS = {"FX_FORWARD", "NDF"}


def load_positions(path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = {"portfolio", "security", "currency", "quantity", "market_value"} - set(df.columns)
    if missing:
        raise ValueError(f"Positions file is missing columns: {sorted(missing)}")
    return df


def hedge_report(positions: pd.DataFrame, hedges: pd.DataFrame, base_ccy: str = "USD",
                 target: float = 1.0, tolerance: float = 0.05) -> pd.DataFrame:
    """positions: portfolio, currency, market_value (in that currency).
    hedges: trades with a 'portfolio' column; selling a currency forward hedges it."""
    exposure = (positions[positions["currency"] != base_ccy]
                .groupby(["portfolio", "currency"])["market_value"].sum().rename("exposure"))
    fwd = hedges[hedges["product"].isin(HEDGE_PRODUCTS)]
    hedged = fwd.groupby(["portfolio", "sell_ccy"])["sell_amount"].sum()
    hedged.index = hedged.index.set_names(["portfolio", "currency"])
    out = pd.concat([exposure, hedged.rename("hedged")], axis=1).fillna(0.0).reset_index()
    out["hedge_ratio"] = out.apply(
        lambda r: r["hedged"] / r["exposure"] if r["exposure"] else float("inf"), axis=1)

    def status(ratio: float) -> str:
        if ratio < target - tolerance:
            return "UNDER-HEDGED"
        if ratio > target + tolerance:
            return "OVER-HEDGED"
        return "OK"

    out["status"] = out["hedge_ratio"].map(status)
    return out.sort_values(["portfolio", "currency"]).reset_index(drop=True)
