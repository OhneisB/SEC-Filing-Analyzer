from sec_filing_analyzer.analysis.diff import (
    diff_risk_factors,
    split_risk_units,
    summarize_changes,
)
from sec_filing_analyzer.parsing.sections import extract_sections


def _risk_texts(sample_10k_2023, sample_10k_2022):
    cur = extract_sections(sample_10k_2023, form="10-K")["1A"].text
    prev = extract_sections(sample_10k_2022, form="10-K")["1A"].text
    return cur, prev


def test_split_risk_units(sample_10k_2023):
    text = extract_sections(sample_10k_2023, form="10-K")["1A"].text
    units = split_risk_units(text)
    assert len(units) == 3  # suppliers, cybersecurity, AI regulation
    assert any("suppliers" in u for u in units)


def test_diff_classification(sample_10k_2023, sample_10k_2022):
    cur, prev = _risk_texts(sample_10k_2023, sample_10k_2022)
    changes = diff_risk_factors(cur, prev)
    counts = summarize_changes(changes)

    # Supplier risk identical -> unchanged; cyber risk gained a ransomware
    # sentence -> modified; AI risk only in 2023 -> new; COVID risk only in
    # 2022 -> removed.
    assert counts == {"new": 1, "modified": 1, "unchanged": 1, "removed": 1}

    new = [c for c in changes if c.status == "new"][0]
    assert "artificial intelligence" in new.current_excerpt.lower()

    modified = [c for c in changes if c.status == "modified"][0]
    assert "cybersecurity" in modified.current_excerpt.lower()
    assert 0.55 <= modified.similarity < 0.92

    removed = [c for c in changes if c.status == "removed"][0]
    assert "covid" in removed.previous_excerpt.lower()


def test_identical_texts_all_unchanged(sample_10k_2023):
    cur, _ = _risk_texts(sample_10k_2023, sample_10k_2023)
    changes = diff_risk_factors(cur, cur)
    assert all(c.status == "unchanged" for c in changes)
    assert all(c.similarity == 1.0 for c in changes)
