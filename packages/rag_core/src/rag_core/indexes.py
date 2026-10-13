"""Published corpus indexing, leased worker execution, and PostgreSQL lexical inspection."""

import contextlib
import hashlib
import json
from datetime import datetime, timedelta
from threading import Event, Thread
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import Engine, and_, func, or_, select, text
from sqlalchemy.orm import Session

from rag_core.chunking import CHUNKING_VERSION, CanonicalSection, Chunk, ChunkConfig, build_chunks
from rag_core.context import PackedContext, pack_context
from rag_core.database import record_worker_heartbeat
from rag_core.embeddings import (
    DENSE_STRATEGY,
    MAX_CONTENT_TOKENS,
    EmbeddingOutput,
    embedding_contract,
    run_embeddings,
    vector_literal,
)
from rag_core.errors import LostLease, PlatformError
from rag_core.index_models import IndexChunk, IndexVariant
from rag_core.models import CorpusVersion, CorpusVersionMember, SourceSection
from rag_core.schemas import Page
from rag_core.settings import Settings
from rag_core.tokenization import (
    BASELINE_TOKENIZER_ID,
    BASELINE_TOKENIZER_REVISION,
    PinnedTokenizer,
)


class IndexCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    corpus_version_id: UUID
    chunking: ChunkConfig = ChunkConfig()
    retrieval: Literal["lexical", "dense"] = "lexical"

    @model_validator(mode="after")
    def compatible_chunks(self) -> "IndexCreate":
        if self.retrieval == "dense" and self.chunking.max_tokens > MAX_CONTENT_TOKENS:
            raise ValueError("MiniLM dense chunks must contain at most 254 content tokens.")
        return self


class IndexView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    corpus_version_id: UUID
    fingerprint: str
    config: dict[str, object]
    state: Literal["pending", "running", "ready", "failed"]
    chunk_count: int
    manifest: dict[str, object] | None
    attempts: int
    error_code: str | None
    error_message: str | None
    created_at: datetime


class SearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    query: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=50)
    context_tokens: int = Field(default=1024, ge=0, le=8192)


class SearchHit(BaseModel):
    rank: int
    score: float
    chunk: Chunk


class SearchView(BaseModel):
    index_id: UUID
    strategy: str = "postgresql-fts-english-ts-rank-cd-v1"
    query: str
    returned_count: int
    hits: list[SearchHit]
    context: PackedContext
    embedding: dict[str, object] | None = None


