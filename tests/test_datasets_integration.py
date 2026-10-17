import hashlib
import json
import os
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from rag_api.main import create_app
from rag_core.database import create_database_engine
from rag_core.documents import DocumentStore
from rag_core.jobs import IngestionQueue
from rag_core.schemas import CorpusCreate
from rag_core.settings import Settings
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.integration


@pytest.fixture
def setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Settings, UUID, UUID]:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a disposable PostgreSQL/pgvector database")
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(Config("alembic.ini"), "head")
    settings = Settings(_env_file=None, artifact_root=tmp_path)
    engine = create_database_engine(settings)
    try:
        store = DocumentStore(engine)
        corpus = store.create_corpus(CorpusCreate(name=f"Dataset test fixture {uuid4()}"))
        raw = "# Transactions\nA transaction is a unit. 🧪\n".encode()
        key = "originals/guide.md"
        path = tmp_path / key
        path.parent.mkdir(parents=True)
        path.write_bytes(raw)
        document, _ = store.upload(
            corpus.id,
            "guide.md",
            key,
            hashlib.sha256(raw).hexdigest(),
            len(raw),
            "text/markdown",
            3,
        )
        queue = IngestionQueue(engine, settings)
        claim = queue.claim()
        assert claim and claim[0] == document.job_id
        queue.process(*claim, Event())
        version = store.publish(corpus.id)
        section = store.sections(document.id, 20, 0).items[0]
        return settings, version.id, section.id
    finally:
        engine.dispose()


def question(section_id: UUID) -> dict[str, object]:
    return {
        "text": "What does this software test fixture say about transactions?",
        "reference_answer": "A transaction is a unit.",
        "required_facts": ["A transaction is a unit."],
        "evidence_groups": [
            {
                "fact_index": 0,
                "alternatives": [
                    {
                        "spans": [
                            {"section_id": str(section_id), "start_offset": 15, "end_offset": 40}
                        ]
                    }
                ],
            }
        ],
        "topic": "transactions",
        "split": "development",
        "split_group": "transactions-basics",
        "review_status": "reviewed",
        "reviewer": "Software test fixture reviewer",
    }


