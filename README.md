# Trade Reconciliation & Settlement Monitor

A Python tool for the daily post-trade checks a trading assistant runs. It reconciles the desk's trades against custodian or counterparty confirmations, flags every discrepancy, highlights settlements at risk of failing, and nets FX settlements by counterparty, currency and value date.

```
$ recon sample_data/blotter.csv sample_data/confirmations.csv --as-of 2026-10-16

Reconciliation as of 2026-10-16: 8 trades, 4 breaks

trade_id                    kind       field        ours      theirs
    T007 MISSING_IN_CONFIRMATION           -     present        None
    T009      MISSING_IN_BLOTTER           -        None     present
    T003          FIELD_MISMATCH sell_amount  13612500.0  13621500.0
    T005          FIELD_MISMATCH settle_date  2026-10-20  2026-10-21

Settlements at risk (open breaks settling within 2 business days):
trade_id counterparty settle_date  business_days_left  status open_breaks
    T003       BANK_B  2026-10-19                   1 AT RISK sell_amount
    T005       BANK_B  2026-10-20                   2 AT RISK settle_date

Netted FX settlements:
counterparty settle_date currency  net_amount  gross_flows direction
      BANK_A  2026-10-16      BRL  -2725000.0            2       PAY
      BANK_A  2026-10-16      USD    500000.0            2   RECEIVE
      ...
```

The sample data is made up. It uses emerging-markets currencies (BRL, MXN, ZAR, INR, COP) and includes FX spot, NDF, IRS and CDS trades.

## Run it

```bash
pip install -e ".[dev]"
recon sample_data/blotter.csv sample_data/confirmations.csv --as-of 2026-10-16 --out breaks.csv
pytest -q
```

## How it works (interview walkthrough)

**1. Loading and validation (`io.py`).** Both files share the same columns: trade ID, trade date, settlement date, counterparty, product, side, and the two currencies and amounts. The loader rejects duplicate trade IDs, unknown products and unknown sides before anything is compared. A bad input file should fail loudly, not produce a silent wrong answer.

**2. Reconciliation (`reconcile.py`).** Trades are matched by trade ID, and three kinds of break are reported:
- **Missing in confirmation:** we booked it, but the custodian or counterparty has no record of it (T007 in the sample). Chase the counterparty.
- **Missing in blotter:** they have a trade we didn't book (T009). Check with the trader before it settles.
- **Field mismatch:** both sides have the trade, but a field differs (T003's amount, T005's settlement date).

Amounts are compared with a small tolerance so rounding differences don't create false breaks. Counterparty names are compared ignoring case and spaces.

**3. Settlement risk (`settlement.py`).** Any trade with an open break that settles within 2 business days, or is already past its settlement date, is flagged as AT RISK or OVERDUE. Weekends are skipped. Late settlement can lead to interest claims from the counterparty, so these breaks get fixed first.

**4. FX netting (`netting.py`).** FX spot and forward trades with the same counterparty, currency and value date are combined into one net payment per currency. In the sample, BANK_A's two trades on 16 Oct become one USD receipt and one BRL payment instead of four flows. NDFs are excluded because they are cash-settled on the difference between the contract rate and the fixing rate, with no exchange of the restricted currency.

## Glossary

| Term | Meaning |
|---|---|
| Blotter | The desk's own record of the trades it executed |
| Custodian | The bank that holds the fund's assets and settles its trades |
| Counterparty | The bank or broker on the other side of the trade |
| Confirmation | The counterparty's record of the trade, which must match ours |
| Break | Any difference between our record and theirs |
| Settlement date | When cash and assets actually change hands (usually T+2 for FX spot) |
| Netting | Combining many payments into one net payment per currency |
| NDF | Non-deliverable forward: an FX forward on a restricted currency (e.g. INR, BRL), settled in USD on the net difference |
| IRS | Interest rate swap: exchanging fixed for floating interest payments |
| CDS | Credit default swap: insurance against a borrower defaulting |
| EMIR / Dodd-Frank | EU/UK and US rules requiring derivative trades to be reported and, where eligible, cleared |

## Limitations and next steps

- Matching is on trade ID only. Real counterparties often use their own references, so the next step is fuzzy matching on economics (date, amounts, currencies).
- Holidays are ignored. Settlement dates should use each currency's holiday calendar.
- Possible extensions: corporate actions tracking, and an EMIR-style trade reporting extract.
