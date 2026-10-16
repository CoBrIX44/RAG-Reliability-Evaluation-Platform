"""Bounded worker-created ZIP evidence bundles with frozen selections and checksums."""

import contextlib
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Thread
from typing import Any, Literal
from uuid import UUID, uuid4
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Engine, and_, func, or_, select, text
from sqlalchemy.engine import ScalarResult
from sqlalchemy.orm import Session

from rag_core.comparison_models import Comparison
from rag_core.database import record_worker_heartbeat
from rag_core.errors import LostLease, PlatformError
from rag_core.evaluation_models import AnswerEvaluation
from rag_core.export_models import ExportJob
from rag_core.run_models import QuestionResult, Run, RunAttempt
from rag_core.runs import TERMINAL, digest, execution_identity
from rag_core.settings import Settings


class ExportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_kind: Literal["run", "comparison"]
    source_id: UUID


class ExportView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    state: str
    manifest_hash: str
    manifest: dict[str, Any]
    output: dict[str, Any] | None
    attempts: int
    created_at: datetime


def raw_row(session: Session, table: str, row_id: UUID) -> dict[str, Any]:
    if table not in {
        "runs",
        "question_results",
        "run_attempts",
        "answer_evaluations",
        "comparisons",
        "source_sections",
        "document_revisions",
        "documents",
        "corpus_versions",
        "dataset_versions",
    }:
        raise ValueError("Unsupported export table")
    row = session.scalar(text(f"SELECT to_jsonb(t) FROM {table} t WHERE id=:id"), {"id": row_id})
    if not isinstance(row, dict):
        raise PlatformError("export_source_missing", "An export source is missing.")
    return row


def section_ids(value: Any) -> set[UUID]:
    found: set[UUID] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "section_id" and isinstance(item, str):
                found.add(UUID(item))
            else:
                found.update(section_ids(item))
    elif isinstance(value, list):
        for item in value:
            found.update(section_ids(item))
    return found


