"""End-to-end analysis pipeline: download -> parse -> analyze -> report."""

from __future__ import annotations

import logging

from .analysis.ai import AiAnalyzer
from .analysis.diff import diff_risk_factors
from .analysis.redflags import detect_red_flags
from .config import Settings
from .edgar.client import EdgarClient
from .models import FilingAnalysis, FilingRef, ParsedFiling
from .parsing.sections import extract_sections, html_to_text
from .parsing.xbrl import extract_key_financials

log = logging.getLogger(__name__)

# Sections worth summarizing per form type.
SUMMARY_ITEMS = {
    "10-K": ["1", "1A", "7", "7A"],
    "10-Q": ["1A", "2"],
    "8-K": ["2.02", "4.01", "4.02", "8.01"],
}


def parse_filing(client: EdgarClient, ref: FilingRef) -> ParsedFiling:
    html = client.download_filing_html(ref)
    text = html_to_text(html)
    sections = extract_sections(text, form=ref.form)
    return ParsedFiling(ref=ref, sections=sections, full_text=text)


def analyze_filing(
    client: EdgarClient,
    settings: Settings,
    parsed: ParsedFiling,
    previous: ParsedFiling | None = None,
    use_ai: bool = True,
    company_facts: dict | None = None,
) -> FilingAnalysis:
    ref = parsed.ref
    ai = AiAnalyzer(settings, enabled=use_ai)

    analysis = FilingAnalysis(ref=ref, ai_used=ai.enabled)

    # 1) Section summaries
    for item in SUMMARY_ITEMS.get(ref.form.upper(), []):
        section = parsed.sections.get(item)
        if section:
            analysis.summaries.append(
                ai.summarize_section(section, ref.company.name, ref.form)
            )

    # 2) Risk factor diff vs. prior filing
    if previous is not None:
        cur = parsed.sections.get("1A")
        prev = previous.sections.get("1A")
        if cur and prev:
            analysis.risk_changes = diff_risk_factors(cur.text, prev.text)
            ai.annotate_risk_changes(analysis.risk_changes, ref.company.name, ref.form)
        else:
            log.warning("Risk Factors section missing in current or prior filing; skipping diff.")

    # 3) Red flags
    analysis.red_flags = detect_red_flags(parsed)
    ai.review_red_flags(analysis.red_flags, ref.company.name, ref.form)

    # 4) XBRL key financials (10-K / 10-Q only)
    if ref.form.upper() in ("10-K", "10-Q"):
        try:
            facts = company_facts if company_facts is not None else client.get_company_facts(ref.company)
            analysis.financials = extract_key_financials(
                facts,
                form=ref.form,
                fiscal_year=ref.fiscal_year,
                accession=ref.accession_number,
            )
        except Exception as exc:
            log.warning("XBRL extraction failed: %s", exc)

    return analysis
