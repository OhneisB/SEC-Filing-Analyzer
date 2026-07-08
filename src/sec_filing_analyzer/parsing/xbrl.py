"""Extract key financial figures from SEC XBRL company facts.

Input is the JSON from ``/api/xbrl/companyfacts/CIK##########.json``.
For each metric we try a list of us-gaap concepts (companies tag revenue
differently), filter facts to the requested fiscal year of the requested
form, and require full-year durations for flow metrics.
"""

from __future__ import annotations

from datetime import date
from typing import Any

# Metric -> ordered list of us-gaap concepts to try.
CONCEPT_MAP: dict[str, list[str]] = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss"],
    "eps_diluted": ["EarningsPerShareDiluted"],
    "total_assets": ["Assets"],
    "total_liabilities": ["Liabilities"],
    "stockholders_equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "cash_and_equivalents": ["CashAndCashEquivalentsAtCarryingValue"],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
}

# Flow metrics must cover (roughly) a full fiscal year in a 10-K.
_FLOW_METRICS = {"revenue", "operating_income", "net_income", "eps_diluted", "operating_cash_flow"}
_ANNUAL_DURATION_DAYS = (330, 400)
_QUARTER_DURATION_DAYS = (75, 105)


def _duration_days(fact: dict[str, Any]) -> int | None:
    try:
        start = date.fromisoformat(fact["start"])
        end = date.fromisoformat(fact["end"])
    except (KeyError, ValueError):
        return None
    return (end - start).days


def _iter_facts(facts: dict[str, Any], concept: str):
    node = facts.get("facts", {}).get("us-gaap", {}).get(concept)
    if not node:
        return
    for unit, entries in node.get("units", {}).items():
        if unit not in ("USD", "USD/shares"):
            continue
        yield from entries


def _select_fact(
    facts: dict[str, Any],
    concept: str,
    form: str,
    fiscal_year: int,
    is_flow: bool,
    accession: str | None,
) -> dict[str, Any] | None:
    matches = []
    for f in _iter_facts(facts, concept):
        if f.get("form", "").upper() != form.upper():
            continue
        if f.get("fy") != fiscal_year and int(str(f.get("end", "0000"))[:4] or 0) != fiscal_year:
            # Accept either EDGAR's fy tag or the period end year.
            continue
        if is_flow:
            days = _duration_days(f)
            lo, hi = _ANNUAL_DURATION_DAYS if form.upper() == "10-K" else _QUARTER_DURATION_DAYS
            if days is None or not (lo <= days <= hi):
                continue
        matches.append(f)
    if not matches:
        return None
    if accession:
        own = [f for f in matches if f.get("accn") == accession]
        if own:
            matches = own
    # Prefer the fact with the latest period end, then the one carrying a frame.
    matches.sort(key=lambda f: (f.get("end", ""), bool(f.get("frame"))), reverse=True)
    return matches[0]


def extract_key_financials(
    facts: dict[str, Any],
    form: str = "10-K",
    fiscal_year: int | None = None,
    accession: str | None = None,
) -> dict[str, Any]:
    """Return a structured dict of key financials for one fiscal period.

    ``fiscal_year`` defaults to the latest year present for net income.
    Values are reported in the unit EDGAR uses (USD, USD/shares).
    """
    if fiscal_year is None:
        years = [
            f.get("fy")
            for f in _iter_facts(facts, "NetIncomeLoss")
            if f.get("form", "").upper() == form.upper() and f.get("fy")
        ]
        if not years:
            raise ValueError("Could not infer fiscal year from company facts")
        fiscal_year = max(years)

    result: dict[str, Any] = {
        "entity": facts.get("entityName", ""),
        "cik": facts.get("cik"),
        "form": form,
        "fiscal_year": fiscal_year,
        "metrics": {},
    }
    for metric, concepts in CONCEPT_MAP.items():
        for concept in concepts:
            fact = _select_fact(
                facts, concept, form, fiscal_year, metric in _FLOW_METRICS, accession
            )
            if fact is not None:
                result["metrics"][metric] = {
                    "value": fact.get("val"),
                    "concept": concept,
                    "start": fact.get("start"),
                    "end": fact.get("end"),
                    "accession": fact.get("accn"),
                    "filed": fact.get("filed"),
                }
                break
    return result
