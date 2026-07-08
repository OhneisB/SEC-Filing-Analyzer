# Evaluation Results (offline mode)

- Run: 2026-07-08T14:16:34+00:00
- Checks: 13, failures: 0
- Overall: ✅ PASSED

| Check | Subject | Result | Detail |
|---|---|---|---|
| xbrl_accuracy | HealthyCo FY2023 revenue | ✅ | expected 383,285,000,000, got 383,285,000,000 |
| xbrl_accuracy | HealthyCo FY2023 net_income | ✅ | expected 96,995,000,000, got 96,995,000,000 |
| xbrl_accuracy | HealthyCo FY2023 total_assets | ✅ | expected 352,583,000,000, got 352,583,000,000 |
| xbrl_accuracy | ProblemCo FY2020 revenue | ✅ | expected 5,258,000,000, got 5,258,000,000 |
| xbrl_accuracy | ProblemCo FY2020 net_income | ✅ | expected -1,714,000,000, got -1,714,000,000 |
| risk_diff | HealthyCo 2023 vs 2022 counts | ✅ | got {'new': 1, 'modified': 1, 'unchanged': 1, 'removed': 1} |
| risk_diff | HealthyCo new AI-regulation risk detected | ✅ | Evolving regulation of artificial intelligence may impose new obligations on our products. Governmen |
| risk_diff | HealthyCo modified cybersecurity risk detected | ✅ | Cybersecurity incidents could disrupt our operations and harm our reputation. The Company experience |
| risk_diff | ProblemCo new going-concern risk detected as NEW | ✅ | 2 new risks |
| red_flags | ProblemCo FY2020 raises going_concern | ✅ | flags found: ['bankruptcy', 'covenant_breach', 'going_concern'] |
| red_flags | ProblemCo FY2020 raises bankruptcy | ✅ | flags found: ['bankruptcy', 'covenant_breach', 'going_concern'] |
| red_flags | ProblemCo FY2020 raises covenant_breach | ✅ | flags found: ['bankruptcy', 'covenant_breach', 'going_concern'] |
| red_flags | HealthyCo FY2023 raises no flags | ✅ | flags found: [] |

_Offline mode validates the full assertion suite against bundled fixture
filings (the problem case is modeled on Hertz Global Holdings' FY2020
disclosures). Run with `--live` for the same checks against real EDGAR
filings of AAPL, MSFT, JNJ, KO and HTZ._
