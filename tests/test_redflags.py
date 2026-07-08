from sec_filing_analyzer.analysis.redflags import detect_red_flags
from sec_filing_analyzer.models import ParsedFiling, Section
from sec_filing_analyzer.parsing.sections import extract_sections

GOING_CONCERN_TEXT = """
Our recurring losses from operations, negative working capital and the ongoing
Chapter 11 Cases raise substantial doubt about our ability to continue as a going
concern within one year after the date the financial statements are issued. On May 22,
2020, the Company filed voluntary petitions for relief under Chapter 11 of the
Bankruptcy Code. We were not in compliance with certain financial covenants under our
Senior RCF as of the fiscal year end.
"""

HEALTHY_TEXT = """
Management concluded that the Company's cash, cash equivalents and marketable
securities together with cash generated from operations will be sufficient to fund
its operating requirements for at least the next twelve months. The audit did not
identify any material weakness in internal control over financial reporting.
"""

NEGATED_GOING_CONCERN = """
The refinancing completed in January alleviated the substantial doubt about the
Company's ability to continue as a going concern that existed in the prior year.
"""


def _filing_with_text(filing_10k_2023, text: str) -> ParsedFiling:
    return ParsedFiling(
        ref=filing_10k_2023,
        sections={"7": Section(item="7", title="MD&A", text=text)},
    )


def test_going_concern_and_bankruptcy_detected(filing_10k_2023):
    flags = detect_red_flags(_filing_with_text(filing_10k_2023, GOING_CONCERN_TEXT))
    ids = {f.flag_id for f in flags}
    assert "going_concern" in ids
    assert "bankruptcy" in ids
    assert "covenant_breach" in ids
    gc = next(f for f in flags if f.flag_id == "going_concern")
    assert gc.severity == "high"
    assert "going concern" in gc.evidence.lower()


def test_healthy_text_produces_no_flags(filing_10k_2023):
    flags = detect_red_flags(_filing_with_text(filing_10k_2023, HEALTHY_TEXT))
    assert flags == []


def test_negation_guard(filing_10k_2023):
    flags = detect_red_flags(_filing_with_text(filing_10k_2023, NEGATED_GOING_CONCERN))
    assert all(f.flag_id != "going_concern" for f in flags)


def test_8k_auditor_change_item_flag(company, sample_8k):
    from sec_filing_analyzer.models import FilingRef

    ref = FilingRef(
        company=company,
        form="8-K",
        accession_number="0000999999-23-000042",
        filing_date="2023-03-15",
        report_date="2023-03-13",
        primary_document="exco-8k_20230315.htm",
    )
    sections = extract_sections(sample_8k, form="8-K")
    flags = detect_red_flags(ParsedFiling(ref=ref, sections=sections))
    ids = {f.flag_id for f in flags}
    assert "auditor_change" in ids
    auditor = next(f for f in flags if f.flag_id == "auditor_change")
    assert auditor.source_item == "4.01"
