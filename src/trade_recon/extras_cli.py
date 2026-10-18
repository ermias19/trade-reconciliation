"""Command line tools for hedges, corporate actions and regulatory reporting."""

from __future__ import annotations

import argparse

import pandas as pd

from .corporate_actions import entitlements, load_events
from .hedging import hedge_report, load_positions
from .io import load_trades
from .reporting import regulatory_extract


def _with_portfolio(trades_path: str) -> pd.DataFrame:
    trades = load_trades(trades_path)
    raw = pd.read_csv(trades_path, dtype={"trade_id": str}).set_index("trade_id")
    trades["portfolio"] = raw["portfolio"] if "portfolio" in raw else "DEFAULT"
    return trades


def hedges_main(argv=None) -> None:
    p = argparse.ArgumentParser(description="Check currency hedge ratios per portfolio")
    p.add_argument("positions")
    p.add_argument("trades")
    a = p.parse_args(argv)
    print(hedge_report(load_positions(a.positions), _with_portfolio(a.trades)).to_string(index=False))


def corp_actions_main(argv=None) -> None:
    p = argparse.ArgumentParser(description="Corporate action entitlements and election deadlines")
    p.add_argument("positions")
    p.add_argument("events")
    p.add_argument("--as-of", default=str(pd.Timestamp.today().date()))
    a = p.parse_args(argv)
    print(entitlements(load_positions(a.positions), load_events(a.events), a.as_of).to_string(index=False))


def reg_report_main(argv=None) -> None:
    p = argparse.ArgumentParser(description="EMIR / Dodd-Frank style derivatives reporting extract")
    p.add_argument("trades")
    p.add_argument("--lei", default="TESTLEI0000000000000", help="reporting firm's 20-character LEI (default is a dummy test value)")
    p.add_argument("--out")
    a = p.parse_args(argv)
    df = regulatory_extract(load_trades(a.trades), a.lei)
    print(df.to_string(index=False))
    if a.out:
        df.to_csv(a.out, index=False)
