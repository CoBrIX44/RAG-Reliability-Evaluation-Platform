"""Token-bounded chunks with exact canonical code-point lineage."""

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field, model_validator

CHUNKING_VERSION = "canonical-token-windows-v1"


class OffsetTokenizer(Protocol):
    identity: str

    def offsets(self, text: str) -> list[tuple[int, int]]: ...

    def count(self, text: str) -> int: ...


class ChunkConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    strategy: Literal["fixed", "section"] = "section"
    max_tokens: int = Field(default=256, ge=1, le=4096)
    overlap_tokens: int = Field(default=0, ge=0, le=1024)

    @model_validator(mode="after")
    def validate_overlap(self) -> "ChunkConfig":
        if self.overlap_tokens >= self.max_tokens:
            raise ValueError("Overlap must be smaller than the chunk token limit.")
        return self


class CanonicalSpan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    section_id: UUID
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    # Position in the chunk text, including separators between source sections.
    text_start: int = Field(ge=0)
    text_end: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_lengths(self) -> "CanonicalSpan":
        if (
            self.end_offset <= self.start_offset
            or self.text_end <= self.text_start
            or self.end_offset - self.start_offset != self.text_end - self.text_start
        ):
            raise ValueError("Source and chunk spans must have the same positive length.")
        return self


@dataclass(frozen=True)
class CanonicalSection:
    id: UUID
    revision_id: UUID
    ordinal: int
    text: str


class Chunk(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: UUID
    ordinal: int = Field(ge=0)
    text: str
    token_count: int = Field(ge=0)
    spans: tuple[CanonicalSpan, ...]

    @model_validator(mode="after")
    def validate_lineage(self) -> "Chunk":
        if not self.spans or not self.text:
            raise ValueError("A chunk requires nonempty source lineage and text.")
        previous_end = 0
        for span in self.spans:
            if span.text_start < previous_end or span.text_end > len(self.text):
                raise ValueError("Chunk lineage must be ordered, disjoint, and within its text.")
            previous_end = span.text_end
        return self


def variant_fingerprint(corpus_hash: str, config: ChunkConfig, tokenizer: OffsetTokenizer) -> str:
    payload = {
        "corpus_hash": corpus_hash,
        "chunking_version": CHUNKING_VERSION,
        "config": config.model_dump(),
        "tokenizer": tokenizer.identity,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def checked_offsets(tokenizer: OffsetTokenizer, text: str) -> list[tuple[int, int]]:
    offsets = tokenizer.offsets(text)
    previous_start = -1
    previous_end = -1
    for start, end in offsets:
        if not (0 <= start < end <= len(text)) or start < previous_start or end < previous_end:
            raise ValueError("Tokenizer returned invalid canonical code-point offsets.")
        previous_start, previous_end = start, end
    return offsets


def token_windows(
    text: str, tokenizer: OffsetTokenizer, config: ChunkConfig
) -> list[tuple[int, int]]:
    """Cover normalized text, retain whitespace, and recheck each independently encoded chunk."""
    offsets = checked_offsets(tokenizer, text)
    if not text:
        return []
    if not offsets:
        return [(0, len(text))]
    windows: list[tuple[int, int]] = []
    first = 0
    while first < len(offsets):
        last = min(first + config.max_tokens, len(offsets))
        start = 0 if first == 0 else offsets[first][0]
        while last > first:
            end = len(text) if last == len(offsets) else offsets[last][0]
            if end > start and tokenizer.count(text[start:end]) <= config.max_tokens:
                break
            last -= 1
        if last == first:
            raise ValueError("Tokenizer cannot form a nonempty chunk within the configured budget.")
        windows.append((start, end))
        if last == len(offsets):
            break
        # Never restart at the same offset: overlapping subword offsets must not loop forever.
        next_first = max(first + 1, last - config.overlap_tokens)
        while next_first < len(offsets) and offsets[next_first][0] <= start:
            next_first += 1
        if next_first >= len(offsets):
            raise ValueError("Tokenizer offsets cannot advance without dropping source text.")
        first = next_first
    return windows


def build_chunks(
    sections: Sequence[CanonicalSection],
    config: ChunkConfig,
    tokenizer: OffsetTokenizer,
    variant_id: UUID,
    *,
    max_chunks: int = 100_000,
    max_characters: int = 20_000_000,
    max_chunk_characters: int = 100_000,
) -> list[Chunk]:
    """Fixed windows cross sections within a document; section windows retain section boundaries."""
    if len({section.id for section in sections}) != len(sections):
        raise ValueError("Canonical section IDs must be unique.")
    if sum(len(section.text) + 2 for section in sections) > max_characters:
        raise ValueError("Corpus exceeds the bounded chunk-build character limit.")
    groups: dict[UUID, list[CanonicalSection]] = {}
    for section in sections:
        groups.setdefault(section.revision_id, []).append(section)
    chunks: list[Chunk] = []
    for revision_id in sorted(groups, key=str):
        ordered = sorted(groups[revision_id], key=lambda item: item.ordinal)
        if len({item.ordinal for item in ordered}) != len(ordered):
            raise ValueError("Section ordinals must be unique within a document revision.")
        units = [[section] for section in ordered] if config.strategy == "section" else [ordered]
        for unit in units:
            text = "\n\n".join(section.text for section in unit)
            locations: list[tuple[CanonicalSection, int, int]] = []
            position = 0
            for section in unit:
                locations.append((section, position, position + len(section.text)))
                position += len(section.text) + 2
            for start, end in token_windows(text, tokenizer, config):
                if end - start > max_chunk_characters:
                    raise ValueError(
                        "A chunk exceeds the character limit; inspect tokenizer coverage."
                    )
                spans = tuple(
                    CanonicalSpan(
                        section_id=section.id,
                        start_offset=max(start, left) - left,
                        end_offset=min(end, right) - left,
                        text_start=max(start, left) - start,
                        text_end=min(end, right) - start,
                    )
                    for section, left, right in locations
                    if max(start, left) < min(end, right)
                )
                if not spans:
                    continue
                ordinal = len(chunks)
                chunks.append(
                    Chunk(
                        id=uuid5(variant_id, str(ordinal)),
                        ordinal=ordinal,
                        text=text[start:end],
                        token_count=tokenizer.count(text[start:end]),
                        spans=spans,
                    )
                )
                if len(chunks) > max_chunks:
                    raise ValueError("Corpus exceeds the bounded chunk-count limit.")
    return chunks
