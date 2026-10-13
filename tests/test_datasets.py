import json
from uuid import uuid4

import pytest
from pydantic import ValidationError
from rag_core.dataset_schemas import QuestionInput
from rag_core.datasets import ImportErrorDetail, normalized_question, parse_jsonl


def test_jsonl_reports_physical_lines_and_has_no_partial_result() -> None:
    raw = b'{"text":"Valid candidate"}\n\n{"text":}\n'
    with pytest.raises(ImportErrorDetail) as error:
        parse_jsonl(raw, 10)
    assert error.value.field_errors[0]["line"] == 3


def test_review_requires_a_named_reviewer() -> None:
    with pytest.raises(ValidationError, match="person"):
        QuestionInput(text="Question?", review_status="reviewed")


def test_unanswerable_question_has_no_positive_evidence() -> None:
    with pytest.raises(ValidationError, match="Unanswerable"):
        QuestionInput(text="Unknown?", answerable=False, required_facts=["Unsupported fact"])


def test_candidates_are_not_automatically_reviewed_and_import_is_bounded() -> None:
    value = parse_jsonl(b'{"text":"Candidate?"}', 10)[0]
    assert value.review_status == "candidate" and value.reviewer == ""
    with pytest.raises(ImportErrorDetail, match="errors"):
        parse_jsonl(b'{"text":"A"}\n{"text":"B"}', 1)


def test_invalid_fact_and_span_indices_are_rejected() -> None:
    with pytest.raises(ValidationError, match="distinct required fact"):
        QuestionInput.model_validate(
            {
                "text": "Question?",
                "required_facts": ["Fact"],
                "evidence_groups": [
                    {
                        "fact_index": 2,
                        "alternatives": [
                            {
                                "spans": [
                                    {"section_id": str(uuid4()), "start_offset": 0, "end_offset": 1}
                                ]
                            }
                        ],
                    }
                ],
            }
        )


def test_interchange_round_trip_and_normalized_duplicate_keys() -> None:
    original = QuestionInput(text="Unicode café?", answerable=False, reference_answer="Abstain.")
    assert (
        parse_jsonl((json.dumps(original.model_dump(mode="json")) + "\n").encode(), 10)[0]
        == original
    )
    assert normalized_question("  Café? ") == normalized_question("CAFE\u0301?")
