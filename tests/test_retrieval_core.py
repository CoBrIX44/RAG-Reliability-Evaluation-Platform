"""Hand-computed fixtures; no research labels, inference, or empirical performance claims."""

import re
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from rag_core.chunking import (
    CanonicalSection,
    CanonicalSpan,
    Chunk,
    ChunkConfig,
    build_chunks,
    checked_offsets,
    variant_fingerprint,
)
from rag_core.context import pack_context
from rag_core.dataset_schemas import QuestionInput
from rag_core.retrieval_evaluation import score_retrieval


class WordTokenizer:
    """Independent software fixture tokenizer; never presented as a model tokenizer."""

    identity = "software-fixture-whitespace-v1"

    def offsets(self, text: str) -> list[tuple[int, int]]:
        return [(match.start(), match.end()) for match in re.finditer(r"\S+", text)]

    def count(self, text: str) -> int:
        return len(self.offsets(text))


TOKENIZER = WordTokenizer()
SECTION_A = UUID(int=1)
SECTION_B = UUID(int=2)
REVISION = UUID(int=3)
VARIANT = UUID(int=4)


def section(text: str, ordinal: int = 0, section_id: UUID = SECTION_A) -> CanonicalSection:
    return CanonicalSection(section_id, REVISION, ordinal, text)


def passage(start: int, end: int, section_id: UUID = SECTION_A) -> Chunk:
    text = "x" * (end - start)
    return Chunk(
        id=uuid4(),
        ordinal=0,
        text=text,
        token_count=1,
        spans=(
            CanonicalSpan(
                section_id=section_id,
                start_offset=start,
                end_offset=end,
                text_start=0,
                text_end=len(text),
            ),
        ),
    )


def gold(*alternatives: list[tuple[UUID, int, int]], answerable: bool = True) -> QuestionInput:
    return QuestionInput(
        text="Hand-computed software fixture question",
        answerable=answerable,
        required_facts=["Fact A"] if answerable else [],
        evidence_groups=[
            {
                "fact_index": 0,
                "alternatives": [
                    {
                        "spans": [
                            {"section_id": sid, "start_offset": start, "end_offset": end}
                            for sid, start, end in spans
                        ]
                    }
                    for spans in alternatives
                ],
            }
        ]
        if answerable
        else [],
    )


def test_fixed_crosses_sections_and_preserves_unicode_lineage() -> None:
    sections = [section("one \U0001f9ea two"), section("three four", 1, SECTION_B)]
    chunks = build_chunks(sections, ChunkConfig(strategy="fixed", max_tokens=4), TOKENIZER, VARIANT)
    assert [chunk.text for chunk in chunks] == ["one \U0001f9ea two\n\nthree ", "four"]
    assert [span.section_id for span in chunks[0].spans] == [SECTION_A, SECTION_B]
    sources = {item.id: item.text for item in sections}
    for chunk in chunks:
        assert chunk.token_count <= 4
        for span in chunk.spans:
            assert (
                chunk.text[span.text_start : span.text_end]
                == sources[span.section_id][span.start_offset : span.end_offset]
            )


def test_section_windows_never_cross_sections_and_split_oversized_sections() -> None:
    chunks = build_chunks(
        [section("a b c d e"), section("f g", 1, SECTION_B)],
        ChunkConfig(max_tokens=2),
        TOKENIZER,
        VARIANT,
    )
    assert [chunk.text for chunk in chunks] == ["a b ", "c d ", "e", "f g"]
    assert all(len(chunk.spans) == 1 for chunk in chunks)


def test_fixed_does_not_cross_documents_and_output_is_order_independent() -> None:
    a, b = section("a b"), CanonicalSection(SECTION_B, UUID(int=9), 0, "c d")
    config = ChunkConfig(strategy="fixed", max_tokens=20)
    first = build_chunks([a, b], config, TOKENIZER, VARIANT)
    assert first == build_chunks([b, a], config, TOKENIZER, VARIANT)
    assert [chunk.text for chunk in first] == ["a b", "c d"]