class ExportQueue:
    def __init__(self, engine: Engine, settings: Settings) -> None:
        self.engine, self.settings = engine, settings

    def create(self, value: ExportCreate, key: str) -> ExportView:
        with Session(self.engine) as session, session.begin():
            session.execute(select(func.pg_advisory_xact_lock(func.hashtext(key))))
            existing = session.scalar(select(ExportJob).where(ExportJob.request_key == key))
            if existing:
                if existing.manifest["request"] != value.model_dump(mode="json"):
                    raise PlatformError(
                        "idempotency_conflict", "Key belongs to another export.", 409
                    )
                return ExportView.model_validate(existing)
            source: Run | Comparison | None = (
                session.get(Run, value.source_id)
                if value.source_kind == "run"
                else session.get(Comparison, value.source_id)
            )
            if source is None:
                raise PlatformError("export_source_missing", "Export source not found.", 404)
            allowed = TERMINAL if value.source_kind == "run" else {"completed", "failed"}
            if source.state not in allowed:
                raise PlatformError(
                    "export_source_active", "Wait for the source to reach a terminal state.", 409
                )
            run_selections = []
            if value.source_kind == "run":
                assert isinstance(source, Run)
                specs: list[dict[str, Any]] = [{"id": str(source.id), "all": True}]
            else:
                assert isinstance(source, Comparison)
                specs = [source.manifest[side] for side in ("baseline", "candidate")]  # type: ignore[misc]
            for spec in specs:
                run_id = UUID(spec["id"])
                run = session.get(Run, run_id)
                assert run
                if run.state not in TERMINAL:
                    raise PlatformError(
                        "export_source_active",
                        "Wait for referenced runs to finish before exporting.",
                        409,
                    )
                if spec.get("all"):
                    results = list(
                        session.scalars(
                            select(QuestionResult.id).where(QuestionResult.run_id == run_id)
                        ).all()
                    )
                    attempts = list(
                        session.scalars(select(RunAttempt.id).where(RunAttempt.run_id == run_id))
                    )
                    evaluation_rows = list(
                        session.execute(
                            select(
                                AnswerEvaluation.id,
                                AnswerEvaluation.state,
                                AnswerEvaluation.attempts,
                                AnswerEvaluation.manifest_hash,
                            )
                            .join(QuestionResult, QuestionResult.id == AnswerEvaluation.result_id)
                            .where(QuestionResult.run_id == run_id)
                        ).all()
                    )
                    evaluations = [
                        {
                            "id": str(e.id),
                            "state": e.state,
                            "attempts": e.attempts,
                            "manifest_hash": e.manifest_hash,
                        }
                        for e in evaluation_rows
                    ]
                else:
                    results = [UUID(row["result_id"]) for row in spec["observations"]]
                    cutoff = datetime.fromisoformat(str(source.manifest["cutoff"]))
                    attempts = list(
                        session.scalars(
                            select(RunAttempt.id).where(
                                RunAttempt.run_id == run_id,
                                RunAttempt.finished_at <= cutoff,
                                RunAttempt.state.in_(
                                    ["completed", "failed", "interrupted", "cancelled"]
                                ),
                            )
                        )
                    )
                    evaluations = []
                    for observation in spec["observations"]:
                        if not observation.get("evaluation_id"):
                            continue
                        states = {
                            metric["state"]
                            for name, metric in observation["metrics"].items()
                            if name
                            in (
                                "answer_correctness",
                                "faithfulness",
                                "citation_support",
                                "abstention_quality",
                            )
                        }
                        state = (
                            "failed"
                            if "error" in states
                            else "completed"
                            if "scored" in states
                            else "not_terminal_at_comparison"
                        )
                        evaluations.append(
                            {
                                "id": observation["evaluation_id"],
                                "state": state,
                                "manifest_hash": observation["evaluation_hash"],
                                "attempts": None,
                            }
                        )
                run_selections.append(
                    {
                        "id": str(run_id),
                        "manifest_hash": run.manifest_hash,
                        "result_ids": sorted(map(str, results)),
                        "attempt_ids": sorted(map(str, attempts)),
                        "evaluations": evaluations,
                    }
                )
            manifest = {
                "schema": "rag-evidence-export-v1",
                "request": value.model_dump(mode="json"),
                "source_id": str(value.source_id),
                "source_hash": source.manifest_hash,
                "source_state": source.state,
                "runs": run_selections,
                "execution": execution_identity(self.settings),
                "max_bytes": self.settings.max_export_bytes,
                "limitations": (
                    "No original uploaded binary files or model weights. Full "
                    "canonical corpus text, index chunks/vectors and snapshot lineage "
                    "are included. Pending evaluation output is not backfilled. "
                    "Comparison bundles retain frozen analysis and only "
                    "already-terminal attempts at its cutoff; accounting is the "
                    "original frozen projection."
                ),
            }
            row = ExportJob(
                run_id=value.source_id if value.source_kind == "run" else None,
                comparison_id=value.source_id if value.source_kind == "comparison" else None,
                request_key=key,
                manifest=manifest,
                manifest_hash=digest(manifest),
                max_attempts=self.settings.job_max_attempts,
            )
            session.add(row)
            session.flush()
            return ExportView.model_validate(row)

    def get(self, export_id: UUID) -> ExportView:
        with Session(self.engine) as session:
            row = session.get(ExportJob, export_id)
            if row is None:
                raise PlatformError("export_not_found", "Export not found.", 404)
            return ExportView.model_validate(row)

    def owned(self, session: Session, export_id: UUID, token: UUID) -> ExportJob:
        row = session.scalar(
            select(ExportJob)
            .where(
                ExportJob.id == export_id,
                ExportJob.state == "running",
                ExportJob.lease_token == token,
                ExportJob.lease_expires_at > func.clock_timestamp(),
            )
            .with_for_update()
        )
        if row is None:
            raise LostLease
        return row

    def claim(self) -> tuple[UUID, UUID] | None:
        with Session(self.engine) as session, session.begin():
            row = session.scalar(
                select(ExportJob)
                .where(
                    or_(
                        ExportJob.state == "pending",
                        and_(
                            ExportJob.state == "running",
                            ExportJob.lease_expires_at <= func.clock_timestamp(),
                        ),
                    )
                )
                .order_by(ExportJob.created_at, ExportJob.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if row is None:
                return None
            now: datetime = session.execute(select(func.clock_timestamp())).scalar_one()
            row.state, row.lease_token = "running", uuid4()
            row.lease_expires_at = now + timedelta(seconds=self.settings.job_lease_seconds)
            if row.attempts >= row.max_attempts:
                session.flush()
                row.state, row.output = (
                    "failed",
                    {
                        "error_code": "attempts_exhausted",
                        "error_message": "Export retry budget exhausted.",
                    },
                )
                row.lease_token = row.lease_expires_at = None
                return None
            row.attempts += 1
            return row.id, row.lease_token

    def heartbeat(self, export_id: UUID, token: UUID) -> None:
        with Session(self.engine) as session, session.begin():
            row = self.owned(session, export_id, token)
            now: datetime = session.execute(select(func.clock_timestamp())).scalar_one()
            row.lease_expires_at = now + timedelta(seconds=self.settings.job_lease_seconds)
        record_worker_heartbeat(self.engine)

    def complete(self, export_id: UUID, token: UUID, output: dict[str, Any]) -> None:
        with Session(self.engine) as session, session.begin():
            row = self.owned(session, export_id, token)
            row.output, row.state = output, "failed" if "error_code" in output else "completed"
            row.lease_token = row.lease_expires_at = None

    def artifact(self, export_id: UUID) -> Path:
        row = self.get(export_id)
        if row.state != "completed" or not row.output:
            raise PlatformError("export_not_ready", "Export is not ready.", 409)
        root = self.settings.artifact_root.resolve()
        path = (root / str(row.output["key"])).resolve()
        if (
            not path.is_relative_to(root)
            or not path.is_file()
            or path.stat().st_size != row.output["bytes"]
        ):
            raise PlatformError(
                "export_artifact_missing", "Export artifact is missing or invalid.", 410
            )
        return path

    def build(
        self, export_id: UUID, token: UUID, manifest: dict[str, Any], stop: Event, lost: Event
    ) -> dict[str, Any]:
        root = self.settings.artifact_root
        root.mkdir(parents=True, exist_ok=True)
        checksums: dict[str, str] = {}
        total = 0
        with TemporaryDirectory(prefix="export-", dir=root) as directory:
            target = Path(directory) / "bundle.zip"
            with ZipFile(target, "w", compression=ZIP_DEFLATED) as archive:

                def write(name: str, value: Any) -> None:
                    nonlocal total
                    if stop.is_set() or lost.is_set():
                        raise LostLease
                    data = (
                        json.dumps(
                            value,
                            sort_keys=True,
                            ensure_ascii=False,
                            allow_nan=False,
                            separators=(",", ":"),
                        )
                        + "\n"
                    ).encode()
                    total += len(data)
                    if total > self.settings.max_export_bytes or len(checksums) >= 20000:
                        raise PlatformError(
                            "export_capacity",
                            "Export exceeds the configured evidence bundle limit.",
                        )
                    info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                    info.compress_type = ZIP_DEFLATED
                    archive.writestr(info, data)
                    checksums[name] = hashlib.sha256(data).hexdigest()

                write("export-manifest.json", manifest)

                def write_query(name: str, query: str, params: dict[str, Any]) -> None:
                    nonlocal total
                    if len(checksums) >= 20000:
                        raise PlatformError("export_capacity", "Too many bundle entries.")
                    info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                    info.compress_type = ZIP_DEFLATED
                    hasher = hashlib.sha256()
                    with Session(self.engine) as session, archive.open(info, "w") as file:
                        values: ScalarResult[Any] = session.execute(
                            text(query), params, execution_options={"yield_per": 100}
                        ).scalars()
                        for value in values:
                            if stop.is_set() or lost.is_set():
                                raise LostLease
                            data = (
                                json.dumps(
                                    value,
                                    sort_keys=True,
                                    ensure_ascii=False,
                                    allow_nan=False,
                                    separators=(",", ":"),
                                )
                                + "\n"
                            ).encode()
                            total += len(data)
                            if total > self.settings.max_export_bytes:
                                raise PlatformError(
                                    "export_capacity", "Evidence bundle exceeds its byte limit."
                                )
                            file.write(data)
                            hasher.update(data)
                    checksums[name] = hasher.hexdigest()

                sources: set[UUID] = set()
                revisions: set[UUID] = set()
                documents: set[UUID] = set()
                indexes: set[str] = set()
                provenance: dict[str, Any] = {}
                written_code: set[str] = set()
                if manifest["request"]["source_kind"] == "comparison":
                    with Session(self.engine) as session:
                        write(
                            "comparison.json",
                            raw_row(session, "comparisons", UUID(manifest["source_id"])),
                        )
                for selection in manifest["runs"]:
                    prefix = f"runs/{selection['id']}"
                    with Session(self.engine) as session:
                        run = raw_row(session, "runs", UUID(selection["id"]))
                    if run["manifest_hash"] != selection["manifest_hash"]:
                        raise PlatformError(
                            "export_lineage", "Run hash differs from the export selection."
                        )
                    write(f"{prefix}/run.json", run)
                    project_root = Path(__file__).resolve().parents[4]
                    execution = run["manifest"]["execution"]
                    available: dict[str, Any] = {}
                    expected_files = dict(execution.get("source_files", {}))
                    expected_files.update(execution.get("lock_hashes", {}))
                    for filename, expected_hash in sorted(expected_files.items()):
                        path = (project_root / filename).resolve()
                        allowed = filename in ("uv.lock", "package-lock.json") or (
                            filename.startswith(("packages/", "services/", "migrations/"))
                            and filename.endswith(".py")
                        )
                        if (
                            not allowed
                            or not path.is_relative_to(project_root)
                            or not path.is_file()
                        ):
                            available[filename] = {
                                "state": "unavailable",
                                "expected_sha256": expected_hash,
                            }
                            continue
                        data = path.read_bytes()
                        if hashlib.sha256(data).hexdigest() != expected_hash:
                            available[filename] = {
                                "state": "unavailable",
                                "expected_sha256": expected_hash,
                            }
                            continue
                        available[filename] = {"state": "included", "sha256": expected_hash}
                        if expected_hash not in written_code:
                            written_code.add(expected_hash)
                            write(
                                f"provenance/files/{expected_hash}.json",
                                {"sha256": expected_hash, "utf8_content": data.decode("utf-8")},
                            )
                    provenance[selection["id"]] = available
                    corpus_id = run["manifest"]["corpus_version_id"]
                    with Session(self.engine) as session:
                        sources.update(
                            session.scalars(
                                text("""
                          SELECT s.id FROM source_sections s JOIN corpus_version_members m
                          ON m.revision_id=s.revision_id WHERE m.version_id=:id
                        """),
                                {"id": UUID(corpus_id)},
                            )
                        )
                    index_id = run["manifest"]["index_id"]
                    if index_id not in indexes:
                        indexes.add(index_id)
                        write_query(
                            f"indexes/{index_id}/index.jsonl",
                            "SELECT to_jsonb(t) FROM index_variants t WHERE id=:id",
                            {"id": UUID(index_id)},
                        )
                        write_query(
                            f"indexes/{index_id}/chunks.jsonl",
                            "SELECT to_jsonb(t) FROM index_chunks t "
                            "WHERE index_id=:id ORDER BY ordinal,id",
                            {"id": UUID(index_id)},
                        )
                        write_query(
                            f"indexes/{index_id}/embeddings.jsonl",
                            "SELECT to_jsonb(t) FROM chunk_embeddings t "
                            "WHERE index_id=:id ORDER BY chunk_id",
                            {"id": UUID(index_id)},
                        )
                    sources.update(section_ids(run["manifest"]["questions"]))
                    for table, ids in (
                        ("question_results", selection["result_ids"]),
                        ("run_attempts", selection["attempt_ids"]),
                    ):
                        for row_id in ids:
                            with Session(self.engine) as session:
                                value = raw_row(session, table, UUID(row_id))
                            if value["run_id"] != selection["id"]:
                                raise PlatformError(
                                    "export_lineage", "Result or attempt belongs to another run."
                                )
                            sources.update(section_ids(value["trace"]))
                            write(f"{prefix}/{table}/{row_id}.json", value)
                    for evaluation in selection["evaluations"]:
                        with Session(self.engine) as session:
                            value = raw_row(session, "answer_evaluations", UUID(evaluation["id"]))
                        if value["manifest_hash"] != evaluation["manifest_hash"]:
                            raise PlatformError(
                                "export_lineage",
                                "Evaluation hash differs from its frozen selection.",
                            )
                        if evaluation["state"] not in ("completed", "failed"):
                            value.update(
                                state=evaluation["state"],
                                output=None,
                                attempts=evaluation["attempts"],
                                lease_token=None,
                                lease_expires_at=None,
                            )
                        write(f"{prefix}/evaluations/{evaluation['id']}.json", value)
                    with Session(self.engine) as session:
                        for table, field in (
                            ("corpus_versions", "corpus_version_id"),
                            ("dataset_versions", "dataset_version_id"),
                        ):
                            write(
                                f"{prefix}/{table}.json",
                                raw_row(session, table, UUID(run["manifest"][field])),
                            )
                for source_id in sorted(sources):
                    with Session(self.engine) as session:
                        source = raw_row(session, "source_sections", source_id)
                    revisions.add(UUID(source["revision_id"]))
                    write(f"sources/sections/{source_id}.json", source)
                for revision_id in sorted(revisions):
                    with Session(self.engine) as session:
                        revision = raw_row(session, "document_revisions", revision_id)
                    documents.add(UUID(revision["document_id"]))
                    write(f"sources/revisions/{revision_id}.json", revision)
                for document_id in sorted(documents):
                    with Session(self.engine) as session:
                        write(
                            f"sources/documents/{document_id}.json",
                            raw_row(session, "documents", document_id),
                        )
                write("provenance/availability.json", provenance)
                write("checksums.json", dict(checksums))
            if stop.is_set() or lost.is_set():
                raise LostLease
            digestor = hashlib.sha256()
            with target.open("rb") as file:
                while block := file.read(1_048_576):
                    digestor.update(block)
            key = f"exports/{export_id}/{token}.zip"
            published = root / key
            published.parent.mkdir(parents=True, exist_ok=True)
            target.replace(published)
            return {
                "key": key,
                "bytes": published.stat().st_size,
                "sha256": digestor.hexdigest(),
                "uncompressed_bytes": total,
                "file_count": len(checksums),
                "format": "zip",
            }

    def process(self, export_id: UUID, token: UUID, stop: Event) -> None:
        lost, finished = Event(), Event()

        def keep_alive() -> None:
            while not finished.wait(self.settings.job_heartbeat_seconds):
                try:
                    self.heartbeat(export_id, token)
                except Exception:
                    lost.set()
                    return

        thread = Thread(target=keep_alive, daemon=True)
        thread.start()
        try:
            with Session(self.engine) as session:
                row = self.owned(session, export_id, token)
                manifest = row.manifest
                if (
                    manifest["max_bytes"] != self.settings.max_export_bytes
                    or digest(manifest) != row.manifest_hash
                    or manifest["execution"] != execution_identity(self.settings)
                ):
                    raise PlatformError(
                        "export_runtime_mismatch",
                        "Export source/runtime differs from its frozen submission.",
                    )
            output = self.build(export_id, token, manifest, stop, lost)
            if not stop.is_set() and not lost.is_set():
                self.complete(export_id, token, output)
        except LostLease:
            pass
        except Exception as error:
            if not stop.is_set() and not lost.is_set():
                safe = (
                    error
                    if isinstance(error, PlatformError)
                    else PlatformError("export_failed", "Export failed; no archive was published.")
                )
                with contextlib.suppress(LostLease):
                    self.complete(
                        export_id, token, {"error_code": safe.code, "error_message": safe.message}
                    )
        finally:
            finished.set()
            thread.join(timeout=2)
