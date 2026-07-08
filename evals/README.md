# Evaluation Suite

Historical validation of the analyzer against known ground truth — not a
trading backtest, but a correctness check of the three analysis stages.

## Checks

| # | Check | What it validates |
|---|-------|-------------------|
| a | `xbrl_accuracy` | Key figures extracted from XBRL company facts match officially reported values (±1% in live mode, exact in offline mode) |
| b | `risk_diff` | The year-over-year risk-factor diff detects risks that actually changed (spot-check assertions on known new/modified/removed risks) |
| c | `red_flags` | Red-flag detection fires on a historical problem case and stays quiet on healthy filings |

## Modes

### Offline (default, used in CI)

```bash
uv run python evals/run_evals.py
```

Runs the full assertion suite against bundled fixture filings:

- **HealthyCo** — a healthy large-cap modeled on Apple's FY2023/FY2022
  10-Ks (revenue $383,285M, net income $96,995M), with a known set of
  risk-factor changes (1 new, 1 modified, 1 unchanged, 1 removed).
- **ProblemCo** — the historical problem case, modeled on the public
  FY2020 disclosures of **Hertz Global Holdings** (Chapter 11 filing in
  May 2020, going-concern doubt, covenant breaches, revenue collapse from
  $9,779M to $5,258M). Expected flags: `going_concern`, `bankruptcy`,
  `covenant_breach`.

No network access is required, which is why CI runs this mode.

### Live

```bash
uv run python evals/run_evals.py --live
```

Downloads real 10-Ks from SEC EDGAR (requires `SEC_USER_AGENT` in `.env`
and outbound network access) and runs the same checks against five
well-known companies:

| Ticker | Fiscal year | Role | Expected (reported) |
|--------|-------------|------|---------------------|
| AAPL | FY2023 | healthy | revenue $383,285M, net income $96,995M |
| MSFT | FY2023 | healthy | revenue $211,915M, net income $72,361M |
| JNJ | FY2023 | healthy | revenue $85,159M, net income $35,153M |
| KO | FY2023 | healthy | revenue $45,754M, net income $10,714M |
| **HTZ** | **FY2020** | **problem case** | revenue $5,258M, net loss $(1,714)M, going-concern flag expected |

## Results

Committed results live in [`results/`](results/). The bundled
`results_offline.*` files were produced in a sandboxed environment without
EDGAR network access; run `--live` locally to regenerate live results.
