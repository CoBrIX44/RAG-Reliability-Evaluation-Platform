"""Reviewed, canonical-span datasets independent of retrieval chunk IDs."""

from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DatasetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=4000)
    corpus_version_id: UUID
    purpose: Literal["research", "development_fixture"] = "research"


class DatasetView(DatasetCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    draft_revision: int
    created_at: datetime


class EvidenceSpan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    section_id: UUID
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)

    @model_validator(mode="after")
    def nonempty(self) -> Self:
        if self.end_offset <= self.start_offset:
            raise ValueError("Evidence spans must contain text")
        return self


class EvidenceAlternative(BaseModel):
    model_config = ConfigDict(extra="forbid")
    spans: list[EvidenceSpan] = Field(min_length=1, max_length=20)


class EvidenceGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fact_index: int = Field(ge=0)
    alternatives: list[EvidenceAlternative] = Field(min_length=1, max_length=20)


class QuestionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    text: str = Field(min_length=1, max_length=4000)
    answerable: bool = True
    reference_answer: str = Field(default="", max_length=16000)
    required_facts: list[str] = Field(default_factory=list, max_length=30)
    evidence_groups: list[EvidenceGroup] = Field(default_factory=list, max_length=30)
    topic: str = Field(default="", max_length=160)
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    split: Literal["unassigned", "development", "test"] = "unassigned"
    split_group: str = Field(default="", max_length=160)
    review_status: Literal["candidate", "reviewed"] = "candidate"
    reviewer: str = Field(default="", max_length=160)

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if sum(len(a.spans) for group in self.evidence_groups for a in group.alternatives) > 200:
            raise ValueError("A question can contain at most 200 evidence spans")
        if any(not fact.strip() or len(fact) > 2000 for fact in self.required_facts):
            raise ValueError("Required facts must be nonempty and at most 2000 characters")
        indices = [group.fact_index for group in self.evidence_groups]
        if len(set(indices)) != len(indices) or any(
            index >= len(self.required_facts) for index in indices
        ):
            raise ValueError("Each evidence group must reference a distinct required fact")
        if not self.answerable and (self.required_facts or self.evidence_groups):
            raise ValueError("Unanswerable questions cannot include positive facts or evidence")
        if self.review_status == "reviewed" and not self.reviewer:
            raise ValueError("Record the person who reviewed the question")
        return self


class QuestionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    dataset_id: UUID
    revision: int
    content: QuestionInput
    reviewed_at: datetime | None
    created_at: datetime


class QuestionUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    content: QuestionInput


class DatasetVersionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    dataset_id: UUID
    corpus_version_id: UUID
    version: int
    draft_revision: int
    question_count: int
    manifest_hash: str
    manifest: dict[str, object]
    created_at: datetime


class ImportResult(BaseModel):
    imported: int
    question_ids: list[UUID]
