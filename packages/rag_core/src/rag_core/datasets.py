"""Atomic curation, corpus lineage checks, and immutable dataset publication."""

import hashlib
import json
import unicodedata
from datetime import datetime
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from rag_core.dataset_models import Dataset, DatasetVersion, Question
from rag_core.dataset_schemas import (
    DatasetCreate,
    DatasetVersionView,
    DatasetView,
    ImportResult,
    QuestionInput,
    QuestionUpdate,
    QuestionView,
)
from rag_core.errors import PlatformError
from rag_core.models import (
    CorpusVersion,
    CorpusVersionMember,
    Document,
    DocumentRevision,
    SourceSection,
)
from rag_core.schemas import Page, SectionView


class ImportErrorDetail(PlatformError):
    def __init__(self, errors: list[dict[str, object]]) -> None:
        super().__init__("invalid_jsonl", "The import has errors. No questions were added.")
        self.field_errors = errors


def parse_jsonl(raw: bytes, max_questions: int) -> list[QuestionInput]:
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ImportErrorDetail([{"line": 1, "message": "Use UTF-8 JSONL."}]) from error
    questions: list[QuestionInput] = []
    errors: list[dict[str, object]] = []
    for number, line in enumerate(content.splitlines(), 1):
        if not line.strip():
            continue
        if len(questions) + len(errors) >= max_questions:
            errors.append({"line": number, "message": "The import exceeds the question limit."})
            break
        try:
            questions.append(QuestionInput.model_validate_json(line))
        except ValidationError as error:
            errors.append(
                {"line": number, "message": "; ".join(item["msg"] for item in error.errors())}
            )
    if errors:
        raise ImportErrorDetail(errors)
    if not questions:
        raise ImportErrorDetail([{"line": 1, "message": "Include at least one question."}])
    return questions


