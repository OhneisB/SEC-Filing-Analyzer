"""Rule-based red-flag detection in filing text.

Deterministic pattern scan for the classic warning signs. Each rule
defines regex patterns plus optional negation guards (to avoid firing on
boilerplate like "there is no substantial doubt"). The optional AI pass
in ai.py can review the evidence, but detection itself never depends on
an API key — this keeps CI and evals reproducible.

8-K specifics: Item 4.01 (auditor change) and Item 4.02 (non-reliance /
restatement) are red flags by presence of the item itself.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..models import ParsedFiling, RedFlag

_EVIDENCE_CHARS = 300


@dataclass(frozen=True)
class Rule:
    flag_id: str
    label: str
    severity: str
    patterns: tuple[str, ...]
    negations: tuple[str, ...] = ()


RULES: tuple[Rule, ...] = (
    Rule(
        flag_id="going_concern",
        label="Going-concern doubt",
        severity="high",
        patterns=(
            r"substantial doubt (?:exists )?(?:about|regarding|as to) (?:the |our |its |the company'?s? )?ability to continue as a going concern",
            r"ability to continue as a going concern",
            r"may not be able to continue as a going concern",
        ),
        negations=(
            r"no substantial doubt",
            r"does not raise substantial doubt",
            r"alleviated? (?:the )?substantial doubt",
        ),
    ),
    Rule(
        flag_id="restatement",
        label="Restatement of previously issued financial statements",
        severity="high",
        patterns=(
            r"restat(?:e|ed|ement|ing) (?:of )?(?:our |the |its |certain )?previously (?:issued|reported) (?:consolidated )?financial statements",
            r"non-?reliance on previously issued financial statements",
            r"should no longer be relied upon",
        ),
    ),
    Rule(
        flag_id="material_weakness",
        label="Material weakness in internal control over financial reporting",
        severity="high",
        patterns=(r"material weakness(?:es)? in (?:our |the |its )?internal control",),
        negations=(
            r"no material weakness",
            r"did not identify any material weakness",
            r"remediated (?:the|all|our) (?:previously (?:identified|reported) )?material weakness",
        ),
    ),
    Rule(
        flag_id="auditor_change",
        label="Change of independent auditor",
        severity="medium",
        patterns=(
            r"dismissed .{0,80} as (?:our|its|the company'?s?) independent registered public accounting firm",
            r"(?:resigned|declined to stand for re-?appointment) as (?:our|its|the company'?s?) independent registered public accounting firm",
            r"engaged .{0,80} as (?:our|its|the company'?s?) new independent registered public accounting firm",
        ),
    ),
    Rule(
        flag_id="accounting_change",
        label="Unusual accounting change / SEC correspondence",
        severity="medium",
        patterns=(
            r"change in accounting principle",
            r"(?:received|responding to) (?:a )?(?:comment|subpoena|inquiry|investigation) (?:letter )?from the (?:SEC|Securities and Exchange Commission)",
            r"revised? (?:our|its) revenue recognition (?:policy|practices)",
        ),
    ),
    Rule(
        flag_id="covenant_breach",
        label="Debt covenant breach / liquidity stress",
        severity="medium",
        patterns=(
            r"(?:breach|violation|not in compliance) (?:of|with) (?:our |its |certain )?(?:financial |debt )?covenants",
            r"waiver (?:of|under) (?:our |its |certain )?(?:financial |debt )?covenants",
            r"missed (?:an? )?(?:scheduled )?(?:interest|principal) payment",
        ),
    ),
    Rule(
        flag_id="bankruptcy",
        label="Bankruptcy / reorganization proceedings",
        severity="high",
        patterns=(
            r"chapter 11 (?:cases?|proceedings?|petitions?|protection)",
            r"voluntary petitions? for (?:relief|reorganization)",
        ),
    ),
)

# 8-K items whose mere presence is a red flag.
EIGHT_K_ITEM_FLAGS = {
    "4.01": ("auditor_change", "Change of independent auditor (8-K Item 4.01)", "medium"),
    "4.02": ("restatement", "Non-reliance on prior financials (8-K Item 4.02)", "high"),
}


def _scan_text(text: str, source_item: str) -> list[RedFlag]:
    flags: list[RedFlag] = []
    # Flatten whitespace so phrases wrapped across lines still match.
    text = re.sub(r"\s+", " ", text)
    lowered = text.lower()
    for rule in RULES:
        match = None
        for pat in rule.patterns:
            match = re.search(pat, lowered)
            if match:
                break
        if not match:
            continue
        window = lowered[max(0, match.start() - 200): match.end() + 200]
        if any(re.search(neg, window) for neg in rule.negations):
            continue
        start = max(0, match.start() - 120)
        evidence = re.sub(r"\s+", " ", text[start:start + _EVIDENCE_CHARS]).strip()
        flags.append(
            RedFlag(
                flag_id=rule.flag_id,
                label=rule.label,
                severity=rule.severity,
                evidence=f"…{evidence}…",
                source_item=source_item,
            )
        )
    return flags


def detect_red_flags(filing: ParsedFiling) -> list[RedFlag]:
    """Scan a parsed filing for red flags (deduplicated by flag id)."""
    found: dict[str, RedFlag] = {}

    if filing.ref.form.upper().startswith("8-K"):
        for item, (flag_id, label, severity) in EIGHT_K_ITEM_FLAGS.items():
            if item in filing.sections:
                found[flag_id] = RedFlag(
                    flag_id=flag_id,
                    label=label,
                    severity=severity,
                    evidence=re.sub(r"\s+", " ", filing.sections[item].text[:_EVIDENCE_CHARS]),
                    source_item=item,
                )

    targets = [(s.item, s.text) for s in filing.sections.values()]
    if not targets and filing.full_text:
        targets = [("", filing.full_text)]
    for item, text in targets:
        for flag in _scan_text(text, item):
            if flag.flag_id not in found:  # first evidence per flag id wins
                found[flag.flag_id] = flag
    return list(found.values())
