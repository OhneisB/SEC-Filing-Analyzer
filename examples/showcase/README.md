# Showcase reports

Committed example output so you can see exactly what the analyzer produces —
**without any API key, network access or live backend**. Regenerate with:

```bash
uv run python examples/generate_examples.py
```

These are produced offline (deterministic heuristics, no AI) from the bundled
fixture filings. The subjects are illustrative and modeled on real cases:

| Folder | Subject | Highlights |
|--------|---------|-----------|
| [`HEALTHYCO/`](HEALTHYCO/10-K_2023-09-30/report.md) | healthy large-cap (modeled on Apple FY2023) | clean report, XBRL financials, risk diff (1 new / 1 modified / 1 unchanged / 1 removed), **no red flags** |
| [`PROBLEMCO/`](PROBLEMCO/10-K_2020-12-31/report.md) | historical problem case (modeled on Hertz FY2020) | **red flags:** going concern, bankruptcy, covenant breach; revenue collapse in XBRL; new going-concern risk detected |

Each folder holds a `report.md` (human-readable) and `report.json` (structured
data). With an `ANTHROPIC_API_KEY` set, the summaries and risk-change notes are
richer, but the deterministic data shown here is always present.
