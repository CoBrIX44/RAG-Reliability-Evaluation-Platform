"""Resolve whitespace-normalized authored quotes to canonical code-point spans."""

import re


def quote_span(text: str, quote: str) -> tuple[int, int]:
    normalized: list[str] = []
    positions: list[int] = []
    for match in re.finditer(r"\S+", text):
        if normalized:
            normalized.append(" ")
            positions.append(match.start() - 1)
        normalized.extend(match.group())
        positions.extend(range(match.start(), match.end()))
    value = "".join(normalized)
    needle = " ".join(quote.split())
    start = value.find(needle)
    if not needle or start < 0 or value.find(needle, start + 1) >= 0:
        raise ValueError("Authored evidence quote must match exactly once in a canonical section")
    return positions[start], positions[start + len(needle) - 1] + 1
