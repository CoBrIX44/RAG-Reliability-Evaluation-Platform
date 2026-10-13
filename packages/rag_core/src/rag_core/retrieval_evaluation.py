"""Independent canonical evidence coverage; known evidence is not exhaustive relevance."""

from collections.abc import Sequence
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from rag_core.chunking import CanonicalSpan, Chunk
from rag_core.dataset_schemas import EvidenceSpan, QuestionInput

EVIDENCE_SCORING_VERSION = "canonical-group-union-v1"


class RetrievalScores(BaseModel):
    model_config = ConfigDict(frozen=True)
    version: str = EVIDENCE_SCORING_VERSION
    applicable: bool
    state: str
    precision: float | None
    recall: float | None
    returned_count: int
    relevant_passage_count: int | None
    covered_group_count: int | None
    required_group_count: int | None
    covered_fact_indices: tuple[int, ...] = ()


def merged_coverage(spans: Sequence[CanonicalSpan]) -> dict[UUID, list[tuple[int, int]]]:
    grouped: dict[UUID, list[tuple[int, int]]] = {}
    for span in spans:
        grouped.setdefault(span.section_id, []).append((span.start_offset, span.end_offset))
    coverage: dict[UUID, list[tuple[int, int]]] = {}
    for section_id, intervals in grouped.items():
        merged: list[tuple[int, int]] = []
        for start, end in sorted(intervals):
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
            else:
                merged.append((start, end))
        coverage[section_id] = merged
    return coverage


def contains(coverage: dict[UUID, list[tuple[int, int]]], span: EvidenceSpan) -> bool:
    return any(
        start <= span.start_offset and end >= span.end_offset
        for start, end in coverage.get(span.section_id, [])
    )


def score_retrieval(question: QuestionInput, passages: Sequence[Chunk]) -> RetrievalScores:
    if not question.answerable:
        return RetrievalScores(
            applicable=False,
            state="not_applicable",
            precision=None,
            recall=None,
            returned_count=len(passages),
            relevant_passage_count=None,
            covered_group_count=None,
            required_group_count=None,
        )
    groups = question.evidence_groups
    if not groups or len(groups) != len(question.required_facts):
        return RetrievalScores(
            applicable=True,
            state="unavailable_annotations",
            precision=None,
            recall=None,
            returned_count=len(passages),
            relevant_passage_count=None,
            covered_group_count=None,
            required_group_count=len(question.required_facts),
        )
    coverage = merged_coverage([span for passage in passages for span in passage.spans])
    covered = tuple(
        sorted(
            group.fact_index
            for group in groups
            if any(
                all(contains(coverage, span) for span in alternative.spans)
                for alternative in group.alternatives
            )
        )
    )
    accepted = [span for group in groups for alt in group.alternatives for span in alt.spans]
    relevant = sum(
        any(contains(merged_coverage(passage.spans), span) for span in accepted)
        for passage in passages
    )
    return RetrievalScores(
        applicable=True,
        state="scored",
        precision=relevant / len(passages) if passages else 0.0,
        recall=len(covered) / len(groups),
        returned_count=len(passages),
        relevant_passage_count=relevant,
        covered_group_count=len(covered),
        required_group_count=len(groups),
        covered_fact_indices=covered,
    )
