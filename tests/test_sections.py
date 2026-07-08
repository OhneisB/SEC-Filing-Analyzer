from sec_filing_analyzer.parsing.sections import extract_sections, html_to_text


def test_extracts_expected_10k_items(sample_10k_2023):
    sections = extract_sections(sample_10k_2023, form="10-K")
    for item in ("1", "1A", "7", "7A", "8", "9A"):
        assert item in sections, f"missing item {item}"
    assert sections["1A"].title == "Risk Factors"


def test_body_beats_table_of_contents(sample_10k_2023):
    sections = extract_sections(sample_10k_2023, form="10-K")
    risk = sections["1A"].text
    # Real section content, not the one-line TOC entry.
    assert "limited number of suppliers" in risk
    assert "ransomware" in risk
    assert len(risk) > 500


def test_section_boundaries(sample_10k_2023):
    sections = extract_sections(sample_10k_2023, form="10-K")
    # Item 7 content must not bleed into Item 1A and vice versa.
    assert "Net sales for fiscal 2023" in sections["7"].text
    assert "Net sales for fiscal 2023" not in sections["1A"].text
    assert "ransomware" not in sections["7"].text


def test_8k_item_extraction(sample_8k):
    sections = extract_sections(sample_8k, form="8-K")
    assert "4.01" in sections
    assert "dismissed" in sections["4.01"].text
    assert "9.01" in sections


def test_html_to_text_preserves_paragraph_breaks(sample_10k_2023):
    text = html_to_text(sample_10k_2023)
    # Paragraphs must be separated by blank lines for risk-unit splitting.
    assert "\n\n" in text
    assert "<p>" not in text


def test_no_sections_in_plain_prose():
    assert extract_sections("Just some text without any items.", form="10-K") == {}
