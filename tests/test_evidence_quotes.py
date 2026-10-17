import pytest
from rag_core.evidence_quotes import quote_span


def test_normalized_quote_returns_original_unicode_code_point_offsets() -> None:
    text = "😀 Prefix\n\nA transaction\n  is atomic.\nSuffix"
    start, end = quote_span(text, "A transaction is atomic.")
    assert start == 10
    assert text[start:end] == "A transaction\n  is atomic."


@pytest.mark.parametrize("quote", ["", "missing", "same"])
def test_empty_missing_or_ambiguous_quotes_are_rejected(quote: str) -> None:
    with pytest.raises(ValueError):
        quote_span("same\ntext\nsame", quote)
