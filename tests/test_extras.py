import pandas as pd
import pytest

from trade_recon.corporate_actions import entitlements
from trade_recon.hedging import hedge_report
from trade_recon.io import validate
from trade_recon.reporting import make_uti, regulatory_extract

COLS = ["trade_id", "trade_date", "settle_date", "counterparty", "product",
        "side", "buy_ccy", "buy_amount", "sell_ccy", "sell_amount"]


def trades(rows):
    return validate(pd.DataFrame(rows, columns=COLS))


def test_hedge_ratio_flags_under_and_over_hedged():
    positions = pd.DataFrame({"portfolio": ["P", "P", "P"], "currency": ["BRL", "MXN", "USD"],
                              "market_value": [1000.0, 1000.0, 500.0]})
    hedges = trades([
        ["H1", "2026-10-01", "2026-12-17", "B", "NDF", "SELL", "USD", 1, "BRL", 500],
        ["H2", "2026-10-01", "2026-12-17", "B", "FX_FORWARD", "SELL", "USD", 1, "MXN", 1000],
        ["H3", "2026-10-01", "2026-10-03", "B", "FX_SPOT", "SELL", "USD", 1, "MXN", 999],
    ])
    hedges["portfolio"] = "P"
    out = hedge_report(positions, hedges).set_index("currency")
    assert "USD" not in out.index
    assert out.loc["BRL", "status"] == "UNDER-HEDGED"
    assert out.loc["MXN", "hedge_ratio"] == pytest.approx(1.0)  # FX spot is not a hedge
    assert out.loc["MXN", "status"] == "OK"


def test_corporate_action_entitlements_and_deadlines():
    positions = pd.DataFrame({"portfolio": ["P", "P"], "security": ["A", "B"], "quantity": [100, 50]})
    events = pd.DataFrame({
        "security": ["A", "B", "B", "C"],
        "event_type": ["DIVIDEND", "TENDER", "SPLIT", "DIVIDEND"],
        "ex_date": pd.to_datetime(["2026-10-20"] * 4),
        "pay_date": pd.to_datetime(["2026-11-05"] * 4),
        "election_deadline": pd.to_datetime([None, "2026-10-22", None, None]),
        "rate": [1.5, 10.0, 2.0, 1.0],
    })
    out = entitlements(positions, events, as_of="2026-10-18")
    assert "C" not in set(out["security"])  # not held
    tender = out[out["event_type"] == "TENDER"].iloc[0]
    assert tender["action"] == "ELECTION DUE"
    assert out[out["event_type"] == "DIVIDEND"].iloc[0]["entitlement"] == "cash 150.00"
    assert out[out["event_type"] == "SPLIT"].iloc[0]["entitlement"] == "+50 shares"


def test_regulatory_extract_reports_derivatives_only():
    t = trades([
        ["T1", "2026-10-14", "2026-10-16", "B", "FX_SPOT", "BUY", "USD", 1, "BRL", 5],
        ["T2", "2026-10-14", "2031-10-14", "B", "IRS", "BUY", "USD", 1e7, "USD", 1e7],
        ["T3", "2026-10-14", "2026-11-17", "B", "NDF", "BUY", "USD", 2e6, "INR", 1.6e8],
    ])
    lei = "TESTLEI0000000000000"
    out = regulatory_extract(t, lei).set_index("trade_id")
    assert list(out.index) == ["T2", "T3"]
    assert out.loc["T2", "clearing"] == "CHECK OBLIGATION"
    assert out.loc["T3", "clearing"] == "NOT REQUIRED"
    assert out.loc["T2", "uti"].startswith(lei)
    assert out.loc["T2", "uti"] == make_uti("T2", pd.Timestamp("2026-10-14"), lei)
    with pytest.raises(ValueError):
        regulatory_extract(t, "SHORT")
