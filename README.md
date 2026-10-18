# Trade Reconciliation & Settlement Monitor

A Python toolkit for the daily checks a trading assistant runs:

- **Reconciliation:** compares the desk's trades against custodian or counterparty confirmations and flags every discrepancy.
- **Settlement monitoring:** highlights settlements at risk of failing.
- **FX netting:** nets FX settlements by counterparty, currency and value date.
- **Hedge tracking:** checks each portfolio's currency hedges.
- **Corporate actions:** monitors corporate actions and election deadlines.
- **Regulatory reporting:** builds an EMIR / Dodd-Frank style reporting extract for derivatives.

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
hedge-check sample_data/positions.csv sample_data/hedges.csv
corp-actions sample_data/positions.csv sample_data/corporate_actions.csv --as-of 2026-10-18
reg-report sample_data/blotter.csv --out emir_extract.csv
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


**5. Currency hedge tracking (`hedging.py`).** An emerging-markets portfolio holding Brazilian or Mexican stocks is exposed to BRL and MXN. Selling those currencies forward (FX forwards, or NDFs for restricted currencies) hedges that exposure. For each portfolio and currency, the tool divides the hedged amount by the exposure. Anything outside 95–105% is flagged as UNDER-HEDGED or OVER-HEDGED for the portfolio manager. In the sample, EM_EQUITY's MXN is only 67% hedged and its ZAR is 112% hedged. FX spot trades are not counted as hedges.

```
portfolio currency  exposure     hedged  hedge_ratio       status
EM_EQUITY      MXN   8250000  5500000.0     0.666667 UNDER-HEDGED
EM_EQUITY      ZAR  16500000 18500000.0     1.121212  OVER-HEDGED
```

**6. Corporate actions (`corporate_actions.py`).** For every event on a security the fund holds, the tool works out the entitlement: cash for a dividend, extra shares for a split. *Mandatory* events (dividends, splits) just happen. *Voluntary* events (tender offers, rights issues) need the portfolio manager to choose, and missing the election deadline means losing the choice. Elections due within 10 days are listed first.

```
 security event_type election_deadline  quantity                     entitlement       action
WALMEX MM     TENDER        2026-10-22    150000 elect on 150,000 shares at 58.0 ELECTION DUE
 PETR4 BZ   DIVIDEND               NaT    200000                 cash 250,000.00         INFO
```

**7. Regulatory reporting extract (`reporting.py`).** Under EMIR (EU and UK) and Dodd-Frank (US), derivative trades must be reported to a trade repository. FX spot is not a derivative, so it's excluded. Each reportable trade gets a Unique Transaction Identifier (UTI), built here from the reporting firm's Legal Entity Identifier (LEI) plus a hash, together with notional, dates and counterparty. IRS and CDS are flagged "CHECK OBLIGATION" because some of them must be centrally cleared. This is a simplified learning version, not the full regulatory schema. The default LEI is a dummy test value.

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
| UTI / LEI | Unique Transaction Identifier for each reported trade / Legal Entity Identifier for each firm |
| Hedge ratio | Hedged amount ÷ exposure; 100% means fully hedged |
| Corporate action | An event decided by a company that affects its shareholders: dividend, split, tender offer, rights issue |
| Election | The choice a holder makes on a voluntary corporate action, by a deadline |

## Limitations and next steps

- Matching is on trade ID only. Real counterparties often use their own references, so the next step is fuzzy matching on economics (date, amounts, currencies).
- Holidays are ignored. Settlement dates should use each currency's holiday calendar.
- Hedge targets are a fixed band. In practice each portfolio has its own hedging policy.
- The reporting extract has core fields only. A real EMIR report has over 200 fields.
