"""Shared data model for filings, sections and analysis results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Company:
    ticker: str
    cik: int
    name: str

    @property
    def cik_padded(self) -> str:
        return f"{self.cik:010d}"


@dataclass
class FilingRef:
    """One entry from the EDGAR submissions index."""

    company: Company
    form: str
    accession_number: str  # e.g. "0000320193-23-000106"
    filing_date: str  # ISO date
    report_date: str  # period of report, ISO date
    primary_document: str
    primary_doc_description: str = ""

    @property
    def accession_nodash(self) -> str:
        return self.accession_number.replace("-", "")

    @property
    def fiscal_year(self) -> int:
        return int((self.report_date or self.filing_date)[:4])


@dataclass
class Section:
    item: str  # canonical item id, e.g. "1A", "7", "4.01"
    title: str
    text: str


@dataclass
class ParsedFiling:
    ref: FilingRef
    sections: dict[str, Section] = field(default_factory=dict)
    full_text: str = ""


@dataclass
class RiskChange:
    status: str  # "new" | "modified" | "unchanged" | "removed"
    similarity: float
    current_excerpt: str = ""
    previous_excerpt: str = ""
    ai_note: str = ""


@dataclass
class RedFlag:
    flag_id: str  # e.g. "going_concern"
    label: str
    severity: str  # "high" | "medium" | "low"
    evidence: str
    source_item: str = ""


@dataclass
class SectionSummary:
    item: str
    title: str
    summary: str
    method: str  # "ai" | "extractive"


@dataclass
class FilingAnalysis:
    ref: FilingRef
    summaries: list[SectionSummary] = field(default_factory=list)
    red_flags: list[RedFlag] = field(default_factory=list)
    risk_changes: list[RiskChange] = field(default_factory=list)
    financials: dict[str, Any] = field(default_factory=dict)
    ai_used: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "company": {
                "ticker": self.ref.company.ticker,
                "cik": self.ref.company.cik,
                "name": self.ref.company.name,
            },
            "filing": {
                "form": self.ref.form,
                "accession_number": self.ref.accession_number,
                "filing_date": self.ref.filing_date,
                "report_date": self.ref.report_date,
                "primary_document": self.ref.primary_document,
            },
            "ai_used": self.ai_used,
            "summaries": [vars(s) for s in self.summaries],
            "red_flags": [vars(f) for f in self.red_flags],
            "risk_changes": [vars(c) for c in self.risk_changes],
            "financials": self.financials,
        }
