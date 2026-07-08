"""Split SEC filing HTML into canonical item sections.

Strategy: convert the HTML to line-oriented plain text, find all item
headings ("Item 1A.", "Item 7.", for 8-Ks "Item 4.01" ...), then build
sections from consecutive headings. Item numbers usually appear twice
(table of contents + body); for each item we keep the occurrence that
yields the longest section, which reliably skips the TOC.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

from ..models import Section

# Canonical titles for the items we care about most.
ITEM_TITLES_10K = {
    "1": "Business",
    "1A": "Risk Factors",
    "1B": "Unresolved Staff Comments",
    "1C": "Cybersecurity",
    "2": "Properties",
    "3": "Legal Proceedings",
    "4": "Mine Safety Disclosures",
    "5": "Market for Registrant's Common Equity",
    "6": "Selected Financial Data / Reserved",
    "7": "Management's Discussion and Analysis (MD&A)",
    "7A": "Quantitative and Qualitative Disclosures About Market Risk",
    "8": "Financial Statements and Supplementary Data",
    "9": "Changes in and Disagreements with Accountants",
    "9A": "Controls and Procedures",
    "9B": "Other Information",
    "10": "Directors, Executive Officers and Corporate Governance",
    "11": "Executive Compensation",
    "15": "Exhibits and Financial Statement Schedules",
}

ITEM_TITLES_8K = {
    "1.01": "Entry into a Material Definitive Agreement",
    "2.02": "Results of Operations and Financial Condition",
    "4.01": "Changes in Registrant's Certifying Accountant",
    "4.02": "Non-Reliance on Previously Issued Financial Statements",
    "5.02": "Departure/Election of Directors or Officers",
    "7.01": "Regulation FD Disclosure",
    "8.01": "Other Events",
    "9.01": "Financial Statements and Exhibits",
}

# "Item 1A." / "ITEM 7:" at the start of a line (10-K/10-Q style)
_ITEM_RE_ANNUAL = re.compile(r"^\s*item\s+(\d{1,2}[A-C]?)\s*[.:—–-]\s*\S", re.IGNORECASE | re.MULTILINE)
# "Item 4.01" (8-K style)
_ITEM_RE_8K = re.compile(r"^\s*item\s+(\d{1,2}\.\d{2})\b", re.IGNORECASE | re.MULTILINE)


def html_to_text(html: str) -> str:
    """Convert filing HTML to plain text.

    Block elements become separate paragraphs (blank line between them) so
    downstream code can split risk factors on paragraph boundaries.
    """
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style"]):
        tag.decompose()
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for tag in soup.find_all(["p", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "table"]):
        tag.append("\n\n")
    text = soup.get_text("\n")
    # Normalize unicode whitespace and collapse blank runs.
    text = text.replace("\xa0", " ").replace("’", "'")
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines()]
    out: list[str] = []
    blank = False
    for ln in lines:
        if ln:
            out.append(ln)
            blank = False
        elif not blank:
            out.append("")
            blank = True
    return "\n".join(out)


@dataclass
class _Heading:
    item: str
    start: int  # offset of the heading in the text
    body_start: int  # offset right after the heading line


def _find_headings(text: str, pattern: re.Pattern) -> list[_Heading]:
    headings = []
    for m in pattern.finditer(text):
        line_end = text.find("\n", m.start())
        if line_end == -1:
            line_end = len(text)
        headings.append(_Heading(item=m.group(1).upper(), start=m.start(), body_start=m.start()))
    return headings


def extract_sections(html_or_text: str, form: str = "10-K") -> dict[str, Section]:
    """Extract item sections from a filing.

    Accepts raw HTML or already-converted plain text. Returns a dict keyed
    by canonical item id ("1A", "7", "4.01", ...).
    """
    text = html_to_text(html_or_text) if "<" in html_or_text[:2000] else html_or_text
    is_8k = form.upper().startswith("8-K")
    pattern = _ITEM_RE_8K if is_8k else _ITEM_RE_ANNUAL
    titles = ITEM_TITLES_8K if is_8k else ITEM_TITLES_10K

    headings = _find_headings(text, pattern)
    if not headings:
        return {}

    # Candidate section for every heading occurrence: from this heading to the
    # next heading of any item (or end of document).
    candidates: dict[str, tuple[int, str]] = {}  # item -> (length, body)
    for idx, h in enumerate(headings):
        end = headings[idx + 1].start if idx + 1 < len(headings) else len(text)
        body = text[h.body_start:end].strip()
        length = len(body)
        # Keep the longest occurrence per item (body beats table of contents).
        if h.item not in candidates or length > candidates[h.item][0]:
            candidates[h.item] = (length, body)

    sections: dict[str, Section] = {}
    for item, (length, body) in candidates.items():
        if length < 40:  # heading with no real content (e.g. TOC-only match)
            continue
        sections[item] = Section(
            item=item,
            title=titles.get(item, f"Item {item}"),
            text=body,
        )
    return sections
