import pytest

from sec_filing_analyzer.edgar.client import EdgarClient, EdgarError


@pytest.fixture
def client(settings, stub_session):
    c = EdgarClient(settings, session=stub_session)
    c.rate_limiter.min_interval = 0  # no artificial waits in tests
    return c


def test_lookup_company(client):
    company = client.lookup_company("exco")
    assert company.cik == 999999
    assert company.name == "ExampleCo Inc."
    assert company.cik_padded == "0000999999"


def test_lookup_unknown_ticker_raises(client):
    with pytest.raises(EdgarError, match="not found"):
        client.lookup_company("NOPE")


def test_list_filings_filters_form_and_order(client, company):
    refs = client.list_filings(company, form="10-K", last=2)
    assert [r.filing_date for r in refs] == ["2023-11-03", "2022-10-28"]
    assert all(r.form == "10-K" for r in refs)
    assert refs[0].accession_nodash == "000099999923000106"
    assert refs[0].fiscal_year == 2023


def test_list_filings_missing_form_raises(client, company):
    with pytest.raises(EdgarError, match="No 20-F filings"):
        client.list_filings(company, form="20-F")


def test_download_uses_cache_on_second_call(client, company, filing_10k_2023, stub_session):
    html1 = client.download_filing_html(filing_10k_2023)
    n_requests = len(stub_session.requests)
    html2 = client.download_filing_html(filing_10k_2023)
    assert html1 == html2
    assert len(stub_session.requests) == n_requests  # served from disk cache


def test_company_facts(client, company):
    facts = client.get_company_facts(company)
    assert facts["entityName"] == "ExampleCo Inc."
    assert "us-gaap" in facts["facts"]