class IndexStore:
    def __init__(self, engine: Engine, settings: Settings) -> None:
        self.engine, self.settings = engine, settings

    def create(self, value: IndexCreate) -> IndexView:
        config: dict[str, object] = {
            "chunking": value.chunking.model_dump(),
            "chunking_version": CHUNKING_VERSION,
            "tokenizer_id": BASELINE_TOKENIZER_ID,
            "tokenizer_revision": BASELINE_TOKENIZER_REVISION,
            "tokenizers_version": "0.23.3",
            "retrieval": "postgresql-fts-english-ts-rank-cd-v1",
        }
        if value.retrieval == "dense":
            config["retrieval"] = DENSE_STRATEGY
            config["embedding"] = embedding_contract()
        with Session(self.engine) as session, session.begin():
            corpus = session.scalar(
                select(CorpusVersion)
                .where(CorpusVersion.id == value.corpus_version_id, CorpusVersion.sealed.is_(True))
                .with_for_update()
            )
            if corpus is None:
                raise PlatformError("corpus_version_not_found", "Choose a published corpus.", 404)
            fingerprint = hashlib.sha256(
                json.dumps(
                    {
                        "corpus_version_id": str(corpus.id),
                        "corpus_hash": corpus.manifest_hash,
                        "config": config,
                    },
                    sort_keys=True,
                ).encode()
            ).hexdigest()
            existing = session.scalar(
                select(IndexVariant).where(IndexVariant.fingerprint == fingerprint)
            )
            if existing:
                return IndexView.model_validate(existing)
            variant = IndexVariant(
                corpus_version_id=corpus.id,
                fingerprint=fingerprint,
                config=config,
                max_attempts=self.settings.job_max_attempts,
            )
            session.add(variant)
            session.flush()
            return IndexView.model_validate(variant)

    def get(self, index_id: UUID) -> IndexView:
        with Session(self.engine) as session:
            variant = session.get(IndexVariant, index_id)
            if variant is None:
                raise PlatformError("index_not_found", "Index not found.", 404)
            return IndexView.model_validate(variant)

    def list(self, limit: int, offset: int) -> Page[IndexView]:
        with Session(self.engine) as session:
            rows = list(
                session.scalars(
                    select(IndexVariant)
                    .order_by(IndexVariant.created_at.desc(), IndexVariant.id)
                    .offset(offset)
                    .limit(limit + 1)
                )
            )
            return Page(
                items=[IndexView.model_validate(row) for row in rows[:limit]],
                next_cursor=str(offset + limit) if len(rows) > limit else None,
            )

    def retry(self, index_id: UUID) -> IndexView:
        with Session(self.engine) as session, session.begin():
            row = session.scalar(
                select(IndexVariant).where(IndexVariant.id == index_id).with_for_update()
            )
            if row is None:
                raise PlatformError("index_not_found", "Index not found.", 404)
            if row.state != "failed":
                raise PlatformError("index_not_failed", "Only a failed build can be retried.", 409)
            row.state, row.attempts = "pending", 0
            row.error_code = row.error_message = None
            row.available_at = session.execute(select(func.clock_timestamp())).scalar_one()
            return IndexView.model_validate(row)

    def search(self, index_id: UUID, value: SearchInput) -> SearchView:
        variant = self.get(index_id)
        if variant.state != "ready":
            raise PlatformError("index_not_ready", "Wait for the index build to finish.", 409)
        if variant.config["retrieval"] == DENSE_STRATEGY:
            raise PlatformError(
                "dense_preview_required", "Queue dense queries for worker execution.", 409
            )
        tokenizer = PinnedTokenizer.load(self.settings.model_cache_dir)
        if not variant.manifest or variant.manifest.get("tokenizer") != tokenizer.identity:
            raise PlatformError(
                "tokenizer_mismatch", "The tokenizer differs from this index build.", 409
            )
        with self.engine.connect() as connection:
            rows = connection.execute(
                text("""
                SELECT id,ordinal,text,token_count,spans,ts_rank_cd(search_vector,q) AS score
                FROM index_chunks, plainto_tsquery('english'::regconfig,:query) q
                WHERE index_id=:index_id AND search_vector @@ q
                ORDER BY score DESC,ordinal,id LIMIT :top_k
            """),
                {"query": value.query, "index_id": index_id, "top_k": value.top_k},
            ).mappings()
            hits = [
                SearchHit(
                    rank=rank,
                    score=row["score"],
                    chunk=Chunk.model_validate(
                        {key: row[key] for key in ("id", "ordinal", "text", "token_count", "spans")}
                    ),
                )
                for rank, row in enumerate(rows, 1)
            ]
        return SearchView(
            index_id=index_id,
            query=value.query,
            returned_count=len(hits),
            hits=hits,
            context=pack_context([hit.chunk for hit in hits], tokenizer, value.context_tokens),
        )

    def dense_result(
        self, index_id: UUID, value: SearchInput, encoded: EmbeddingOutput
    ) -> SearchView:
        variant = self.get(index_id)
        if (
            variant.state != "ready"
            or variant.config.get("retrieval") != DENSE_STRATEGY
            or variant.config.get("embedding") != encoded.metadata["contract"]
        ):
            raise PlatformError(
                "embedding_mismatch", "Query model is incompatible with this index.", 409
            )
        assert variant.manifest is not None
        built = variant.manifest.get("embedding")
        if not isinstance(built, dict) or built.get("artifact_hashes") != encoded.metadata.get(
            "artifact_hashes"
        ):
            raise PlatformError(
                "embedding_artifact_mismatch", "Query artifacts differ from index artifacts.", 409
            )
        tokenizer = PinnedTokenizer.load(self.settings.model_cache_dir)
        if variant.manifest.get("tokenizer") != tokenizer.identity:
            raise PlatformError("tokenizer_mismatch", "Tokenizer differs from this index.", 409)
        query = vector_literal(encoded.vectors[0])
        with self.engine.connect() as connection:
            # No ANN index exists: the baseline searches every compatible vector in this variant.
            rows = connection.execute(
                text("""
                SELECT c.id,c.ordinal,c.text,c.token_count,c.spans,
                       1-(e.embedding <=> CAST(:query AS vector(384))) AS score
                FROM chunk_embeddings e JOIN index_chunks c ON c.id=e.chunk_id
                WHERE e.index_id=:index AND e.compatibility_key=:key
                ORDER BY e.embedding <=> CAST(:query AS vector(384)),c.ordinal,c.id LIMIT :top_k
            """),
                {
                    "query": query,
                    "index": index_id,
                    "key": embedding_contract()["compatibility_key"],
                    "top_k": value.top_k,
                },
            ).mappings()
            hits = [
                SearchHit(
                    rank=rank,
                    score=row["score"],
                    chunk=Chunk.model_validate(
                        {key: row[key] for key in ("id", "ordinal", "text", "token_count", "spans")}
                    ),
                )
                for rank, row in enumerate(rows, 1)
            ]
        return SearchView(
            index_id=index_id,
            strategy=DENSE_STRATEGY,
            query=value.query,
            returned_count=len(hits),
            hits=hits,
            embedding=encoded.metadata,
            context=pack_context([hit.chunk for hit in hits], tokenizer, value.context_tokens),
        )


