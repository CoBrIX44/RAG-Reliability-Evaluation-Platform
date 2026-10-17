"""Independently constructed curation fixtures, never research labels."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from rag_core.benchmark_audit import audit_curation
from rag_core.dataset_schemas import QuestionInput, QuestionView
from rag_core.schemas import SectionView


def inputs() -> tuple[list[QuestionView], list[SectionView]]:
    dataset_id, revision_id = uuid4(), uuid4()
    sections = [
        SectionView(
            id=uuid4(),
            revision_id=revision_id,
            ordinal=i,
            heading_path=[],
            text="Synthetic canonical fact.",
            start_offset=0,
            end_offset=25,
            source={"format": "text"},
        )
        for i in range(2)
    ]
    questions = [
        QuestionView(
            id=uuid4(),
            dataset_id=dataset_id,
            revision=1,
            content=QuestionInput(
                text=f"Synthetic question {i}?",
                reference_answer="Synthetic fact.",
                required_facts=["Synthetic fact."],
                evidence_groups=[
                    {
                        "fact_index": 0,
                        "alternatives": [
                            {
                                "spans": [
                                    {
                                        "section_id": s.id,
                                        "start_offset": 0,
                                        "end_offset": len(s.text),
                                    }
                                ]
                            }
                        ],
                    }
                ],
                topic="synthetic",
                difficulty="medium",
                split="development",
                split_group=f"provisional-{i}",
                review_status="reviewed",
                reviewer="Synthetic reviewer",
            ),
            reviewed_at=datetime(2026, 1, 1, tzinfo=UTC),
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        for i, s in enumerate(sections)
    ]
    return questions, sections


def test_conservative_document_group_detects_leakage_across_different_sections() -> None:
    questions, sections = inputs()
    questions[1].content.split = "test"
    result = audit_curation(
        questions, sections, allowed_revision_ids={sections[0].revision_id}, minimum_questions=2
    )
    assert result.reviewed_count == 2
    assert len(result.source_groups) == 1
    assert result.source_groups[0].assigned_splits == ["development", "test"]
    assert {i.code for i in result.issues} == {"source_group_leakage"}
    assert questions[1].content.split == "test"  # The audit does not rewrite labels or splits.


def test_review_reference_span_and_sample_gaps_are_independent() -> None:
    questions, sections = inputs()
    q = questions[0]
    q.content.review_status, q.content.reviewer, q.reviewed_at = "candidate", "", None
    q.content.reference_answer, q.content.split = "", "unassigned"
    q.content.evidence_groups[0].alternatives[0].spans[0].end_offset = 999
    result = audit_curation(questions, sections, allowed_revision_ids={sections[0].revision_id})
    assert result.reviewed_count == 1 and result.unassigned_count == 1
    assert {i.code for i in result.issues} == {
        "review_missing",
        "reference_missing",
        "split_unassigned",
        "evidence_bounds",
        "sample_target_unmet",
    }
    assert not result.automated_checks_pass


def test_normalized_duplicates_and_foreign_lineage_never_pass() -> None:
    questions, sections = inputs()
    questions[1].content.text = "  SYNTHETIC   QUESTION 0? "
    result = audit_curation(
        questions, sections, allowed_revision_ids={uuid4()}, minimum_questions=2
    )
    assert {i.code for i in result.issues} == {"duplicate_question", "evidence_lineage"}
    assert len(result.source_groups) == 1


def test_automated_pass_still_discloses_manual_checks_and_rejects_duplicate_inputs() -> None:
    questions, sections = inputs()
    result = audit_curation(
        questions, sections, allowed_revision_ids={sections[0].revision_id}, minimum_questions=2
    )
    assert result.automated_checks_pass and result.manual_checks_required
    with pytest.raises(ValueError, match="duplicate logical"):
        audit_curation(questions * 2, sections, allowed_revision_ids={sections[0].revision_id})
    with pytest.raises(ValueError, match="bounded"):
        audit_curation(questions, sections, allowed_revision_ids=set(), minimum_questions=0)


def test_ai_reviews_are_counted_separately_from_human_reviews() -> None:
    questions, sections = inputs()
    questions[1].content.review_source = "ai"
    questions[1].content.reviewer = "Synthetic AI reviewer"
    result = audit_curation(
        questions, sections, allowed_revision_ids={sections[0].revision_id}, minimum_questions=2
    )
    assert result.reviewed_count == 2
    assert result.human_reviewed_count == 1
    assert result.ai_reviewed_count == 1