def normalized_question(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


class DatasetStore:
    def __init__(self, engine: Engine, max_questions: int = 1000) -> None:
        self.engine, self.max_questions = engine, max_questions

    @staticmethod
    def _dataset(session: Session, dataset_id: UUID, lock: bool = False) -> Dataset:
        query = select(Dataset).where(Dataset.id == dataset_id)
        dataset = session.scalar(query.with_for_update() if lock else query)
        if dataset is None:
            raise PlatformError("not_found", "The dataset was not found.", 404)
        return dataset

    @staticmethod
    def _validate_evidence(session: Session, corpus_id: UUID, content: QuestionInput) -> None:
        spans = [
            span
            for group in content.evidence_groups
            for alternative in group.alternatives
            for span in alternative.spans
        ]
        identifiers = {span.section_id for span in spans}
        sections = (
            {
                section.id: section
                for section in session.scalars(
                    select(SourceSection)
                    .join(
                        CorpusVersionMember,
                        CorpusVersionMember.revision_id == SourceSection.revision_id,
                    )
                    .where(
                        CorpusVersionMember.version_id == corpus_id,
                        SourceSection.id.in_(identifiers),
                    )
                )
            }
            if identifiers
            else {}
        )
        for span in spans:
            section = sections.get(span.section_id)
            if section is None:
                raise PlatformError(
                    "evidence_lineage", "Evidence must belong to the dataset's published corpus."
                )
            if (
                span.end_offset > len(section.text)
                or not section.text[span.start_offset : span.end_offset].strip()
            ):
                raise PlatformError(
                    "invalid_evidence_span",
                    "Evidence offsets must identify nonempty text inside the source section.",
                )

    def create(self, value: DatasetCreate) -> DatasetView:
        with Session(self.engine) as session, session.begin():
            corpus = session.get(CorpusVersion, value.corpus_version_id)
            if corpus is None or not corpus.sealed:
                raise PlatformError(
                    "corpus_not_published", "Choose a published corpus version.", 409
                )
            dataset = Dataset(**value.model_dump())
            session.add(dataset)
            session.flush()
            return DatasetView.model_validate(dataset)

    def datasets(self, limit: int, offset: int) -> Page[DatasetView]:
        with Session(self.engine) as session:
            rows = list(
                session.scalars(
                    select(Dataset)
                    .order_by(Dataset.created_at, Dataset.id)
                    .offset(offset)
                    .limit(limit + 1)
                )
            )
            return Page(
                items=[DatasetView.model_validate(row) for row in rows[:limit]],
                next_cursor=str(offset + limit) if len(rows) > limit else None,
            )

    def get(self, dataset_id: UUID) -> DatasetView:
        with Session(self.engine) as session:
            return DatasetView.model_validate(self._dataset(session, dataset_id))

    def questions(self, dataset_id: UUID, limit: int, offset: int) -> Page[QuestionView]:
        with Session(self.engine) as session:
            self._dataset(session, dataset_id)
            rows = list(
                session.scalars(
                    select(Question)
                    .where(Question.dataset_id == dataset_id)
                    .order_by(Question.created_at, Question.id)
                    .offset(offset)
                    .limit(limit + 1)
                )
            )
            return Page(
                items=[QuestionView.model_validate(row) for row in rows[:limit]],
                next_cursor=str(offset + limit) if len(rows) > limit else None,
            )

    def add(self, dataset_id: UUID, values: list[QuestionInput]) -> list[QuestionView]:
        with Session(self.engine) as session, session.begin():
            dataset = self._dataset(session, dataset_id, lock=True)
            existing = list(
                session.scalars(select(Question).where(Question.dataset_id == dataset_id))
            )
            if len(existing) + len(values) > self.max_questions:
                raise PlatformError(
                    "question_limit", "The dataset exceeds its configured question limit."
                )
            seen = {normalized_question(str(q.content["text"])) for q in existing}
            errors: list[dict[str, object]] = []
            for index, value in enumerate(values, 1):
                try:
                    self._validate_evidence(session, dataset.corpus_version_id, value)
                    key = normalized_question(value.text)
                    if key in seen:
                        raise PlatformError(
                            "duplicate_question",
                            "This question already exists in the dataset.",
                            409,
                        )
                    seen.add(key)
                except PlatformError as error:
                    errors.append({"record": index, "message": error.message, "code": error.code})
            if errors:
                if len(values) == 1:
                    first = errors[0]
                    raise PlatformError(
                        str(first["code"]),
                        str(first["message"]),
                        409 if first["code"] == "duplicate_question" else 422,
                    )
                raise ImportErrorDetail(errors)
            now: datetime = session.execute(select(func.clock_timestamp())).scalar_one()
            questions = [
                Question(
                    dataset_id=dataset_id,
                    content=value.model_dump(mode="json"),
                    reviewed_at=now if value.review_status == "reviewed" else None,
                )
                for value in values
            ]
            session.add_all(questions)
            dataset.draft_revision += 1
            session.flush()
            return [QuestionView.model_validate(question) for question in questions]

    def update(self, dataset_id: UUID, question_id: UUID, value: QuestionUpdate) -> QuestionView:
        with Session(self.engine) as session, session.begin():
            dataset = self._dataset(session, dataset_id, lock=True)
            question = session.scalar(
                select(Question)
                .where(Question.id == question_id, Question.dataset_id == dataset_id)
                .with_for_update()
            )
            if question is None:
                raise PlatformError("not_found", "The question was not found.", 404)
            if question.revision != value.expected_revision:
                raise PlatformError(
                    "revision_conflict", "This question changed. Reload it before saving.", 409
                )
            self._validate_evidence(session, dataset.corpus_version_id, value.content)
            others = session.scalars(
                select(Question).where(
                    Question.dataset_id == dataset_id, Question.id != question_id
                )
            )
            if any(
                normalized_question(str(q.content["text"]))
                == normalized_question(value.content.text)
                for q in others
            ):
                raise PlatformError(
                    "duplicate_question", "This question already exists in the dataset.", 409
                )
            question.content = value.content.model_dump(mode="json")
            question.revision += 1
            question.reviewed_at = (
                session.execute(select(func.clock_timestamp())).scalar_one()
                if value.content.review_status == "reviewed"
                else None
            )
            dataset.draft_revision += 1
            session.flush()
            return QuestionView.model_validate(question)

    def import_jsonl(self, dataset_id: UUID, raw: bytes) -> ImportResult:
        values = parse_jsonl(raw, self.max_questions)
        lines = [
            number
            for number, line in enumerate(raw.decode("utf-8-sig").splitlines(), 1)
            if line.strip()
        ]
        try:
            questions = self.add(dataset_id, values)
        except ImportErrorDetail as error:
            for detail in error.field_errors:
                detail["line"] = lines[int(str(detail.pop("record"))) - 1]
            raise
        except PlatformError as error:
            raise ImportErrorDetail([{"line": lines[0], "message": error.message}]) from error
        return ImportResult(imported=len(questions), question_ids=[q.id for q in questions])

    def source_sections(self, corpus_id: UUID, limit: int, offset: int) -> Page[SectionView]:
        with Session(self.engine) as session:
            if session.get(CorpusVersion, corpus_id) is None:
                raise PlatformError("not_found", "The corpus version was not found.", 404)
            rows = list(
                session.execute(
                    select(SourceSection, Document.filename)
                    .join(
                        CorpusVersionMember,
                        CorpusVersionMember.revision_id == SourceSection.revision_id,
                    )
                    .join(DocumentRevision, DocumentRevision.id == SourceSection.revision_id)
                    .join(Document, Document.id == DocumentRevision.document_id)
                    .where(CorpusVersionMember.version_id == corpus_id)
                    .order_by(SourceSection.revision_id, SourceSection.ordinal)
                    .offset(offset)
                    .limit(limit + 1)
                )
            )
            return Page(
                items=[
                    SectionView.model_validate(row[0]).model_copy(update={"document_name": row[1]})
                    for row in rows[:limit]
                ],
                next_cursor=str(offset + limit) if len(rows) > limit else None,
            )

    def source_section(self, corpus_id: UUID, section_id: UUID) -> SectionView:
        with Session(self.engine) as session:
            row = session.execute(
                select(SourceSection, Document.filename)
                .join(
                    CorpusVersionMember,
                    CorpusVersionMember.revision_id == SourceSection.revision_id,
                )
                .join(DocumentRevision, DocumentRevision.id == SourceSection.revision_id)
                .join(Document, Document.id == DocumentRevision.document_id)
                .where(CorpusVersionMember.version_id == corpus_id, SourceSection.id == section_id)
            ).first()
            if row is None:
                raise PlatformError("not_found", "This source is not in the published corpus.", 404)
            return SectionView.model_validate(row[0]).model_copy(update={"document_name": row[1]})

    def publish(self, dataset_id: UUID) -> DatasetVersionView:
        with Session(self.engine) as session, session.begin():
            dataset = self._dataset(session, dataset_id, lock=True)
            previous = session.scalar(
                select(DatasetVersion).where(
                    DatasetVersion.dataset_id == dataset_id,
                    DatasetVersion.draft_revision == dataset.draft_revision,
                )
            )
            if previous:
                return DatasetVersionView.model_validate(previous)
            questions = list(
                session.scalars(
                    select(Question)
                    .where(Question.dataset_id == dataset_id)
                    .order_by(Question.id)
                    .with_for_update()
                )
            )
            if not questions:
                raise PlatformError(
                    "dataset_not_ready", "Add reviewed questions before publishing.", 409
                )
            grouped_splits: dict[str, str] = {}
            section_splits: dict[UUID, str] = {}
            for question in questions:
                content = QuestionInput.model_validate(question.content)
                if (
                    content.review_status != "reviewed"
                    or not question.reviewed_at
                    or content.split == "unassigned"
                    or not content.topic
                    or not content.split_group
                ):
                    raise PlatformError(
                        "dataset_not_ready",
                        "Every question needs a human review, topic, split, and split group.",
                        409,
                    )
                if not content.reference_answer:
                    raise PlatformError(
                        "dataset_not_ready",
                        "Record a reference answer or expected abstention for every question.",
                        409,
                    )
                if content.answerable and (
                    not content.required_facts
                    or {g.fact_index for g in content.evidence_groups}
                    != set(range(len(content.required_facts)))
                ):
                    raise PlatformError(
                        "dataset_not_ready", "Every required fact needs supporting evidence.", 409
                    )
                self._validate_evidence(session, dataset.corpus_version_id, content)
                if (
                    content.split_group in grouped_splits
                    and grouped_splits[content.split_group] != content.split
                ):
                    raise PlatformError(
                        "split_leakage",
                        "Questions in one split group must use the same split.",
                        409,
                    )
                grouped_splits[content.split_group] = content.split
                for group in content.evidence_groups:
                    for alternative in group.alternatives:
                        for span in alternative.spans:
                            if (
                                span.section_id in section_splits
                                and section_splits[span.section_id] != content.split
                            ):
                                raise PlatformError(
                                    "split_leakage",
                                    "A source section cannot supply gold evidence to both "
                                    "development and test splits.",
                                    409,
                                )
                            section_splits[span.section_id] = content.split
            corpus = session.get(CorpusVersion, dataset.corpus_version_id)
            assert corpus is not None
            manifest: dict[str, object] = {
                "schema": "dataset-v1",
                "corpus_version_id": str(corpus.id),
                "corpus_manifest_hash": corpus.manifest_hash,
                "purpose": dataset.purpose,
                "evidence_policy": "canonical-section-local-codepoint-spans-v1",
                "questions": [
                    {
                        "id": str(q.id),
                        "revision": q.revision,
                        "content": q.content,
                        "reviewed_at": q.reviewed_at.isoformat() if q.reviewed_at else None,
                    }
                    for q in questions
                ],
            }
            digest = hashlib.sha256(
                json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            latest = (
                session.scalar(
                    select(func.max(DatasetVersion.version)).where(
                        DatasetVersion.dataset_id == dataset_id
                    )
                )
                or 0
            )
            version = DatasetVersion(
                dataset_id=dataset_id,
                corpus_version_id=corpus.id,
                version=latest + 1,
                draft_revision=dataset.draft_revision,
                question_count=len(questions),
                manifest=manifest,
                manifest_hash=digest,
            )
            session.add(version)
            session.flush()
            version.sealed = True
            session.flush()
            return DatasetVersionView.model_validate(version)

    def versions(self, dataset_id: UUID, limit: int, offset: int) -> Page[DatasetVersionView]:
        with Session(self.engine) as session:
            self._dataset(session, dataset_id)
            rows = list(
                session.scalars(
                    select(DatasetVersion)
                    .where(DatasetVersion.dataset_id == dataset_id)
                    .order_by(DatasetVersion.version)
                    .offset(offset)
                    .limit(limit + 1)
                )
            )
            return Page(
                items=[DatasetVersionView.model_validate(row) for row in rows[:limit]],
                next_cursor=str(offset + limit) if len(rows) > limit else None,
            )

    def export(self, version_id: UUID) -> str:
        with Session(self.engine) as session:
            version = session.get(DatasetVersion, version_id)
            if version is None:
                raise PlatformError("not_found", "The dataset version was not found.", 404)
            # Export only interchange fields so the same JSONL can be imported into a new draft.
            questions = version.manifest["questions"]
            assert isinstance(questions, list)
            return "".join(json.dumps(q["content"], ensure_ascii=False) + "\n" for q in questions)
