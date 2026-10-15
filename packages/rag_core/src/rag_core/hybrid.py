"""Rank fusion on the SAME immutable dense index's lexical/vector chunk universe."""

import time
from collections.abc import Callable
from threading import Event
from uuid import UUID

from rag_core.chunking import Chunk
from rag_core.embeddings import run_embeddings
from rag_core.errors import LostLease, PlatformError
from rag_core.indexes import IndexStore, SearchHit, SearchInput, SearchView
from rag_core.reranking import RerankInput, rerank, reranker_contract
from rag_core.settings import Settings

FUSION_VERSION = "equal-weight-rrf-v1"


def fusion_contract() -> dict[str, object]:
    return {
        "version": FUSION_VERSION,
        "lexical_weight": 1,
        "dense_weight": 1,
        "rank_base": 1,
        "deduplication": "immutable-chunk-id-per-arm",
        "tie_break": "chunk-ordinal-then-id",
        "lexical_query": "english-plainto-tsquery",
    }


def fuse_hits(lexical: list[SearchHit], dense: list[SearchHit], rrf_k: int) -> list[SearchHit]:
    if not 1 <= rrf_k <= 1000:
        raise PlatformError("invalid_fusion", "RRF constant is out of bounds.")
    chunks: dict[UUID, Chunk] = {}
    scores: dict[UUID, float] = {}
    for arm in (lexical, dense):
        seen: set[UUID] = set()
        for hit in arm:
            if hit.rank < 1:
                raise PlatformError("invalid_fusion", "RRF ranks must start at one.")
            if hit.chunk.id in chunks and chunks[hit.chunk.id] != hit.chunk:
                raise PlatformError("fusion_lineage_mismatch", "Fusion chunk content differs.")
            if hit.chunk.id in seen:
                continue
            seen.add(hit.chunk.id)
            chunks[hit.chunk.id] = hit.chunk
            scores[hit.chunk.id] = scores.get(hit.chunk.id, 0) + 1 / (rrf_k + hit.rank)
    ordered = sorted(chunks, key=lambda item: (-scores[item], chunks[item].ordinal, str(item)))
    return [
        SearchHit(rank=i, score=scores[item], chunk=chunks[item])
        for i, item in enumerate(ordered, 1)
    ]


def hybrid_retrieve(
    store: IndexStore,
    index_id: UUID,
    query: str,
    top_k: int,
    candidate_k: int,
    rrf_k: int,
    use_reranker: bool,
    settings: Settings,
    stop: Event,
    lost: Event,
    checkpoint: Callable[[SearchView], None] | None = None,
) -> SearchView:
    if not top_k <= candidate_k <= 50:
        raise PlatformError("invalid_candidates", "Candidate depth must cover top-k and fit 50.")
    value = SearchInput(query=query, top_k=candidate_k, context_tokens=0)
    timings: dict[str, float] = {}
    started = time.monotonic()
    lexical = store.search(index_id, value, allow_dense_lexical=True)
    timings["lexical_wall_ms"] = (time.monotonic() - started) * 1000
    if stop.is_set() or lost.is_set():
        raise LostLease
    started = time.monotonic()
    encoded = run_embeddings([query], settings, stop, lost)
    timings["query_embedding_wall_ms"] = (time.monotonic() - started) * 1000
    started = time.monotonic()
    dense = store.dense_result(index_id, value, encoded)
    timings["dense_search_wall_ms"] = (time.monotonic() - started) * 1000
    started = time.monotonic()
    fused = fuse_hits(lexical.hits, dense.hits, rrf_k)
    candidates = fused[:candidate_k]
    timings["fusion_wall_ms"] = (time.monotonic() - started) * 1000
    pipeline: dict[str, object] = {
        "fusion": fusion_contract(),
        "candidate_k": candidate_k,
        "rrf_k": rrf_k,
        "lexical": [
            {"chunk_id": str(h.chunk.id), "rank": h.rank, "score": h.score} for h in lexical.hits
        ],
        "dense": [
            {"chunk_id": str(h.chunk.id), "rank": h.rank, "score": h.score} for h in dense.hits
        ],
        "fused": [{"chunk_id": str(h.chunk.id), "rank": h.rank, "score": h.score} for h in fused],
        "reranker": None,
        "timings": timings,
    }
    hits = candidates[:top_k]
    if use_reranker and candidates:
        if checkpoint:
            checkpoint(
                dense.model_copy(
                    update={
                        "strategy": "hybrid-rrf-v1",
                        "returned_count": len(candidates),
                        "hits": candidates,
                        "pipeline": pipeline,
                    }
                )
            )
        if stop.is_set() or lost.is_set():
            raise LostLease
        started = time.monotonic()
        ranked = rerank(
            RerankInput(
                query=query,
                passages=[h.chunk for h in candidates],
                threads=settings.reranker_threads,
                batch_size=settings.reranker_batch_size,
            ),
            settings,
            stop,
            lost,
        )
        if ranked.metadata["contract"] != reranker_contract() or ranked.passage_ids != [
            h.chunk.id for h in candidates
        ]:
            raise PlatformError("reranker_result_mismatch", "Reranking candidates differ.")
        order = sorted(
            range(len(candidates)),
            key=lambda i: (
                -ranked.scores[i],
                candidates[i].chunk.ordinal,
                str(candidates[i].chunk.id),
            ),
        )
        hits = [
            SearchHit(rank=rank, score=ranked.scores[i], chunk=candidates[i].chunk)
            for rank, i in enumerate(order[:top_k], 1)
        ]
        timings["reranking_wall_ms"] = (time.monotonic() - started) * 1000
        pipeline["reranker"] = ranked.model_dump(mode="json")
    return dense.model_copy(
        update={
            "strategy": "hybrid-rrf-cross-encoder-v1" if use_reranker else "hybrid-rrf-v1",
            "returned_count": len(hits),
            "hits": hits,
            "pipeline": pipeline,
        }
    )
