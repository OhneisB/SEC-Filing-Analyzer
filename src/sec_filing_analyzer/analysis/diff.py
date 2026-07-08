"""Year-over-year diff of Item 1A Risk Factors.

The section text is split into individual risk-factor units (paragraph
blocks). Units of the current filing are matched against the prior
filing's units via difflib similarity, then classified:

- similarity >= 0.92           -> unchanged
- 0.55 <= similarity < 0.92    -> modified
- similarity < 0.55            -> new
- prior units without a match  -> removed

Deterministic by design so results are reproducible; an optional AI pass
(see ai.py) adds a human-readable note on what changed.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from ..models import RiskChange

UNCHANGED_THRESHOLD = 0.92
MODIFIED_THRESHOLD = 0.55
_MIN_UNIT_CHARS = 120
_EXCERPT_CHARS = 240


def split_risk_units(text: str) -> list[str]:
    """Split a Risk Factors section into individual risk paragraphs.

    Consecutive short lines (headings) are merged into the following
    paragraph; tiny fragments are dropped.
    """
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    units: list[str] = []
    pending_heading = ""
    for block in blocks:
        merged = f"{pending_heading}\n{block}".strip() if pending_heading else block
        if len(merged) < _MIN_UNIT_CHARS:
            pending_heading = merged
            continue
        units.append(merged)
        pending_heading = ""
    if pending_heading and len(pending_heading) >= _MIN_UNIT_CHARS:
        units.append(pending_heading)
    return units


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


def _excerpt(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s[:_EXCERPT_CHARS] + ("…" if len(s) > _EXCERPT_CHARS else "")


def diff_risk_factors(current_text: str, previous_text: str) -> list[RiskChange]:
    """Compare two Risk Factors sections and classify each current unit."""
    current_units = split_risk_units(current_text)
    previous_units = split_risk_units(previous_text)
    unmatched_prev = set(range(len(previous_units)))
    changes: list[RiskChange] = []

    for cur in current_units:
        best_idx, best_score = -1, 0.0
        for idx in range(len(previous_units)):
            score = _similarity(cur, previous_units[idx])
            if score > best_score:
                best_idx, best_score = idx, score
        if best_score >= UNCHANGED_THRESHOLD:
            status = "unchanged"
        elif best_score >= MODIFIED_THRESHOLD:
            status = "modified"
        else:
            status = "new"
            best_idx = -1
        if best_idx >= 0:
            unmatched_prev.discard(best_idx)
        changes.append(
            RiskChange(
                status=status,
                similarity=round(best_score, 3),
                current_excerpt=_excerpt(cur),
                previous_excerpt=_excerpt(previous_units[best_idx]) if best_idx >= 0 else "",
            )
        )

    for idx in sorted(unmatched_prev):
        changes.append(
            RiskChange(
                status="removed",
                similarity=0.0,
                current_excerpt="",
                previous_excerpt=_excerpt(previous_units[idx]),
            )
        )
    return changes


def summarize_changes(changes: list[RiskChange]) -> dict[str, int]:
    counts = {"new": 0, "modified": 0, "unchanged": 0, "removed": 0}
    for c in changes:
        counts[c.status] = counts.get(c.status, 0) + 1
    return counts
