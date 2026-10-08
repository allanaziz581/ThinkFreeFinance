#!/usr/bin/env python3
"""
ThinkFree Finance, numeral set-membership validation for GPT outputs.

Every GPT output (sector summaries, economic reasoning, Chef GPT briefing) can invent
numbers that were never in the source data. This module checks that each numeral appearing
in a generated text is a MEMBER of the set of numerals in the source it was built from,
comparing NORMALIZED values with a rounding tolerance rather than raw string tokens (so
"12.3%" matches a source "12.34%", and "$1,200" matches "1200").

The legacy default ignores bare years and small counts, but always checks explicit
percentages and dollar amounts. Production report/news callers use strict=True to
also check years/counts. Matching a value does not verify its attribution or meaning.
Callers decide whether to flag or withhold an output; this module never rewrites it.
"""
from __future__ import annotations

import re

# Numbers we never treat as claims worth validating: plausible calendar years and tiny
# integers (list positions, "3 sectors", "the 8-question framework").
_YEAR_RANGE = range(1900, 2100)


def extract_numerals(text: str) -> list[float]:
    """Pull numeric values out of free text. Handles $, commas, decimals, and percentages
    (the percent sign is dropped, so 12.3% -> 12.3). Signs are captured."""
    if not text:
        return []
    out: list[float] = []
    # match optional sign, digits with optional thousands commas, optional decimal
    for m in re.finditer(r"(?<![\w.])[-+]?\$?\d{1,3}(?:,\d{3})+(?:\.\d+)?|(?<![\w.])[-+]?\$?\d+(?:\.\d+)?", text):
        tok = m.group(0).replace("$", "").replace(",", "")
        try:
            out.append(float(tok))
        except ValueError:
            continue
    return out


def _is_ignorable(value: float) -> bool:
    """Years and small whole counts are not factual claims we validate."""
    if value == int(value):
        iv = int(value)
        if iv in _YEAR_RANGE:
            return True
        if abs(iv) <= 12:      # small counts, list ordinals, the 8 questions, months
            return True
    return False


def _matches_any(value: float, source: list[float], tol: float, rel_tol: float) -> bool:
    for s in source:
        if abs(value - s) <= tol:
            return True
        if s != 0 and abs(value - s) / abs(s) <= rel_tol:
            return True
    return False


def validate_numerals(
    source_numbers,
    output_text: str,
    abs_tol: float = 0.1,
    rel_tol: float = 0.01,
    strict: bool = False,
) -> dict:
    """Check that every non-ignorable numeral in output_text is within tolerance of some
    number in the source.

    source_numbers may be a list of floats or a source text (it is run through
    extract_numerals if it is a string). Returns:
      {ok, checked, matched, hallucinated: [values], hallucinated_count}
    ok is True when nothing was flagged.
    """
    if isinstance(source_numbers, str):
        source = extract_numerals(source_numbers)
    else:
        source = [float(x) for x in source_numbers]

    # Small financial amounts/percentages are claims, not list ordinals.
    financial = extract_numerals(" ".join(re.findall(
        r"[-+]?\$[\d,]+(?:\.\d+)?|[-+]?[\d,]+(?:\.\d+)?\s*%", output_text)))
    candidates = [v for v in extract_numerals(output_text)
                  if strict or v in financial or not _is_ignorable(v)]
    hallucinated = [v for v in candidates if not _matches_any(v, source, abs_tol, rel_tol)]

    return {
        "ok": not hallucinated,
        "checked": len(candidates),
        "matched": len(candidates) - len(hallucinated),
        "hallucinated": hallucinated,
        "hallucinated_count": len(hallucinated),
        "scope": "numeric value membership only; does not verify attribution, units, or meaning",
    }


def collect_numbers(obj) -> list[float]:
    """Recursively pull every number out of a nested dict/list/str structure, for use as
    the source set when validating an output against its assembled inputs."""
    nums: list[float] = []
    if isinstance(obj, bool):
        return nums
    if isinstance(obj, (int, float)):
        nums.append(float(obj))
    elif isinstance(obj, str):
        nums.extend(extract_numerals(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            nums.extend(collect_numbers(v))
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            nums.extend(collect_numbers(v))
    return nums
