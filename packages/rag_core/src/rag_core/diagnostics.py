"""Bounded diagnostic projections of frozen questions and latest explicit-source assessments."""

from typing import Any, Literal
from uuid import UUID

from sqlalchemy import Engine, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from rag_core.errors import PlatformError
from rag_core.evaluation_models import AnswerEvaluation
from rag_core.run_models import QuestionResult, Run

ISSUES = (
    "execution_error",
    "retrieval_miss",
    "context_loss",
    "quality_issue",
    "judge_error",
    "unknown_citations",
    "no_citations",
    "truncated_answer",
    "false_abstention",
    "unavailable_assessment",
    "missing_observation",
)


def diagnostics(
    engine: Engine,
    run_id: UUID,
    *,
    source: Literal["human", "model"] = "human",
    topic: str = "",
    difficulty: str = "",
    issue: str = "",
    limit: int = 100,
    cursor: int = 0,
) -> dict[str, Any]:
    if issue and issue not in ISSUES:
        raise PlatformError("invalid_issue", "Choose a supported diagnostic category.")
    with Session(engine) as session:
        run = session.get(Run, run_id)
        if run is None:
            raise PlatformError("run_not_found", "Run not found.", 404)
        manifest: dict[str, Any] = run.manifest
        rows = session.execute(
            select(
                QuestionResult.id,
                QuestionResult.question_id,
                QuestionResult.repeat,
                QuestionResult.state,
                QuestionResult.trace["retrieval_scores"].label("retrieval"),
                QuestionResult.trace["context_scores"].label("context"),
                QuestionResult.trace["error"].label("error"),
                QuestionResult.trace["generation"]["finish_reason"].as_string().label("finish"),
                QuestionResult.trace["generation"]["abstained"].as_boolean().label("abstained"),
                QuestionResult.trace["generation"]["citations"].label("citations"),
                QuestionResult.trace["generation"]["unknown_citations"].label("unknown_citations"),
            ).where(QuestionResult.run_id == run_id)
        ).all()
        evaluations = session.execute(
            select(
                AnswerEvaluation.id,
                AnswerEvaluation.result_id,
                AnswerEvaluation.state,
                AnswerEvaluation.output["metrics"].label("metrics"),
            )
            .join(QuestionResult, QuestionResult.id == AnswerEvaluation.result_id)
            .where(QuestionResult.run_id == run_id, AnswerEvaluation.kind == source)
            .ext(distinct_on(AnswerEvaluation.result_id))
            .order_by(
                AnswerEvaluation.result_id,
                AnswerEvaluation.created_at.desc(),
                AnswerEvaluation.id.desc(),
            )
        ).all()
    selected = {row.result_id: row for row in evaluations}
    results = {(str(row.question_id), row.repeat): row for row in rows}
    items = []
    for frozen in manifest["questions"]:
        q = frozen["content"]
        for repeat in range(int(manifest["config"]["repeats"])):
            row = results.get((frozen["id"], repeat))
            flags = []
            assessment = selected.get(row.id) if row else None
            if not row:
                flags.append("missing_observation")
            else:
                if row.state == "failed":
                    flags.append("execution_error")
                before, after = (
                    (row.retrieval or {}).get("recall"),
                    (row.context or {}).get("recall"),
                )
                if q["answerable"] and before is not None and before < 1:
                    flags.append("retrieval_miss")
                if before is not None and after is not None and after < before:
                    flags.append("context_loss")
                if assessment and assessment.state == "failed":
                    flags.append("judge_error")
                elif not assessment or assessment.state != "completed":
                    flags.append("unavailable_assessment")
                if assessment and any(
                    score.get("value") is not None and score["value"] < 1
                    for score in (assessment.metrics or {}).values()
                ):
                    flags.append("quality_issue")
                if row.unknown_citations:
                    flags.append("unknown_citations")
                if row.state == "succeeded" and not row.abstained and not row.citations:
                    flags.append("no_citations")
                if row.finish == "length":
                    flags.append("truncated_answer")
                if q["answerable"] and row.abstained:
                    flags.append("false_abstention")
            items.append(
                {
                    "question_id": frozen["id"],
                    "question_revision": frozen["revision"],
                    "question": q["text"],
                    "topic": q["topic"],
                    "difficulty": q["difficulty"],
                    "repeat": repeat,
                    "result_id": str(row.id) if row else None,
                    "state": row.state if row else "unavailable",
                    "issues": flags,
                    "error": row.error if row else None,
                    "assessment_id": str(assessment.id) if assessment else None,
                }
            )
    filtered = [
        item
        for item in items
        if (not topic or item["topic"] == topic)
        and (not difficulty or item["difficulty"] == difficulty)
        and (not issue or issue in item["issues"])
    ]
    return {
        "run_id": str(run_id),
        "purpose": manifest["purpose"],
        "source": source,
        "topics": sorted({item["topic"] for item in items}),
        "difficulties": sorted({item["difficulty"] for item in items}),
        "issue_counts": {name: sum(name in item["issues"] for item in filtered) for name in ISSUES},
        "total_count": len(items),
        "filtered_count": len(filtered),
        "items": filtered[cursor : cursor + limit],
        "next_cursor": str(cursor + limit) if cursor + limit < len(filtered) else None,
        "policy": "diagnostic-signals-v1",
        "limitations": (
            "Citation syntax and missing assessments are diagnostic signals, "
            "not proof of an incorrect answer."
        ),
    }