def test_overlap_does_not_omit_text_and_has_distinct_stable_chunk_ids() -> None:
    chunks = build_chunks(
        [section("a b c d e")], ChunkConfig(max_tokens=3, overlap_tokens=1), TOKENIZER, VARIANT
    )
    assert [chunk.text for chunk in chunks] == ["a b c ", "c d e"]
    assert [(chunk.spans[0].start_offset, chunk.spans[0].end_offset) for chunk in chunks] == [
        (0, 6),
        (4, 9),
    ]
    assert len({chunk.id for chunk in chunks}) == 2


@pytest.mark.parametrize("text", ["", "   \n", " leading trailing ", "\U0001f9ea\nSQL\n"])
def test_empty_whitespace_and_edge_text(text: str) -> None:
    chunks = build_chunks([section(text)], ChunkConfig(max_tokens=20), TOKENIZER, VARIANT)
    assert "".join(chunk.text for chunk in chunks) == text


@pytest.mark.parametrize(
    "kwargs", [{"max_chunks": 1}, {"max_characters": 2}, {"max_chunk_characters": 1}]
)
def test_build_resource_bounds(kwargs: dict[str, int]) -> None:
    with pytest.raises(ValueError, match="limit"):
        build_chunks(
            [section("one two three")], ChunkConfig(max_tokens=1), TOKENIZER, VARIANT, **kwargs
        )


def test_duplicate_sections_and_ordinals_rejected() -> None:
    with pytest.raises(ValueError, match="IDs"):
        build_chunks([section("a"), section("b")], ChunkConfig(), TOKENIZER, VARIANT)
    with pytest.raises(ValueError, match="ordinals"):
        build_chunks(
            [section("a"), section("b", section_id=SECTION_B)], ChunkConfig(), TOKENIZER, VARIANT
        )


@pytest.mark.parametrize("limit,overlap", [(0, 0), (2, 2), (2, 3), (4097, 0), (3, -1)])
def test_config_rejects_invalid_budgets(limit: int, overlap: int) -> None:
    with pytest.raises(ValidationError):
        ChunkConfig(max_tokens=limit, overlap_tokens=overlap)


def test_variant_identity_tracks_corpus_tokenizer_and_configuration() -> None:
    fingerprint = variant_fingerprint("corpus-a", ChunkConfig(), TOKENIZER)
    assert fingerprint == variant_fingerprint("corpus-a", ChunkConfig(), TOKENIZER)
    assert fingerprint != variant_fingerprint("corpus-b", ChunkConfig(), TOKENIZER)
    assert fingerprint != variant_fingerprint("corpus-a", ChunkConfig(strategy="fixed"), TOKENIZER)
    alternate = WordTokenizer()
    alternate.identity = "different-fixture-tokenizer"
    assert fingerprint != variant_fingerprint("corpus-a", ChunkConfig(), alternate)


@pytest.mark.parametrize(
    "offsets", [[(-1, 2)], [(0, 5)], [(2, 1)], [(0, 0)], [(1, 2), (0, 1)], [(0, 3), (1, 2)]]
)
def test_invalid_tokenizer_offsets_rejected(offsets: list[tuple[int, int]]) -> None:
    class BrokenTokenizer(WordTokenizer):
        def offsets(self, text: str) -> list[tuple[int, int]]:
            return offsets

    with pytest.raises(ValueError, match="offsets"):
        checked_offsets(BrokenTokenizer(), "abc")


def test_union_coverage_crosses_chunks_but_precision_requires_full_span() -> None:
    result = score_retrieval(gold([(SECTION_A, 0, 10)]), [passage(0, 5), passage(5, 10)])
    assert result.recall == 1
    assert result.precision == 0
    assert result.covered_group_count == 1
    assert result.returned_count == 2


def test_overlapping_duplicates_do_not_inflate_recall_and_gaps_do_not_cover() -> None:
    question = gold([(SECTION_A, 0, 10)])
    assert score_retrieval(question, [passage(0, 10)] * 3).recall == 1
    assert score_retrieval(question, [passage(0, 4), passage(5, 10)]).recall == 0


