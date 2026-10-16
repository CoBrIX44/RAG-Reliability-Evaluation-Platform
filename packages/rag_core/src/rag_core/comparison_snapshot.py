"""Small immutable projections of runs, explicit evaluation selections and usage evidence."""

import math
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from rag_core.answer_evaluation import RUBRIC_VERSION
from rag_core.comparison_analysis import (
    METRICS,
    Datum,
    FrozenQuestion,
    Observation,
    RunSample,
    timing_summary,
)
from rag_core.evaluation_models import AnswerEvaluation
from rag_core.run_models import QuestionResult, Run, RunAttempt
from rag_core.runs import digest


def valid_timings(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    return {
        key: float(number)
        for key, number in value.items()
        if isinstance(number, (int, float))
        and not isinstance(number, bool)
        and math.isfinite(number)
        and number >= 0
    }


def usage(rows: Sequence[dict[str, Any] | None], potential_unknown: int) -> dict[str, Any]:
    valid = [
        row
        for row in rows
        if row is not None
        and all(
            isinstance(row.get(key), int) and not isinstance(row[key], bool) and row[key] >= 0
            for key in ("input_tokens", "output_tokens")
        )
    ]
    return {
        "recorded_call_count": len(valid),
        "input_tokens": sum(row["input_tokens"] for row in valid) if valid else None,
        "output_tokens": sum(row["output_tokens"] for row in valid) if valid else None,
        "potential_unobserved_call_count": potential_unknown + len(rows) - len(valid),
        "policy": "available-attempt-usage-no-inferred-zero-v1",
    }


def snapshot_run(session: Session, run: Run, source: str, cutoff: datetime) -> RunSample:
    manifest: dict[str, Any] = run.manifest
    questions = [
        FrozenQuestion(
            id=q["id"],
            revision=q["revision"],
            content_hash=digest(q["content"]),
            text=q["content"]["text"],
            group=q["content"]["split_group"],
            answerable=q["content"]["answerable"],
            topic=q["content"]["topic"],
            difficulty=q["content"]["difficulty"],
        )
        for q in manifest["questions"]
    ]
    rows = session.execute(
        select(
            QuestionResult.id,
            QuestionResult.question_id,
            QuestionResult.repeat,
            QuestionResult.state,
            QuestionResult.trace["retrieval_scores"].label("retrieval"),
            QuestionResult.trace["context_scores"].label("context"),
            QuestionResult.trace["timings"].label("timings"),
            func.coalesce(
                QuestionResult.trace["retrieval"]["pipeline"]["timings"],
                QuestionResult.trace["retrieval_candidates"]["pipeline"]["timings"],
            ).label("pipeline_timings"),
        )
        .where(QuestionResult.run_id == run.id)
        .order_by(QuestionResult.question_id, QuestionResult.repeat)
    ).all()
    selected = session.execute(
        select(
            AnswerEvaluation.id,
            AnswerEvaluation.result_id,
            AnswerEvaluation.state,
            AnswerEvaluation.manifest_hash,
            AnswerEvaluation.manifest["rubric"].label("rubric"),
            AnswerEvaluation.manifest["judge"].label("judge"),
            AnswerEvaluation.reviewer,
            AnswerEvaluation.output["metrics"].label("metrics"),
        )
        .join(QuestionResult, QuestionResult.id == AnswerEvaluation.result_id)
        .where(
            QuestionResult.run_id == run.id,
            AnswerEvaluation.kind == source,
            AnswerEvaluation.created_at <= cutoff,
        )
        .ext(distinct_on(AnswerEvaluation.result_id))
        .order_by(
            AnswerEvaluation.result_id,
            AnswerEvaluation.created_at.desc(),
            AnswerEvaluation.id.desc(),
        )
    ).all()
    evaluations = {row.result_id: row for row in selected}
    observations = []
    by_question = {q.id: q for q in questions}
    for row in rows:
        answerable = by_question[str(row.question_id)].answerable
        data: dict[str, Datum] = {}
        for name in METRICS[:3]:
            scores = row.context if name == "context_recall" else row.retrieval
            value = (scores or {}).get("precision" if name == "retrieval_precision" else "recall")
            state = (
                "not_applicable"
                if not answerable
                else "scored"
                if value is not None
                else ("error" if row.state == "failed" else "unavailable")
            )
            data[name] = Datum(
                state=state,
                value=value if state == "scored" else None,
                policy_hash=digest(manifest["config"].get("evidence_scoring")),
            )
        evaluation = evaluations.get(row.id)
        for name in METRICS[3:]:
            score = (evaluation.metrics or {}).get(name, {}) if evaluation else {}
            state = "unavailable"
            if name == "answer_correctness" and not answerable:
                state = "not_applicable"
            elif evaluation and evaluation.state == "failed":
                state = "error"
            elif evaluation and evaluation.state == "completed":
                state = "scored" if score.get("value") is not None else "not_applicable"
            policy = (
                {
                    "source": source,
                    "rubric": evaluation.rubric,
                    "judge": evaluation.judge if source == "model" else None,
                }
                if evaluation
                else None
            )
            data[name] = Datum(
                state=state,
                value=score.get("value") if state == "scored" else None,
                policy_hash=digest(policy) if policy else None,
            )
        observations.append(
            Observation(
                result_id=str(row.id),
                question_id=str(row.question_id),
                repeat=row.repeat,
                state=row.state,
                metrics=data,
                evaluation_id=str(evaluation.id) if evaluation else None,
                evaluation_hash=evaluation.manifest_hash if evaluation else None,
                timings=valid_timings(row.timings)
                | {
                    f"pipeline_{key}": value
                    for key, value in valid_timings(row.pipeline_timings).items()
                },
            )
        )
    attempts = session.execute(
        select(
            RunAttempt.state,
            func.jsonb_typeof(RunAttempt.trace["generation"]).label("generation_type"),
            RunAttempt.trace["generation"]["input_tokens"].label("input_tokens"),
            RunAttempt.trace["generation"]["output_tokens"].label("output_tokens"),
            RunAttempt.trace["error"].label("error"),
            RunAttempt.started_at,
            RunAttempt.finished_at,
        ).where(RunAttempt.run_id == run.id)
    ).all()
    judge_calls = session.execute(
        select(
            AnswerEvaluation.state,
            AnswerEvaluation.output["raw"]["input_tokens"].label("input_tokens"),
            AnswerEvaluation.output["raw"]["output_tokens"].label("output_tokens"),
            AnswerEvaluation.attempts,
        )
        .join(QuestionResult, QuestionResult.id == AnswerEvaluation.result_id)
        .where(
            QuestionResult.run_id == run.id,
            AnswerEvaluation.kind == "model",
            AnswerEvaluation.created_at <= cutoff,
        )
    ).all()
    generation_usage = [
        {"input_tokens": row.input_tokens, "output_tokens": row.output_tokens}
        for row in attempts
        if row.generation_type == "object"
    ]
    potential_unknown = sum(
        row.generation_type != "object"
        and (
            row.state in ("started", "interrupted", "cancelled")
            or (row.error or {}).get("stage") == "generation"
        )
        for row in attempts
    )
    stage_names = sorted(
        {name for observation in observations for name in observation.timings}
        | {"question_wall_ms", "retrieval_wall_ms", "generation_wall_ms"}
    )
    generation_contract: dict[str, Any] = manifest["config"]["generation"]
    accounting = {
        "run_state": run.state,
        "planned_observations": run.total_count,
        "saved_observations": len(observations),
        "successful_observations": sum(row.state == "succeeded" for row in observations),
        "failed_observations": sum(row.state == "failed" for row in observations),
        "completion_rate": sum(row.state == "succeeded" for row in observations) / run.total_count,
        "run_elapsed_ms": (run.finished_at - run.started_at).total_seconds() * 1000
        if run.finished_at and run.started_at
        else None,
        "queue_wait_ms": (run.started_at - run.created_at).total_seconds() * 1000
        if run.started_at
        else None,
        "stage_timings": {
            stage: timing_summary(
                [row.timings[stage] for row in observations if stage in row.timings],
                run.total_count,
            )
            for stage in stage_names
        },
        "attempt_count": len(attempts),
        "attempt_wall_ms": timing_summary(
            [
                (row.finished_at - row.started_at).total_seconds() * 1000
                for row in attempts
                if row.finished_at
            ],
            len(attempts),
        ),
        "attempts_by_state": {
            state: sum(row.state == state for row in attempts)
            for state in sorted({row.state for row in attempts})
        },
        "generation_usage": usage(generation_usage, potential_unknown),
        "judge_usage": usage(
            [
                {"input_tokens": row.input_tokens, "output_tokens": row.output_tokens}
                for row in judge_calls
                if row.attempts > 0
            ],
            sum(max(row.attempts - 1, 0) for row in judge_calls),
        ),
        "provider": generation_contract.get("provider"),
        "model_id": generation_contract.get("model_id"),
        "execution": manifest["execution"],
        "measurement": manifest["config"].get("measurement", {"cache_condition": "not_recorded"}),
        "index_build_ms": manifest["index_manifest"].get("build_elapsed_ms"),
        "cost": {
            "state": "unavailable",
            "value": None,
            "currency": None,
            "pricing_snapshot": None,
            "reason": "Local CPU energy/hardware cost is unmeasured; no provider pricing "
            "snapshot. Unknown usage is not free.",
        },
        "limitations": [
            "Final-observation stage times include successful and failed observations with "
            "available measurements.",
            "Generation includes hashing and fresh model loading; shared preparation is "
            "outside question timers.",
            "Run elapsed time includes recovery gaps; queue wait ends at first claim.",
            "Missing attempt usage may conceal completed inference; known token totals are "
            "lower bounds.",
            "Cache conditions are operator declarations, never verified automatically.",
        ],
        "evaluation_selection": {
            "source": source,
            "cutoff": cutoff.isoformat(),
            "policy": "latest-record-per-result-and-source-v1",
            "rubric_reference": RUBRIC_VERSION,
            "reviewers": sorted({row.reviewer for row in selected if row.reviewer}),
        },
    }
    return RunSample(
        id=str(run.id),
        manifest_hash=run.manifest_hash,
        state=run.state,
        purpose=manifest["purpose"],
        corpus_hash=manifest["index_manifest"]["corpus_hash"],
        dataset_hash=manifest["dataset_hash"],
        config=manifest["config"],
        execution=manifest["execution"],
        questions=questions,
        observations=observations,
        accounting=accounting,
    )
