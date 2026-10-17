"""Read-only curation checks and conservative source groups before benchmark split freeze."""

from collections import Counter, defaultdict
from collections.abc import Sequence
from uuid import UUID

from pydantic import BaseModel

from rag_core.dataset_schemas import QuestionView
from rag_core.datasets import normalized_question
from rag_core.schemas import SectionView


class AuditIssue(BaseModel):
    code: str
    question_ids: list[UUID]
    message: str


class SourceGroup(BaseModel):
    question_ids: list[UUID]
    revision_ids: list[UUID]
    existing_groups: list[str]
    assigned_splits: list[str]


class CurationAudit(BaseModel):
    schema_version: str = "benchmark-curation-audit-v1"
    question_count: int
    reviewed_count: int
    human_reviewed_count: int
    ai_reviewed_count: int
    minimum_questions: int
    unassigned_count: int
    answerability: dict[str, int]
    topics: dict[str, int]
    difficulties: dict[str, int]
    issues: list[AuditIssue]
    source_groups: list[SourceGroup]
    automated_checks_pass: bool
    manual_checks_required: list[str] = [
        "Review paraphrases, related pages and cross-references before merging split groups.",
        "Validate unanswerability against the whole corpus and audit annotation completeness.",
        "Freeze the grouped split before tuning; this audit neither assigns nor publishes it.",
    ]


def audit_curation(
    questions: Sequence[QuestionView],
    sections: Sequence[SectionView],
    *,
    allowed_revision_ids: set[UUID],
    minimum_questions: int = 150,
) -> CurationAudit:
    if not 1 <= minimum_questions <= 1000 or len(questions) > 1000 or len(sections) > 100000:
        raise ValueError("Curation audit exceeds its bounded question/source limits")
    ids = [q.id for q in questions]
    if len({q.dataset_id for q in questions}) > 1:
        raise ValueError("Audit one dataset at a time")
    if len(set(ids)) != len(ids):
        raise ValueError("Audit input contains duplicate logical question IDs")
    source = {s.id: s for s in sections}
    if len(source) != len(sections):
        raise ValueError("Audit input contains duplicate source section IDs")
    issues: list[AuditIssue] = []
    parents = {qid: qid for qid in ids}

    def root(qid: UUID) -> UUID:
        while parents[qid] != qid:
            parents[qid] = parents[parents[qid]]
            qid = parents[qid]
        return qid

    def join(a: UUID, b: UUID) -> None:
        parents[root(b)] = root(a)

    owners: dict[tuple[str, str], UUID] = {}
    duplicates: dict[str, list[UUID]] = defaultdict(list)
    revisions: dict[UUID, set[UUID]] = defaultdict(set)
    for question in questions:
        q, qid = question.content, question.id

        def issue(code: str, message: str, qid: UUID = qid) -> None:
            issues.append(AuditIssue(code=code, question_ids=[qid], message=message))

        duplicates[normalized_question(q.text)].append(qid)
        if q.review_status != "reviewed" or not q.reviewer.strip() or question.reviewed_at is None:
            issue(
                "review_missing", "A saved individual review, reviewer and timestamp are required."
            )
        if not q.reference_answer.strip():
            issue(
                "reference_missing", "Record a reference answer or an explicit expected abstention."
            )
        if not q.topic.strip() or not q.split_group.strip():
            issue("group_metadata_missing", "Record a topic and a provisional relatedness group.")
        if q.split == "unassigned":
            issue(
                "split_unassigned", "Keep pending until the complete dataset's group audit is done."
            )
        if q.answerable and (
            not q.required_facts
            or {g.fact_index for g in q.evidence_groups} != set(range(len(q.required_facts)))
        ):
            issue("fact_evidence_missing", "Every required fact needs an accepted evidence group.")
        keys = [("group", q.split_group)] if q.split_group else []
        for group in q.evidence_groups:
            for alternative in group.alternatives:
                for span in alternative.spans:
                    section = source.get(span.section_id)
                    if section is None or section.revision_id not in allowed_revision_ids:
                        issue("evidence_lineage", "Gold evidence is outside the frozen corpus.")
                        continue
                    if (
                        span.end_offset > len(section.text)
                        or not section.text[span.start_offset : span.end_offset].strip()
                    ):
                        issue("evidence_bounds", "Gold evidence is outside the canonical section.")
                    revisions[qid].add(section.revision_id)
                    keys.append(("revision", str(section.revision_id)))
        for key in keys:
            if key in owners:
                join(owners[key], qid)
            else:
                owners[key] = qid
    for duplicate_ids in duplicates.values():
        if len(duplicate_ids) > 1:
            issues.append(
                AuditIssue(
                    code="duplicate_question",
                    question_ids=sorted(duplicate_ids, key=str),
                    message="Normalized question text repeats; reconcile before splitting.",
                )
            )
            for qid in duplicate_ids[1:]:
                join(duplicate_ids[0], qid)
    components: dict[UUID, list[QuestionView]] = defaultdict(list)
    for question in questions:
        components[root(question.id)].append(question)
    groups: list[SourceGroup] = []
    for members in components.values():
        member_ids = sorted((q.id for q in members), key=str)
        splits = sorted({q.content.split for q in members} - {"unassigned"})
        groups.append(
            SourceGroup(
                question_ids=member_ids,
                revision_ids=sorted({r for q in members for r in revisions[q.id]}, key=str),
                existing_groups=sorted({q.content.split_group for q in members}),
                assigned_splits=splits,
            )
        )
        if len(splits) > 1:
            issues.append(
                AuditIssue(
                    code="source_group_leakage",
                    question_ids=member_ids,
                    message="Related questions or one source document span development and test.",
                )
            )
    if len(questions) < minimum_questions:
        issues.append(
            AuditIssue(
                code="sample_target_unmet",
                question_ids=[],
                message=(
                    f"Need {minimum_questions} reviewed questions; "
                    f"current draft has {len(questions)}."
                ),
            )
        )
    return CurationAudit(
        question_count=len(questions),
        reviewed_count=sum(
            q.content.review_status == "reviewed"
            and q.reviewed_at is not None
            and bool(q.content.reviewer.strip())
            for q in questions
        ),
        human_reviewed_count=sum(
            q.content.review_source == "human"
            and q.content.review_status == "reviewed"
            and q.reviewed_at is not None
            and bool(q.content.reviewer.strip())
            for q in questions
        ),
        ai_reviewed_count=sum(
            q.content.review_source == "ai"
            and q.content.review_status == "reviewed"
            and q.reviewed_at is not None
            and bool(q.content.reviewer.strip())
            for q in questions
        ),
        minimum_questions=minimum_questions,
        unassigned_count=sum(q.content.split == "unassigned" for q in questions),
        answerability=dict(
            Counter("answerable" if q.content.answerable else "unanswerable" for q in questions)
        ),
        topics=dict(Counter(q.content.topic for q in questions)),
        difficulties=dict(Counter(q.content.difficulty for q in questions)),
        issues=issues,
        source_groups=sorted(groups, key=lambda g: str(g.question_ids[0])),
        automated_checks_pass=not issues,
    )
