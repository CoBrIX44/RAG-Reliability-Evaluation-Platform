"""Rank-order context packing with whole, source-linked prefixes and an exact text budget."""

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from rag_core.chunking import CanonicalSpan, Chunk, OffsetTokenizer, checked_offsets

PACKING_VERSION = "ranked-prefix-v1"
SEPARATOR = "\n\n"


class PackedContext(BaseModel):
    model_config = ConfigDict(frozen=True)
    version: str = PACKING_VERSION
    tokenizer: str
    token_budget: int
    token_count: int
    text: str
    passages: tuple[Chunk, ...]
    truncated_chunk_ids: tuple[str, ...]
    omitted_chunk_ids: tuple[str, ...]


def prefix(passage: Chunk, end: int, tokenizer: OffsetTokenizer) -> Chunk | None:
    spans = tuple(
        CanonicalSpan(
            section_id=span.section_id,
            start_offset=span.start_offset,
            end_offset=span.start_offset + min(end, span.text_end) - span.text_start,
            text_start=span.text_start,
            text_end=min(end, span.text_end),
        )
        for span in passage.spans
        if end > span.text_start
    )
    if not spans:
        return None
    return passage.model_copy(
        update={
            "text": passage.text[:end],
            "token_count": tokenizer.count(passage.text[:end]),
            "spans": spans,
        }
    )


def pack_context(
    passages: Sequence[Chunk], tokenizer: OffsetTokenizer, token_budget: int
) -> PackedContext:
    if not 0 <= token_budget <= 131_072:
        raise ValueError("Context token budget must be between 0 and 131072.")
    if len(passages) > 100:
        raise ValueError("Context packing accepts at most 100 ranked passages.")
    delivered: list[Chunk] = []
    truncated: list[str] = []
    omitted: list[str] = []
    seen: set[str] = set()
    text = ""
    exhausted = token_budget == 0
    for passage in passages:
        key = str(passage.id)
        if key in seen or exhausted:
            omitted.append(key)
            continue
        seen.add(key)
        joiner = SEPARATOR if delivered else ""
        if tokenizer.count(text + joiner + passage.text) <= token_budget:
            delivered.append(passage)
            text += joiner + passage.text
            continue
        # Re-tokenization is not assumed additive or monotonic. Evaluate candidate prefixes
        # from longest to shortest; the first fitting one maximizes retained source text.
        ends = sorted({end for _, end in checked_offsets(tokenizer, passage.text)}, reverse=True)
        fitted: Chunk | None = None
        for end in ends:
            candidate = text + joiner + passage.text[:end]
            if tokenizer.count(candidate) <= token_budget:
                fitted = prefix(passage, end, tokenizer)
                if fitted:
                    text = candidate
                    break
        if fitted:
            delivered.append(fitted)
            truncated.append(key)
        else:
            omitted.append(key)
        # Rank-order packing stops after the first passage that does not fit completely.
        exhausted = True
    return PackedContext(
        tokenizer=tokenizer.identity,
        token_budget=token_budget,
        token_count=tokenizer.count(text),
        text=text,
        passages=tuple(delivered),
        truncated_chunk_ids=tuple(truncated),
        omitted_chunk_ids=tuple(omitted),
    )
