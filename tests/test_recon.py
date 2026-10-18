import pandas as pd
import pytest

from trade_recon import net_fx_settlements, reconcile, settlement_risk
from trade_recon.io import validate
from trade_recon.settlement import business_days_between


def trades(rows):
    cols = ["trade_id", "trade_date", "settle_date", "counterparty", "product",
            "side", "buy_ccy", "buy_amount", "sell_ccy", "sell_amount"]
    return validate(pd.DataFrame(rows, columns=cols))


BASE = ["T1", "2026-10-14", "2026-10-16", "BANK_A", "FX_SPOT", "BUY", "USD", 1_000_000, "BRL", 5_450_000]


def test_identical_files_have_no_breaks():
    assert reconcile(trades([BASE]), trades([BASE])) == []


def test_missing_trades_on_either_side():
    other = ["T2"] + BASE[1:]
    breaks = reconcile(trades([BASE]), trades([other]))
    kinds = {(b.trade_id, b.kind) for b in breaks}
    assert kinds == {("T1", "MISSING_IN_CONFIRMATION"), ("T2", "MISSING_IN_BLOTTER")}


def test_amount_and_date_mismatches_are_reported_but_rounding_is_ignored():
    theirs = BASE.copy()
    theirs[2] = "2026-10-19"
    theirs[9] = 5_450_000.004
    breaks = reconcile(trades([BASE]), trades([theirs]))
    assert [(b.field, b.kind) for b in breaks] == [("settle_date", "FIELD_MISMATCH")]


def test_counterparty_compare_ignores_case_and_spaces():
    theirs = BASE.copy()
    theirs[3] = " bank_a "
    assert reconcile(trades([BASE]), trades([theirs])) == []


def test_fx_netting_combines_flows_and_excludes_ndf():
    rows = [
        BASE,
        ["T2", "2026-10-14", "2026-10-16", "BANK_A", "FX_SPOT", "SELL", "BRL", 2_725_000, "USD", 500_000],
        ["T3", "2026-10-14", "2026-10-16", "BANK_A", "NDF", "BUY", "USD", 1_000_000, "BRL", 5_450_000],
    ]
    net = net_fx_settlements(trades(rows)).set_index("currency")
    assert net.loc["USD", "net_amount"] == 500_000
    assert net.loc["USD", "direction"] == "RECEIVE"
    assert net.loc["BRL", "net_amount"] == -2_725_000
    assert net.loc["BRL", "gross_flows"] == 2


def test_settlement_risk_flags_breaks_settling_soon_or_overdue():
    soon = BASE.copy()
    late = ["T2", "2026-10-01", "2026-10-05", "BANK_B", "FX_SPOT", "BUY", "USD", 1, "MXN", 18]
    later = ["T3", "2026-10-15", "2026-11-17", "BANK_C", "NDF", "BUY", "USD", 1, "INR", 84]
    ours = trades([soon, late, later])
    theirs_rows = [s.copy() for s in (soon, late, later)]
    for r in theirs_rows:
        r[7] = r[7] + 10  # every trade has an amount break
    breaks = reconcile(ours, trades(theirs_rows))
    risk = settlement_risk(ours, breaks, as_of="2026-10-15").set_index("trade_id")
    assert risk.loc["T2", "status"] == "OVERDUE"
    assert risk.loc["T1", "status"] == "AT RISK"
    assert "T3" not in risk.index


def test_business_days_skip_weekends():
    assert business_days_between(pd.Timestamp("2026-10-16"), pd.Timestamp("2026-10-19")) == 1


def test_validation_rejects_duplicates_and_unknown_products():
    with pytest.raises(ValueError):
        trades([BASE, BASE])
    bad = BASE.copy()
    bad[4] = "SWAPTION"
    with pytest.raises(ValueError):
        trades([bad])
