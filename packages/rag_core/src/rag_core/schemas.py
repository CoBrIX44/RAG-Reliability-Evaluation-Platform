import hashlib
from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CorpusCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=4000)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Give the corpus a name")
        return value


class CorpusView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    description: str
    draft_revision: int
    created_at: datetime


class DocumentView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    corpus_id: UUID
    filename: str
    media_type: str
    checksum: str
    byte_count: int
    state: Literal["pending", "processing", "ready", "failed"]
    error_code: str | None
    error_message: str | None
    created_at: datetime
    job_id: UUID
    section_count: int = 0
    revision_id: UUID | None = None


class SectionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    revision_id: UUID
    ordinal: int
    heading_path: list[str]
    text: str
    start_offset: int
    end_offset: int
    source: dict[str, object]
    document_name: str | None = None


class VersionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    corpus_id: UUID
    version: int
    draft_revision: int
    manifest_hash: str
    manifest: dict[str, object]
    document_count: int
    created_at: datetime


class JobView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    document_id: UUID
    kind: str
    state: str
    attempts: int
    max_attempts: int
    error_code: str | None
    error_message: str | None
    checkpoint_stage: str | None = None


class Page[T](BaseModel):
    items: list[T]
    next_cursor: str | None = None


class SourceLocation(BaseModel):
    format: str
    page: int | None = None
    anchor: str | None = None
    start_line: int | None = None
    end_line: int | None = None


class ExtractedSection(BaseModel):
    heading_path: list[str]
    text: str
    source: SourceLocation


class Extraction(BaseModel):
    extractor_version: str
    input_checksum: str
    checksum: str
    sections: list[ExtractedSection]
    character_count: int

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        canonical = "\n\n".join(section.text for section in self.sections)
        if not canonical.strip() or len(canonical) != self.character_count:
            raise ValueError("Extraction text length is inconsistent")
        if hashlib.sha256(canonical.encode()).hexdigest() != self.checksum:
            raise ValueError("Extraction checksum is inconsistent")
        return self