def test_alternative_requires_all_its_spans_but_any_complete_alternative_suffices() -> None:
    question = gold([(SECTION_A, 0, 5), (SECTION_B, 0, 5)], [(SECTION_A, 10, 15)])
    assert score_retrieval(question, [passage(0, 5)]).recall == 0
    assert score_retrieval(question, [passage(0, 5), passage(0, 5, SECTION_B)]).recall == 1
    result = score_retrieval(question, [passage(10, 15), passage(30, 35)])
    assert result.recall == 1 and result.precision == 0.5


def test_multiple_fact_groups_have_independent_denominators() -> None:
    question = gold([(SECTION_A, 0, 5)])
    data = question.model_dump()
    data["required_facts"] = ["Fact A", "Fact B"]
    data["evidence_groups"].append(
        {
            "fact_index": 1,
            "alternatives": [
                {
                    "spans": [
                        {
                            "section_id": SECTION_B,
                            "start_offset": 0,
                            "end_offset": 5,
                        }
                    ]
                }
            ],
        }
    )
    result = score_retrieval(QuestionInput.model_validate(data), [passage(0, 5)])
    assert result.recall == 0.5 and result.precision == 1
    assert result.covered_fact_indices == (0,)
    assert result.required_group_count == 2


def test_empty_unanswerable_and_missing_gold_have_distinct_states() -> None:
    empty = score_retrieval(gold([(SECTION_A, 0, 5)]), [])
    assert empty.precision == 0 and empty.recall == 0 and empty.state == "scored"
    unanswerable = score_retrieval(gold(answerable=False), [passage(0, 5)])
    assert not unanswerable.applicable and unanswerable.precision is None
    assert unanswerable.recall is None and unanswerable.required_group_count is None
    missing = score_retrieval(QuestionInput(text="Unannotated candidate"), [])
    assert missing.applicable and missing.recall is None
    assert missing.state == "unavailable_annotations"


def test_packing_truncates_source_spans_and_changes_evidence_coverage() -> None:
    chunks = build_chunks([section("a b c d")], ChunkConfig(), TOKENIZER, VARIANT)
    question = gold([(SECTION_A, 4, 7)])
    packed = pack_context(chunks, TOKENIZER, 2)
    assert packed.text == "a b" and packed.token_count == 2
    assert packed.truncated_chunk_ids == (str(chunks[0].id),)
    assert packed.passages[0].spans[0].end_offset == 3
    assert score_retrieval(question, chunks).recall == 1
    assert score_retrieval(question, packed.passages).recall == 0


def test_packing_preserves_order_skips_duplicate_ids_and_records_omissions() -> None:
    chunks = build_chunks([section("a b c d e")], ChunkConfig(max_tokens=2), TOKENIZER, VARIANT)
    packed = pack_context([chunks[0], chunks[0], *chunks[1:]], TOKENIZER, 3)
    assert [item.id for item in packed.passages] == [chunks[0].id, chunks[1].id]
    assert packed.token_count == 3
    assert packed.omitted_chunk_ids == (str(chunks[0].id), str(chunks[2].id))
    assert packed.truncated_chunk_ids == (str(chunks[1].id),)


def test_zero_budget_delivers_no_evidence() -> None:
    chunks = build_chunks([section("a b")], ChunkConfig(), TOKENIZER, VARIANT)
    packed = pack_context(chunks, TOKENIZER, 0)
    assert packed.text == "" and not packed.passages and packed.token_count == 0
    assert packed.omitted_chunk_ids == (str(chunks[0].id),)


def test_packing_accounts_for_separators_and_retokenizes_combined_text() -> None:
    class SeparatorTokenizer(WordTokenizer):
        def count(self, text: str) -> int:
            return super().count(text) + text.count("\n\n")

    tokenizer = SeparatorTokenizer()
    chunks = build_chunks([section("a b c d")], ChunkConfig(max_tokens=2), tokenizer, VARIANT)
    packed = pack_context(chunks, tokenizer, 3)
    assert packed.text == chunks[0].text
    assert len(packed.passages) == 1 and packed.token_count == 2
    assert packed.omitted_chunk_ids == (str(chunks[1].id),)
