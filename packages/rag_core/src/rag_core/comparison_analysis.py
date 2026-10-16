"""Paired question means and deterministic cluster bootstrap; no inferred missing scores."""

import math
import random
from collections import Counter, defaultdict
from threading import Event
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from rag_core.errors import LostLease

ANALYSIS_VERSION = "paired-question-cluster-bootstrap-v2"
METRICS = (
    "retrieval_precision",
    "retrieval_recall",
    "context_recall",
    "answer_correctness",
    "faithfulness",
    "citation_support",
    "abstention_quality",
)


class Datum(BaseModel):
    state: Literal["scored", "unavailable", "error", "not_applicable"]
    value: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    policy_hash: str | None = None


class FrozenQuestion(BaseModel):
    id: str
    revision: int
    content_hash: str
    text: str
    group: str
    answerable: bool
    topic: str | None = None
    difficulty: str | None = None


class Observation(BaseModel):
    result_id: str
    question_id: str
    repeat: int
    state: str
    metrics: dict[str, Datum]
    evaluation_id: str | None = None
    evaluation_hash: str | None = None
    timings: dict[str, float] = Field(default_factory=dict)


class RunSample(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    manifest_hash: str
    state: str
    purpose: str
    corpus_hash: str
    dataset_hash: str
    config: dict[str, Any]
    execution: dict[str, Any]
    questions: list[FrozenQuestion]
    observations: list[Observation]
    accounting: dict[str, Any]


def quantile(values: list[float], probability: float) -> float | None:
    """Linear interpolation at (n-1)*p, including singleton and empty inputs."""
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * probability
    lo, hi = math.floor(index), math.ceil(index)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (index - lo)


def timing_summary(values: list[float], expected: int) -> dict[str, Any]:
    valid = [value for value in values if math.isfinite(value) and value >= 0]
    return {
        "unit": "ms",
        "p50": quantile(valid, 0.5),
        "p95": quantile(valid, 0.95),
        "scored_count": len(valid),
        "unavailable_count": expected - len(valid),
        "quantile_policy": "linear-n-minus-one-v1",
    }


def compatibility(a: RunSample, b: RunSample) -> list[dict[str, Any]]:
    differences = []

    def compare(path: str, left: object, right: object, controlled: bool) -> None:
        if left != right:
            differences.append(
                {"field": path, "baseline": left, "candidate": right, "blocks_strict": controlled}
            )

    for field in ("corpus_hash", "dataset_hash"):
        compare(field, getattr(a, field), getattr(b, field), True)
    for field in (
        "split",
        "generation",
        "context_tokens",
        "max_new_tokens",
        "seed",
        "repeats",
        "top_k",
        "evidence_scoring",
    ):
        compare(f"config.{field}", a.config.get(field), b.config.get(field), True)
    for field in (
        "retrieval",
        "retrieval_strategy",
        "candidate_k",
        "rrf_k",
        "reranker",
        "measurement",
    ):
        compare(f"config.{field}", a.config.get(field), b.config.get(field), False)
    compare("execution", a.execution, b.execution, False)
    for label, sample in (("baseline", a), ("candidate", b)):
        if sample.state != "completed":
            differences.append(
                {
                    "field": f"{label}.state",
                    "baseline": "completed",
                    "candidate": sample.state,
                    "blocks_strict": True,
                }
            )
    return differences


def coverage(sample: RunSample, metric: str) -> dict[str, Any]:
    repeats = int(sample.config["repeats"])
    questions = {question.id: question for question in sample.questions}
    observations: dict[str, list[Observation]] = {
        row.question_id: [] for row in sample.observations
    }
    for observation in sample.observations:
        observations[observation.question_id].append(observation)
    counts: Counter[str] = Counter()
    for question in questions.values():
        for repeat in range(repeats):
            row = next(
                (row for row in observations.get(question.id, []) if row.repeat == repeat), None
            )
            datum = row.metrics.get(metric) if row else None
            if datum is None:
                # Retrieval/correctness applicability can be established without a saved result.
                counts[
                    "not_applicable"
                    if not question.answerable
                    and metric
                    in (
                        "retrieval_precision",
                        "retrieval_recall",
                        "context_recall",
                        "answer_correctness",
                    )
                    else "unavailable"
                ] += 1
            else:
                counts[datum.state] += 1
    planned = len(questions) * repeats
    unknown = (
        counts["unavailable"] + counts["error"]
        if metric in ("faithfulness", "citation_support")
        else 0
    )
    return {
        "planned_count": planned,
        "applicable_count": None if unknown else planned - counts["not_applicable"],
        "scored_count": counts["scored"],
        "error_count": counts["error"],
        "unavailable_count": counts["unavailable"],
        "not_applicable_count": counts["not_applicable"],
    }


def question_mean(
    sample: RunSample, question_id: str, metric: str
) -> tuple[float | None, str, str | None]:
    expected = int(sample.config["repeats"])
    rows = [row for row in sample.observations if row.question_id == question_id]
    if {row.repeat for row in rows} != set(range(expected)):
        return None, "missing_repeat", None
    data = [row.metrics.get(metric, Datum(state="unavailable")) for row in rows]
    if any(datum.state != "scored" or datum.value is None for datum in data):
        reason = (
            "error"
            if any(d.state == "error" for d in data)
            else (
                "not_applicable"
                if all(d.state == "not_applicable" for d in data)
                else "unavailable"
            )
        )
        return None, reason, None
    policies = {datum.policy_hash for datum in data}
    if len(policies) != 1 or None in policies:
        return None, "mixed_scoring_policy", None
    return (
        sum(datum.value for datum in data if datum.value is not None) / expected,
        "scored",
        next(iter(policies)),
    )


def analyze(
    a: RunSample,
    b: RunSample,
    *,
    exploratory: bool,
    seed: int,
    resamples: int,
    stop: Event,
    lost: Event,
) -> dict[str, Any]:
    differences = compatibility(a, b)
    strict_blocked = any(item["blocks_strict"] for item in differences)
    aq, bq = {q.id: q for q in a.questions}, {q.id: q for q in b.questions}
    reports = {}
    for metric in METRICS:
        pairs: list[dict[str, Any]] = []
        exclusions: list[dict[str, str]] = []
        clusters: dict[str, list[float]] = defaultdict(list)
        for question_id in sorted(aq.keys() | bq.keys()):
            if stop.is_set() or lost.is_set():
                raise LostLease
            left, right = aq.get(question_id), bq.get(question_id)
            reason = None
            if not left or not right:
                reason = "question_not_in_both_runs"
            elif (left.content_hash, left.revision, left.group) != (
                right.content_hash,
                right.revision,
                right.group,
            ):
                reason = "question_revision_content_or_group_mismatch"
            av, ar, ap = question_mean(a, question_id, metric) if left else (None, "missing", None)
            bv, br, bp = question_mean(b, question_id, metric) if right else (None, "missing", None)
            if reason is None and (av is None or bv is None):
                reason = f"baseline:{ar};candidate:{br}"
            if reason is None and ap != bp:
                reason = "scoring_policy_mismatch"
            if reason:
                exclusions.append({"question_id": question_id, "reason": reason})
                continue
            assert av is not None and bv is not None and left is not None
            delta = bv - av
            pairs.append(
                {
                    "question_id": question_id,
                    "question": left.text,
                    "group": left.group,
                    "baseline": av,
                    "candidate": bv,
                    "difference": delta,
                    "policy_hash": ap,
                }
            )
            clusters[left.group].append(delta)
        ac, bc = coverage(a, metric), coverage(b, metric)
        incomplete = any(c["error_count"] or c["unavailable_count"] for c in (ac, bc))
        policies = {pair["policy_hash"] for pair in pairs}
        mixed_policies = len(policies) > 1
        eligible = (
            bool(pairs)
            and not mixed_policies
            and (exploratory or not (strict_blocked or incomplete))
        )
        interval, interval_reason = None, None
        if mixed_policies:
            interval_reason = (
                "Scoring revisions vary across paired questions; mixed-policy inference is blocked."
            )
        elif not eligible:
            interval_reason = (
                "No paired scores."
                if not pairs
                else "Strict comparison blocked by controls or incomplete scoring."
            )
        elif len(clusters) < 2:
            interval_reason = (
                "At least two independent split groups are required; no singleton interval."
            )
        else:
            rng = random.Random(seed)
            groups = sorted(clusters)
            totals = {group: (sum(clusters[group]), len(clusters[group])) for group in groups}
            bootstrap = []
            for iteration in range(resamples):
                if iteration % 32 == 0 and (stop.is_set() or lost.is_set()):
                    raise LostLease
                selected = rng.choices(groups, k=len(groups))
                bootstrap.append(
                    sum(totals[g][0] for g in selected) / sum(totals[g][1] for g in selected)
                )
            interval = {
                "low": quantile(bootstrap, 0.025),
                "high": quantile(bootstrap, 0.975),
                "confidence": 0.95,
                "seed": seed,
                "resamples": resamples,
                "unit": "score_difference",
                "resampling_unit": "split_group",
            }
        reports[metric] = {
            "state": "scored" if eligible else "blocked" if pairs else "unavailable",
            "baseline_coverage": ac,
            "candidate_coverage": bc,
            "paired_question_count": len(pairs),
            "scoring_policy_count": len(policies),
            "group_count": len(clusters),
            "excluded_question_count": len(exclusions),
            "exclusion_counts": dict(Counter(e["reason"] for e in exclusions)),
            "baseline_mean": sum(p["baseline"] for p in pairs) / len(pairs) if pairs else None,
            "candidate_mean": sum(p["candidate"] for p in pairs) / len(pairs) if pairs else None,
            "difference": sum(p["difference"] for p in pairs) / len(pairs) if pairs else None,
            "interval": interval,
            "interval_reason": interval_reason,
            "pairs": pairs,
            "exclusions": exclusions,
        }
    return {
        "version": ANALYSIS_VERSION,
        "exploratory": exploratory,
        "differences": differences,
        "strict_blocked": strict_blocked,
        "metrics": reports,
        "accounting": {"baseline": a.accounting, "candidate": b.accounting},
        "development_fixture": a.purpose != "research" or b.purpose != "research",
        "limitations": [
            "No automatic winner or generalization claim.",
            "Repeats are averaged per question; split groups are resampled as whole clusters.",
            "Percentile intervals describe the paired sample and recorded resampling procedure.",
            "Multiple metrics are exploratory; no multiple-comparison adjustment is applied.",
            "Human labels and model estimates remain separate; judge calibration is not "
            "established.",
            "Latency includes model hashing/loading; unknown cache/compute cost is not zero.",
        ],
    }