def create_dataset(client: TestClient, version_id: UUID) -> str:
    response = client.post(
        "/api/v1/datasets",
        json={
            "name": "Dataset software fixture",
            "purpose": "development_fixture",
            "corpus_version_id": str(version_id),
        },
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


@pytest.mark.parametrize("review_source", ["human", "ai"])
def test_split_assignment_preserves_actual_source_review_time(
    setup: tuple[Settings, UUID, UUID], review_source: str
) -> None:
    settings, corpus_id, section_id = setup
    with TestClient(create_app(settings)) as client:
        dataset_id = create_dataset(client, corpus_id)
        path = f"/api/v1/datasets/{dataset_id}/questions"
        saved = client.post(path, json=question(section_id) | {"review_source": review_source})
        assert saved.status_code == 201, saved.text
        original = saved.json()
        url = path + "/" + original["id"]
        content = original["content"] | {"split": "test", "split_group": "audited-group"}
        updated = client.patch(
            url, json={"expected_revision": original["revision"], "content": content}
        )
        assert updated.status_code == 200, updated.text
        current = updated.json()
        assert current["reviewed_at"] == original["reviewed_at"]
        assert current["content"]["review_source"] == review_source
        assert current["revision"] == original["revision"] + 1
        # Saving new source-reviewed gold is a new attestation, unlike moving a split.
        changed = client.patch(
            url,
            json={
                "expected_revision": current["revision"],
                "content": content | {"reference_answer": "The fixture describes a single unit."},
            },
        )
        assert changed.status_code == 200, changed.text
        assert changed.json()["reviewed_at"] > current["reviewed_at"]
        cleared = client.patch(
            url,
            json={
                "expected_revision": changed.json()["revision"],
                "content": changed.json()["content"] | {"review_status": "candidate"},
            },
        )
        assert cleared.status_code == 200, cleared.text
        assert cleared.json()["reviewed_at"] is None


def test_ai_gold_review_provenance_survives_publication_and_jsonl(
    setup: tuple[Settings, UUID, UUID],
) -> None:
    settings, corpus_id, section_id = setup
    with TestClient(create_app(settings)) as client:
        dataset_id = create_dataset(client, corpus_id)
        value = question(section_id) | {
            "review_source": "ai",
            "reviewer": "Synthetic AI reviewer",
        }
        saved = client.post(f"/api/v1/datasets/{dataset_id}/questions", json=value)
        assert saved.status_code == 201
        assert saved.json()["content"]["review_source"] == "ai"
        published = client.post(f"/api/v1/datasets/{dataset_id}/versions")
        assert published.status_code == 201, published.text
        version_id = published.json()["id"]
        raw = client.get(f"/api/v1/dataset-versions/{version_id}/export")
        assert raw.status_code == 200
        exported = json.loads(raw.text.strip())
        assert exported["review_source"] == "ai"
        other = create_dataset(client, corpus_id)
        imported = client.post(
            f"/api/v1/datasets/{other}/import",
            files={"file": ("synthetic.jsonl", raw.content, "application/x-ndjson")},
        )
        assert imported.status_code == 200, imported.text
        row = client.get(f"/api/v1/datasets/{other}/questions").json()["items"][0]
        assert row["content"]["review_source"] == "ai"


def test_dataset_publication_export_roundtrip_and_draft_isolation(
    setup: tuple[Settings, UUID, UUID],
) -> None:
    settings, corpus_id, section_id = setup
    with TestClient(create_app(settings)) as client:
        dataset_id = create_dataset(client, corpus_id)
        path = f"/api/v1/datasets/{dataset_id}"
        candidate = question(section_id) | {"review_status": "candidate", "reviewer": ""}
        response = client.post(path + "/questions", json=candidate)
        assert response.status_code == 201, response.text
        draft = response.json()
        assert client.post(path + "/versions").status_code == 409
        reviewed = client.patch(
            path + "/questions/" + draft["id"],
            json={"expected_revision": 1, "content": question(section_id)},
        )
        assert reviewed.status_code == 200, reviewed.text
        frozen = client.post(path + "/versions").json()
        assert frozen["question_count"] == 1
        assert client.post(path + "/versions").json()["id"] == frozen["id"]
        exported = client.get(f"/api/v1/dataset-versions/{frozen['id']}/export")
        assert exported.status_code == 200
        other_id = create_dataset(client, corpus_id)
        imported = client.post(
            f"/api/v1/datasets/{other_id}/import",
            files={"file": ("fixture.jsonl", exported.content)},
        )
        assert imported.status_code == 200 and imported.json()["imported"] == 1
        assert client.post(f"/api/v1/datasets/{other_id}/versions").status_code == 201
        edited = question(section_id) | {
            "text": "Edited question?",
            "review_status": "candidate",
            "reviewer": "",
        }
        assert (
            client.patch(
                path + "/questions/" + draft["id"], json={"expected_revision": 2, "content": edited}
            ).status_code
            == 200
        )
        assert (
            client.get(f"/api/v1/dataset-versions/{frozen['id']}/export").content
            == exported.content
        )
        assert (
            client.patch(
                path + "/questions/" + draft["id"], json={"expected_revision": 2, "content": edited}
            ).status_code
            == 409
        )
        engine = create_database_engine(settings)
        try:
            with engine.begin() as connection, pytest.raises(IntegrityError):
                connection.execute(
                    text("UPDATE dataset_versions SET manifest_hash='tampered' WHERE id=:id"),
                    {"id": frozen["id"]},
                )
        finally:
            engine.dispose()


def test_atomic_import_lineage_offsets_and_split_leakage(
    setup: tuple[Settings, UUID, UUID],
) -> None:
    settings, corpus_id, section_id = setup
    with TestClient(create_app(settings)) as client:
        dataset_id = create_dataset(client, corpus_id)
        path = f"/api/v1/datasets/{dataset_id}"
        invalid = json.dumps(question(section_id)) + '\n\n{"text":}\n'
        response = client.post(path + "/import", files={"file": ("bad.jsonl", invalid.encode())})
        assert response.status_code == 422 and response.json()["field_errors"][0]["line"] == 3
        assert client.get(path + "/questions").json()["items"] == []
        wrong = question(uuid4())
        assert client.post(path + "/questions", json=wrong).json()["code"] == "evidence_lineage"
        wrong = question(section_id)
        groups = wrong["evidence_groups"]
        assert isinstance(groups, list)
        groups[0]["alternatives"][0]["spans"][0]["end_offset"] = 100000
        assert (
            client.post(path + "/questions", json=wrong).json()["code"] == "invalid_evidence_span"
        )
        assert client.post(path + "/questions", json=question(section_id)).status_code == 201
        engine = create_database_engine(settings)
        try:
            with engine.begin() as connection, pytest.raises(IntegrityError):
                connection.execute(
                    text(
                        "UPDATE questions SET content=jsonb_set(content, "
                        "'{evidence_groups,0,alternatives,0,spans,0,section_id}', "
                        "to_jsonb(CAST(:foreign_id AS text))) WHERE dataset_id=:dataset"
                    ),
                    {"foreign_id": str(uuid4()), "dataset": dataset_id},
                )
        finally:
            engine.dispose()
        duplicate = question(section_id) | {
            "text": " WHAT DOES THIS SOFTWARE TEST FIXTURE SAY ABOUT TRANSACTIONS? "
        }
        assert client.post(path + "/questions", json=duplicate).status_code == 409
        test_question = question(section_id) | {
            "text": "Another question?",
            "split": "test",
            "split_group": "other-group",
        }
        assert client.post(path + "/questions", json=test_question).status_code == 201
        assert client.post(path + "/versions").json()["code"] == "split_leakage"


def test_unanswerable_questions_publish_without_positive_evidence(
    setup: tuple[Settings, UUID, UUID],
) -> None:
    settings, corpus_id, _ = setup
    with TestClient(create_app(settings)) as client:
        dataset_id = create_dataset(client, corpus_id)
        value = {
            "text": "Is an unavailable feature documented?",
            "answerable": False,
            "reference_answer": "The corpus does not supply an answer.",
            "topic": "unanswerable",
            "split": "test",
            "split_group": "missing-feature",
            "review_status": "reviewed",
            "reviewer": "Software fixture reviewer",
        }
        assert (
            client.post(f"/api/v1/datasets/{dataset_id}/questions", json=value).status_code == 201
        )
        assert client.post(f"/api/v1/datasets/{dataset_id}/versions").status_code == 201