class IndexQueue(IndexStore):
    def claim(self) -> tuple[UUID, UUID] | None:
        with Session(self.engine) as session, session.begin():
            eligible = or_(
                and_(
                    IndexVariant.state == "pending",
                    IndexVariant.available_at <= func.clock_timestamp(),
                ),
                and_(
                    IndexVariant.state == "running",
                    IndexVariant.lease_expires_at <= func.clock_timestamp(),
                ),
            )
            while row := session.scalar(
                select(IndexVariant)
                .where(eligible)
                .order_by(IndexVariant.created_at, IndexVariant.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            ):
                if row.attempts >= row.max_attempts:
                    row.state, row.error_code = "failed", "attempts_exhausted"
                    row.error_message = "Index build exhausted its retry budget."
                    row.lease_token = row.lease_expires_at = None
                    session.flush()
                    continue
                now: datetime = session.execute(select(func.clock_timestamp())).scalar_one()
                row.state, row.lease_token = "running", uuid4()
                row.attempts += 1
                row.lease_expires_at = now + timedelta(seconds=self.settings.job_lease_seconds)
                return row.id, row.lease_token
        return None

    def owned(self, session: Session, index_id: UUID, token: UUID) -> IndexVariant:
        row = session.scalar(
            select(IndexVariant)
            .where(
                IndexVariant.id == index_id,
                IndexVariant.state == "running",
                IndexVariant.lease_token == token,
                IndexVariant.lease_expires_at > func.clock_timestamp(),
            )
            .with_for_update()
        )
        if row is None:
            raise LostLease
        return row

    def heartbeat(self, index_id: UUID, token: UUID) -> None:
        with Session(self.engine) as session, session.begin():
            row = self.owned(session, index_id, token)
            now: datetime = session.execute(select(func.clock_timestamp())).scalar_one()
            row.lease_expires_at = now + timedelta(seconds=self.settings.job_lease_seconds)
        record_worker_heartbeat(self.engine)

    def complete(
        self,
        index_id: UUID,
        token: UUID,
        chunks: list[Chunk],
        tokenizer: PinnedTokenizer,
        encoded: EmbeddingOutput | None = None,
    ) -> None:
        with Session(self.engine) as session, session.begin():
            row = self.owned(session, index_id, token)
            corpus = session.get(CorpusVersion, row.corpus_version_id)
            assert corpus is not None
            # One atomic publication: a crash leaves no partial chunks to duplicate on retry.
            session.add_all(
                [
                    IndexChunk(
                        id=chunk.id,
                        index_id=index_id,
                        ordinal=chunk.ordinal,
                        text=chunk.text,
                        token_count=chunk.token_count,
                        spans=[span.model_dump(mode="json") for span in chunk.spans],
                    )
                    for chunk in chunks
                ]
            )
            session.flush()
            dense = row.config.get("retrieval") == DENSE_STRATEGY
            if dense:
                if (
                    encoded is None
                    or len(encoded.vectors) != len(chunks)
                    or row.config.get("embedding") != encoded.metadata["contract"]
                ):
                    raise PlatformError("embedding_mismatch", "Index embeddings are incompatible.")
                session.execute(
                    text("""
                    INSERT INTO chunk_embeddings(chunk_id,index_id,compatibility_key,embedding)
                    VALUES(:chunk,:index,:key,CAST(:vector AS vector(384)))
                """),
                    [
                        {
                            "chunk": chunk.id,
                            "index": index_id,
                            "key": embedding_contract()["compatibility_key"],
                            "vector": vector_literal(vector),
                        }
                        for chunk, vector in zip(chunks, encoded.vectors, strict=True)
                    ],
                )
            elif encoded is not None:
                raise PlatformError(
                    "unexpected_embeddings", "Lexical index cannot publish vectors."
                )
            now: datetime = session.execute(select(func.clock_timestamp())).scalar_one()
            if row.lease_expires_at is None or row.lease_expires_at <= now:
                raise LostLease
            digest = hashlib.sha256()
            for chunk in chunks:
                digest.update(chunk.model_dump_json().encode())
                digest.update(b"\n")
            row.manifest = {
                "schema": "dense-index-v1" if dense else "lexical-index-v1",
                "corpus_hash": corpus.manifest_hash,
                "tokenizer": tokenizer.identity,
                "chunk_hash": digest.hexdigest(),
                "chunk_count": len(chunks),
                "config": row.config,
            }
            if encoded:
                row.manifest["embedding"] = encoded.metadata
            row.chunk_count, row.state = len(chunks), "ready"
            row.lease_token = row.lease_expires_at = None
            row.error_code = row.error_message = None

    def fail(self, index_id: UUID, token: UUID, error: PlatformError) -> None:
        with Session(self.engine) as session, session.begin():
            row = self.owned(session, index_id, token)
            row.state = (
                "pending" if error.retryable and row.attempts < row.max_attempts else "failed"
            )
            now: datetime = session.execute(select(func.clock_timestamp())).scalar_one()
            row.available_at = now + timedelta(seconds=2**row.attempts)
            row.error_code, row.error_message = error.code, error.message
            row.lease_token = row.lease_expires_at = None

    def process(self, index_id: UUID, token: UUID, stop: Event) -> None:
        finished, lost = Event(), Event()

        def keep_alive() -> None:
            while not finished.wait(self.settings.job_heartbeat_seconds):
                try:
                    self.heartbeat(index_id, token)
                except Exception:
                    lost.set()
                    return

        thread = Thread(target=keep_alive, daemon=True)
        thread.start()
        try:
            with Session(self.engine) as session:
                row = self.owned(session, index_id, token)
                config = ChunkConfig.model_validate(row.config["chunking"])
                dense = row.config.get("retrieval") == DENSE_STRATEGY
                sections: list[CanonicalSection] = []
                characters = 0
                sources = session.scalars(
                    select(SourceSection)
                    .join(
                        CorpusVersionMember,
                        CorpusVersionMember.revision_id == SourceSection.revision_id,
                    )
                    .where(CorpusVersionMember.version_id == row.corpus_version_id)
                    .order_by(SourceSection.revision_id, SourceSection.ordinal)
                    .execution_options(yield_per=100)
                )
                for source in sources:
                    characters += len(source.text) + 2
                    if characters > 20_000_000 or len(sections) >= 100_000:
                        raise PlatformError(
                            "index_capacity", "Index exceeds the local build capacity."
                        )
                    sections.append(
                        CanonicalSection(source.id, source.revision_id, source.ordinal, source.text)
                    )
            tokenizer = PinnedTokenizer.load(self.settings.model_cache_dir, allow_download=True)
            chunks = build_chunks(sections, config, tokenizer, index_id)
            encoded = None
            if dense:
                if len(chunks) > self.settings.max_dense_chunks:
                    raise PlatformError(
                        "dense_capacity", "Dense index exceeds the configured chunk limit."
                    )
                encoded = run_embeddings(
                    [chunk.text for chunk in chunks], self.settings, stop, lost, allow_download=True
                )
            if not stop.is_set() and not lost.is_set():
                self.complete(index_id, token, chunks, tokenizer, encoded)
        except LostLease:
            pass
        except Exception as error:
            if not stop.is_set() and not lost.is_set():
                with contextlib.suppress(LostLease):
                    self.fail(
                        index_id,
                        token,
                        error
                        if isinstance(error, PlatformError)
                        else PlatformError(
                            "index_build_failed",
                            "Index build failed. Inspect configuration and retry.",
                        ),
                    )
        finally:
            finished.set()
            thread.join(timeout=2)
