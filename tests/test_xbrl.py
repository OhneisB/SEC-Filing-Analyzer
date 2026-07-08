import pytest

from sec_filing_analyzer.parsing.xbrl import extract_key_financials


def test_extracts_fy2023_values(companyfacts):
    result = extract_key_financials(companyfacts, form="10-K", fiscal_year=2023)
    metrics = result["metrics"]
    assert metrics["revenue"]["value"] == 383_285_000_000
    assert metrics["net_income"]["value"] == 96_995_000_000
    assert metrics["total_assets"]["value"] == 352_583_000_000
    assert metrics["eps_diluted"]["value"] == 6.13
    assert metrics["operating_cash_flow"]["value"] == 110_543_000_000


def test_flow_metrics_require_full_year_duration(companyfacts):
    # The Q4-only revenue fact (89,498M, ~90 days) must never be picked.
    result = extract_key_financials(companyfacts, form="10-K", fiscal_year=2023)
    assert result["metrics"]["revenue"]["value"] != 89_498_000_000


def test_prior_year_comparative_not_picked(companyfacts):
    # The FY2023 10-K also reports FY2022 revenue (394,328M) with fy=2023;
    # sorting by period end must select the FY2023 figure.
    result = extract_key_financials(companyfacts, form="10-K", fiscal_year=2023)
    assert result["metrics"]["revenue"]["end"] == "2023-09-30"


def test_infers_latest_fiscal_year(companyfacts):
    result = extract_key_financials(companyfacts, form="10-K")
    assert result["fiscal_year"] == 2023


def test_accession_filter(companyfacts):
    result = extract_key_financials(
        companyfacts, form="10-K", fiscal_year=2023, accession="0000999999-23-000106"
    )
    assert result["metrics"]["net_income"]["accession"] == "0000999999-23-000106"


def test_raises_without_data():
    with pytest.raises(ValueError):
        extract_key_financials({"facts": {"us-gaap": {}}}, form="10-K")
