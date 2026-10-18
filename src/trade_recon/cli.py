"""Run the daily post-trade check and print a report."""

from __future__ import annotations

import argparse

import pandas as pd

from .io import load_trades
from .netting import net_fx_settlements
from .reconcile import breaks_table, reconcile
from .settlement import settlement_risk


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Reconcile trades and monitor settlement")
    parser.add_argument("blotter", help="our trades (CSV)")
    parser.add_argument("confirmations", help="custodian or counterparty confirmations (CSV)")
    parser.add_argument("--as-of", default=str(pd.Timestamp.today().date()), help="report date, YYYY-MM-DD")
    parser.add_argument("--out", help="write breaks to this CSV file")
    args = parser.parse_args(argv)

    ours, theirs = load_trades(args.blotter), load_trades(args.confirmations)
    breaks = reconcile(ours, theirs)
    table = breaks_table(breaks)

    pd.set_option("display.width", 140)
    print(f"Reconciliation as of {args.as_of}: {len(ours)} trades, {len(breaks)} breaks\n")
    print(table.fillna("-").to_string(index=False) if len(table) else "No breaks.")
    print("\nSettlements at risk (open breaks settling within 2 business days):")
    risk = settlement_risk(ours, breaks, args.as_of)
    print(risk.to_string(index=False) if len(risk) else "None.")
    print("\nNetted FX settlements:")
    print(net_fx_settlements(ours).to_string(index=False))
    if args.out:
        table.to_csv(args.out, index=False)


if __name__ == "__main__":
    main()
