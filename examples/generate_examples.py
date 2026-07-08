#!/usr/bin/env python3
"""Generate committed showcase reports under examples/showcase/.

Runs the full offline pipeline (deterministic, no AI, no network) against the
bundled fixture filings so the public repo contains real example output —
Markdown + JSON — without anyone needing API keys or a live backend.

The two subjects mirror the eval fixtures:
- healthyco : a healthy large-cap (modeled on Apple FY2023 vs FY2022)
- problemco : the historical problem case (modeled on Hertz FY2020 vs FY2019)

Usage: uv run python examples/generate_examples.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sec_filing_analyzer.analysis.diff import diff_risk_factors
from sec_filing_analyzer.analysis.redflags import detect_red_flags
from sec_filing_analyzer.models import Company, FilingAnalysis, FilingRef, ParsedFiling
from sec_filing_analyzer.parsing.sections import extract_sections, html_to_text
from sec_filing_analyzer.parsing.xbrl import extract_key_financials
from sec_filing_analyzer.reporting.writer import write_reports

EVAL_FIXTURES = ROOT / "evals" / "fixtures"
OUT = ROOT / "examples" / "showcase"

SUBJECTS = [
    {
        "ticker": "HEALTHYCO", "name": "HealthyCo Inc. (illustrative, modeled on Apple FY2023)",
        "cur": "healthyco_10k_2023.html", "prev": "healthyco_10k_2022.html",
        "facts": "companyfacts_healthyco.json", "fy": 2023, "report_date": "2023-09-30",
        "summary_items": ["1", "1A", "7"],
    },
    {
        "ticker": "PROBLEMCO", "name": "ProblemCo Holdings Inc. (illustrative, modeled on Hertz FY2020)",
        "cur": "problemco_10k_2020.html", "prev": "problemco_10k_2019.html",
        "facts": "companyfacts_problemco.json", "fy": 2020, "report_date": "2020-12-31",
        "summary_items": ["1", "1A", "7"],
    },
]


def _parse(html: str, ref: FilingRef) -> ParsedFiling:
    text = html_to_text(html)
    return ParsedFiling(ref=ref, sections=extract_sections(text, form="10-K"), full_text=text)


def build_one(spec: dict) -> tuple[Path, Path]:
    from sec_filing_analyzer.analysis.ai import extractive_summary
    from sec_filing_analyzer.models import SectionSummary

    company = Company(ticker=spec["ticker"], cik=0, name=spec["name"])
    ref = FilingRef(
        company=company, form="10-K", accession_number="fixture-example",
        filing_date=spec["report_date"], report_date=spec["report_date"],
        primary_document="fixture.htm",
    )
    cur = _parse((EVAL_FIXTURES / spec["cur"]).read_text(), ref)
    prev = _parse((EVAL_FIXTURES / spec["prev"]).read_text(), ref)
    facts = json.loads((EVAL_FIXTURES / spec["facts"]).read_text())

    analysis = FilingAnalysis(ref=ref, ai_used=False)
    for item in spec["summary_items"]:
        section = cur.sections.get(item)
        if section:
            analysis.summaries.append(
                SectionSummary(item, section.title, extractive_summary(section.text), "extractive")
            )
    if "1A" in cur.sections and "1A" in prev.sections:
        analysis.risk_changes = diff_risk_factors(cur.sections["1A"].text, prev.sections["1A"].text)
    analysis.red_flags = detect_red_flags(cur)
    analysis.financials = extract_key_financials(facts, form="10-K", fiscal_year=spec["fy"])

    return write_reports(analysis, OUT)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for spec in SUBJECTS:
        md, js = build_one(spec)
        print(f"wrote {md.relative_to(ROOT)}")
        print(f"wrote {js.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
