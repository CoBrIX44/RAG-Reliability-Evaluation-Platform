"""Versioned, inspectable answer judgments; model estimates are never human labels."""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from rag_core.errors import PlatformError

RUBRIC_VERSION = "answer-evidence-v1"
RUBRIC = {
    "version": RUBRIC_VERSION,
    "correctness": "Covered required facts / all required facts; any contradiction gives zero. "
    "Unanswerable questions have no correctness denominator. Abstaining on answerable gives zero.",
    "faithfulness": "Supported atomic answer claims / all answer claims against delivered evidence "
    "only. Uncertain counts as unsupported. Abstention or no factual claims is unavailable.",
    "citation_support": "Claims with at least one valid supporting inline citation / all claims. "
    "Missing, unknown, or unsupported citations give no credit. No claims is unavailable.",
    "abstention_quality": "Exact INSUFFICIENT_EVIDENCE decision agrees with frozen answerability "
    "(binary decision accuracy, not a semantic refusal detector).",
    "limitations": "Fact coverage depends on gold completeness. Claim segmentation and support "
    "are reviewer judgments. Local 0.5B self-judge estimates are uncalibrated; "
    "inspect disagreements.",
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, strict=True)


class ClaimJudgment(StrictModel):
    text: str = Field(min_length=1, max_length=2000)
    support: Literal["supported", "unsupported", "uncertain"]
    citations: list[str] = Field(max_length=50)
    citations_supported: bool


class Judgment(StrictModel):
    facts: list[Literal["covered", "missing", "contradicted"]] = Field(max_length=100)
    claims: list[ClaimJudgment] = Field(max_length=50)
    no_factual_claims: bool
    rationale: str = Field(min_length=1, max_length=4000)


def validate_judgment(value: Judgment, inputs: dict[str, object]) -> None:
    facts = inputs["required_facts"]
    assert isinstance(facts, list)
    answer = str(inputs["answer"])
    abstained = answer.strip() == "INSUFFICIENT_EVIDENCE"
    if len(value.facts) != len(facts):
        raise PlatformError("invalid_judgment", "Assess every required fact in its original order.")
    if value.no_factual_claims != (len(value.claims) == 0):
        raise PlatformError(
            "invalid_judgment", "Confirm no factual claims or assess answer claims."
        )
    if abstained and (value.claims or any(fact != "missing" for fact in value.facts)):
        raise PlatformError(
            "invalid_judgment", "An exact abstention has no claims or covered facts."
        )
    if len({claim.text for claim in value.claims}) != len(value.claims):
        raise PlatformError("invalid_judgment", "Assess each distinct answer claim once.")
    for claim in value.claims:
        # Quotes must be literal excerpts of this answer; no invented claims or evidence IDs.
        if claim.text not in answer or len(set(claim.citations)) != len(claim.citations):
            raise PlatformError(
                "invalid_judgment", "Each claim must quote the saved answer exactly."
            )
        if any(
            f"[{citation}]" not in answer or not re.fullmatch(r"P[1-9][0-9]*", citation)
            for citation in claim.citations
        ):
            raise PlatformError("invalid_judgment", "Use only citation IDs present in the answer.")


def score_judgment(value: Judgment, inputs: dict[str, object]) -> dict[str, object]:
    validate_judgment(value, inputs)
    abstained = str(inputs["answer"]).strip() == "INSUFFICIENT_EVIDENCE"
    answerable = inputs["answerable"] is True
    evidence = inputs["evidence"]
    assert isinstance(evidence, list)
    valid_ids = {f"P{i}" for i in range(1, len(evidence) + 1)}

    def metric(numerator: int, denominator: int, reason: str) -> dict[str, object]:
        return {
            "value": numerator / denominator if denominator else None,
            "numerator": numerator if denominator else None,
            "denominator": denominator if denominator else None,
            "state": "scored" if denominator else "unavailable",
            "reason": None if denominator else reason,
        }

    factual = value.claims if not abstained else []
    correctness = 0 if abstained or "contradicted" in value.facts else value.facts.count("covered")
    return {
        "answer_correctness": metric(
            correctness,
            len(value.facts) if answerable else 0,
            "No applicable required-fact denominator.",
        ),
        "faithfulness": metric(
            sum(c.support == "supported" for c in factual),
            len(factual),
            "No factual claims to assess.",
        ),
        "citation_support": metric(
            sum(
                c.support == "supported"
                and c.citations_supported
                and bool(c.citations)
                and set(c.citations) <= valid_ids
                for c in factual
            ),
            len(factual),
            "No factual claims to assess.",
        ),
        "abstention_quality": metric(int(abstained != answerable), 1, ""),
    }
