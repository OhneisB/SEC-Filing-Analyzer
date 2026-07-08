#!/usr/bin/env python3
"""Historical validation harness for sec-filing-analyzer.

Two modes:

- ``--offline`` (default): runs the full assertion suite against bundled
  fixture filings — a healthy company and a problem case modeled on the
  FY2020 disclosures of Hertz Global Holdings (Chapter 11, going-concern
  doubt, covenant breaches). No network access required; used in CI.

- ``--live``: downloads real 10-Ks of five well-known companies from SEC
  EDGAR (AAPL, MSFT, JNJ, KO and the historical problem case HTZ) and runs
  the same three checks against them:
    (a) XBRL key figures match officially reported values (±1%),
    (b) the risk-factor diff detects year-over-year changes,
    (c) red-flag detection fires on the problem case (HTZ FY2020) and
        stays quiet on healthy filings.

Results are written to evals/results/ as JSON and Markdown.

Usage:
    uv run python evals/run_evals.py [--live] [--out evals/results]
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sec_filing_analyzer.analysis.diff import diff_risk_factors, summarize_changes
from sec_filing_analyzer.analysis.redflags import detect_red_flags
from sec_filing_analyzer.models import Company, FilingRef, ParsedFiling
from sec_filing_analyzer.parsing.sections import extract_sections
from sec_filing_analyzer.parsing.xbrl import extract_key_financials

EVALS_DIR = Path(__file__).resolve().parent
FIXTURES = EVALS_DIR / "fixtures"

# Officially reported figures (10-K / press releases) used in live mode.
# tolerance: 1% relative deviation allowed for concept-mapping differences.
LIVE_COMPANIES = [
    {
        "ticker": "AAPL", "name": "Apple Inc.", "fiscal_year": 2023, "problem_case": False,
        "expected": {"revenue": 383_285_000_000, "net_income": 96_995_000_000},
    },
    {
        "ticker": "MSFT", "name": "Microsoft Corp.", "fiscal_year": 2023, "problem_case": False,
        "expected": {"revenue": 211_915_000_000, "net_income": 72_361_000_000},
    },
    {
        "ticker": "JNJ", "name": "Johnson & Johnson", "fiscal_year": 2023, "problem_case": False,
        "expected": {"revenue": 85_159_000_000, "net_income": 35_153_000_000},
    },
    {
        "ticker": "KO", "name": "Coca-Cola Co.", "fiscal_year": 2023, "problem_case": False,
        "expected": {"revenue": 45_754_000_000, "net_income": 10_714_000_000},
    },
    {
        # Historical problem case: Chapter 11 May 2020, going-concern doubt
        # in the FY2020 10-K (filed 2021-02-26).
        "ticker": "HTZ", "name": "Hertz Global Holdings", "fiscal_year": 2020, "problem_case": True,
        "expected": {"revenue": 5_258_000_000, "net_income": -1_714_000_000},
    },
]

TOLERANCE = 0.01


@dataclass
class EvalResult:
    check: str
    subject: str
    passed: bool
    detail: str


@dataclass
class EvalReport:
    mode: str
    results: list[EvalResult] = field(default_factory=list)

    def add(self, check: str, subject: str, passed: bool, detail: str) -> None:
        self.results.append(EvalResult(check, subject, passed, detail))
        icon = "PASS" if passed else "FAIL"
        print(f"[{icon}] {check} / {subject}: {detail}")

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)


def _within_tolerance(actual: float | None, expected: float) -> bool:
    if actual is None:
        return False
    return abs(actual - expected) <= abs(expected) * TOLERANCE


def _make_ref(ticker: str, name: str, form: str, report_date: str) -> FilingRef:
    return FilingRef(
        company=Company(ticker=ticker, cik=0, name=name),
        form=form,
        accession_number="fixture",
        filing_date=report_date,
        report_date=report_date,
        primary_document="fixture.htm",
    )


# --------------------------------------------------------------------- offline

def run_offline(report: EvalReport) -> None:
    healthy_cur = (FIXTURES / "healthyco_10k_2023.html").read_text()
    healthy_prev = (FIXTURES / "healthyco_10k_2022.html").read_text()
    problem_cur = (FIXTURES / "problemco_10k_2020.html").read_text()
    problem_prev = (FIXTURES / "problemco_10k_2019.html").read_text()
    healthy_facts = json.loads((FIXTURES / "companyfacts_healthyco.json").read_text())
    problem_facts = json.loads((FIXTURES / "companyfacts_problemco.json").read_text())

    # (a) XBRL figures match the fixture ground truth ------------------------
    fin = extract_key_financials(healthy_facts, form="10-K", fiscal_year=2023)
    for metric, expected in [("revenue", 383_285_000_000), ("net_income", 96_995_000_000),
                             ("total_assets", 352_583_000_000)]:
        actual = fin["metrics"].get(metric, {}).get("value")
        report.add(
            "xbrl_accuracy", f"HealthyCo FY2023 {metric}",
            actual == expected, f"expected {expected:,}, got {actual:,}" if actual else "missing",
        )

    fin = extract_key_financials(problem_facts, form="10-K", fiscal_year=2020)
    for metric, expected in [("revenue", 5_258_000_000), ("net_income", -1_714_000_000)]:
        actual = fin["metrics"].get(metric, {}).get("value")
        report.add(
            "xbrl_accuracy", f"ProblemCo FY2020 {metric}",
            actual == expected, f"expected {expected:,}, got {actual:,}" if actual else "missing",
        )

    # (b) Diff analysis detects the known risk-factor changes ----------------
    cur_1a = extract_sections(healthy_cur, form="10-K")["1A"].text
    prev_1a = extract_sections(healthy_prev, form="10-K")["1A"].text
    changes = diff_risk_factors(cur_1a, prev_1a)
    counts = summarize_changes(changes)
    report.add(
        "risk_diff", "HealthyCo 2023 vs 2022 counts",
        counts == {"new": 1, "modified": 1, "unchanged": 1, "removed": 1},
        f"got {counts}",
    )
    new_risks = [c for c in changes if c.status == "new"]
    report.add(
        "risk_diff", "HealthyCo new AI-regulation risk detected",
        any("artificial intelligence" in c.current_excerpt.lower() for c in new_risks),
        new_risks[0].current_excerpt[:100] if new_risks else "no new risks found",
    )
    modified = [c for c in changes if c.status == "modified"]
    report.add(
        "risk_diff", "HealthyCo modified cybersecurity risk detected",
        any("cybersecurity" in c.current_excerpt.lower() for c in modified),
        modified[0].current_excerpt[:100] if modified else "no modified risks found",
    )

    cur_1a = extract_sections(problem_cur, form="10-K")["1A"].text
    prev_1a = extract_sections(problem_prev, form="10-K")["1A"].text
    changes = diff_risk_factors(cur_1a, prev_1a)
    new_risks = [c for c in changes if c.status == "new"]
    report.add(
        "risk_diff", "ProblemCo new going-concern risk detected as NEW",
        any("going concern" in c.current_excerpt.lower() for c in new_risks),
        f"{len(new_risks)} new risks",
    )

    # (c) Red flags fire on the problem case, not on the healthy one ---------
    parsed_problem = ParsedFiling(
        ref=_make_ref("PRBL", "ProblemCo Holdings Inc.", "10-K", "2020-12-31"),
        sections=extract_sections(problem_cur, form="10-K"),
    )
    flags = {f.flag_id for f in detect_red_flags(parsed_problem)}
    for expected_flag in ("going_concern", "bankruptcy", "covenant_breach"):
        report.add(
            "red_flags", f"ProblemCo FY2020 raises {expected_flag}",
            expected_flag in flags, f"flags found: {sorted(flags)}",
        )

    parsed_healthy = ParsedFiling(
        ref=_make_ref("HLTH", "HealthyCo Inc.", "10-K", "2023-09-30"),
        sections=extract_sections(healthy_cur, form="10-K"),
    )
    healthy_flags = detect_red_flags(parsed_healthy)
    report.add(
        "red_flags", "HealthyCo FY2023 raises no flags",
        healthy_flags == [], f"flags found: {[f.flag_id for f in healthy_flags]}",
    )


# ----------------------------------------------------------------------- live

def run_live(report: EvalReport) -> None:
    from sec_filing_analyzer.config import load_settings
    from sec_filing_analyzer.edgar.client import EdgarClient
    from sec_filing_analyzer.pipeline import parse_filing

    settings = load_settings()
    client = EdgarClient(settings)

    for spec in LIVE_COMPANIES:
        ticker, fy = spec["ticker"], spec["fiscal_year"]
        company = client.lookup_company(ticker)

        # Find the 10-K covering the target fiscal year (walk back in history).
        refs = client.list_filings(company, form="10-K", last=15)
        target = next((r for r in refs if r.fiscal_year == fy), None)
        if target is None:
            report.add("setup", f"{ticker} 10-K FY{fy}", False, "filing not found")
            continue
        prior = next((r for r in refs if r.filing_date < target.filing_date), None)

        # (a) XBRL vs. officially reported figures
        facts = client.get_company_facts(company)
        fin = extract_key_financials(facts, form="10-K", fiscal_year=fy,
                                     accession=target.accession_number)
        for metric, expected in spec["expected"].items():
            actual = fin["metrics"].get(metric, {}).get("value")
            report.add(
                "xbrl_accuracy", f"{ticker} FY{fy} {metric}",
                _within_tolerance(actual, expected),
                f"expected ~{expected:,}, got {actual:,}" if actual is not None else "missing",
            )

        # (b) Diff analysis vs. prior 10-K
        parsed = parse_filing(client, target)
        if prior is not None and "1A" in parsed.sections:
            parsed_prior = parse_filing(client, prior)
            if "1A" in parsed_prior.sections:
                changes = diff_risk_factors(
                    parsed.sections["1A"].text, parsed_prior.sections["1A"].text
                )
                counts = summarize_changes(changes)
                report.add(
                    "risk_diff", f"{ticker} FY{fy} vs prior year",
                    counts["new"] + counts["modified"] >= 1 and counts["unchanged"] >= 1,
                    f"got {counts}",
                )

        # (c) Red flags
        flags = {f.flag_id for f in detect_red_flags(parsed)}
        if spec["problem_case"]:
            report.add(
                "red_flags", f"{ticker} FY{fy} (problem case) raises going_concern",
                "going_concern" in flags, f"flags found: {sorted(flags)}",
            )
        else:
            hard_flags = flags & {"going_concern", "bankruptcy", "restatement"}
            report.add(
                "red_flags", f"{ticker} FY{fy} raises no hard flags",
                not hard_flags, f"flags found: {sorted(flags)}",
            )


# ---------------------------------------------------------------------- output

def write_results(report: EvalReport, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = {
        "mode": report.mode,
        "timestamp": timestamp,
        "passed": report.passed,
        "total": len(report.results),
        "failures": sum(1 for r in report.results if not r.passed),
        "results": [vars(r) for r in report.results],
    }
    (out_dir / f"results_{report.mode}.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )

    lines = [
        f"# Evaluation Results ({report.mode} mode)",
        "",
        f"- Run: {timestamp}",
        f"- Checks: {payload['total']}, failures: {payload['failures']}",
        f"- Overall: {'✅ PASSED' if report.passed else '❌ FAILED'}",
        "",
        "| Check | Subject | Result | Detail |",
        "|---|---|---|---|",
    ]
    for r in report.results:
        lines.append(
            f"| {r.check} | {r.subject} | {'✅' if r.passed else '❌'} | {r.detail} |"
        )
    if report.mode == "offline":
        lines += [
            "",
            "_Offline mode validates the full assertion suite against bundled fixture",
            "filings (the problem case is modeled on Hertz Global Holdings' FY2020",
            "disclosures). Run with `--live` for the same checks against real EDGAR",
            "filings of AAPL, MSFT, JNJ, KO and HTZ._",
        ]
    (out_dir / f"results_{report.mode}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nResults written to {out_dir}/results_{report.mode}.{{json,md}}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="run against real EDGAR data")
    parser.add_argument("--out", type=Path, default=EVALS_DIR / "results")
    args = parser.parse_args()

    report = EvalReport(mode="live" if args.live else "offline")
    if args.live:
        run_live(report)
    else:
        run_offline(report)
    write_results(report, args.out)
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
