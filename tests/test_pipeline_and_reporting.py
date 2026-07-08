import json

from sec_filing_analyzer.edgar.client import EdgarClient
from sec_filing_analyzer.pipeline import analyze_filing, parse_filing
from sec_filing_analyzer.reporting.writer import render_markdown, write_reports


def _client(settings, stub_session):
    c = EdgarClient(settings, session=stub_session)
    c.rate_limiter.min_interval = 0
    return c


def test_end_to_end_offline(settings, stub_session, company, filing_10k_2023, companyfacts):
    client = _client(settings, stub_session)
    refs = client.list_filings(company, form="10-K", last=2)
    current = parse_filing(client, refs[0])
    previous = parse_filing(client, refs[1])

    analysis = analyze_filing(
        client, settings, current,
        previous=previous, use_ai=False, company_facts=companyfacts,
    )

    assert analysis.ai_used is False
    assert analysis.financials["metrics"]["revenue"]["value"] == 383_285_000_000
    statuses = {c.status for c in analysis.risk_changes}
    assert {"new", "modified", "unchanged", "removed"} <= statuses
    assert any(s.item == "1A" for s in analysis.summaries)
    assert all(s.method == "extractive" for s in analysis.summaries)

    md_path, json_path = write_reports(analysis, settings.reports_dir)
    assert md_path.exists() and json_path.exists()

    md = md_path.read_text()
    assert "Risk Factor Changes" in md
    assert "Key Financials (XBRL)" in md

    data = json.loads(json_path.read_text())
    assert data["company"]["ticker"] == "EXCO"
    assert data["financials"]["metrics"]["net_income"]["value"] == 96_995_000_000


def test_markdown_renders_red_flags(settings, stub_session, company, filing_10k_2023):
    from sec_filing_analyzer.models import FilingAnalysis, RedFlag

    analysis = FilingAnalysis(ref=filing_10k_2023)
    analysis.red_flags.append(
        RedFlag(
            flag_id="going_concern",
            label="Going-concern doubt",
            severity="high",
            evidence="substantial doubt about the ability to continue as a going concern",
        )
    )
    md = render_markdown(analysis)
    assert "Going-concern doubt" in md
    assert "🔴" in md
