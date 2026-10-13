"use client";

import { useState } from "react";
import useSWR from "swr";
import { allPages, corpusSchema, requestJSON, sectionSchema, versionSchema } from "@/lib/documents";
import { denseSearchSchema, indexSchema, searchSchema, type SearchResult } from "@/lib/indexes";

export function RetrievalWorkspace({ available, workerReady }: { available: boolean; workerReady: boolean }) {
  const [versionId, setVersionId] = useState("");
  const [selectedIndex, setSelectedIndex] = useState("");
  const [method, setMethod] = useState("lexical");
  const [searchId, setSearchId] = useState("");
  const [strategy, setStrategy] = useState("section");
  const [tokens, setTokens] = useState(256);
  const [overlap, setOverlap] = useState(0);
  const [query, setQuery] = useState("");
  const [budget, setBudget] = useState(1024);
  const [lexicalResult, setResult] = useState<SearchResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [source, setSource] = useState<{ corpusVersion: string; section: string; start: number; end: number } | null>(null);
  const versions = useSWR(available ? "retrieval-corpus-versions" : null, async () => {
    const corpora = await allPages("corpora", corpusSchema);
    return (await Promise.all(corpora.map(async corpus =>
      (await allPages(`corpora/${corpus.id}/versions`, versionSchema)).map(version => ({ ...version, corpusName: corpus.name }))
    ))).flat();
  }, { shouldRetryOnError: false });
  const indexes = useSWR(available ? "retrieval-indexes" : null, () => allPages("indexes", indexSchema), { refreshInterval: 3000, shouldRetryOnError: false });
  const indexId = selectedIndex || indexes.data?.[0]?.id || "";
  const current = indexes.data?.find(item => item.id === indexId);
  const isDense = current?.config.retrieval === "pgvector-exact-cosine-v1";
  const denseSearch = useSWR(searchId ? `dense-searches/${searchId}` : null,
    async (path: string) => denseSearchSchema.parse(await requestJSON(path)),
    { refreshInterval: data => data?.state === "completed" || data?.state === "failed" ? 0 : 1500, shouldRetryOnError: false });
  const searching = Boolean(searchId && (!denseSearch.data || ["pending", "running"].includes(denseSearch.data.state)));
  const result = searchId ? denseSearch.data?.result : lexicalResult;
  const corpusVersion = versionId || versions.data?.[0]?.id || "";
  const fetchError = indexes.error || versions.error || denseSearch.error;

  async function act(operation: () => Promise<void>) {
    setBusy(true); setError(""); setMessage("");
    try { await operation(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "The request failed."); }
    finally { setBusy(false); }
  }

  return <section className="retrieval-workspace" aria-labelledby="retrieval-title">
    <div className="section-topline"><h2 id="retrieval-title">Inspect a retrieval baseline</h2><span className="outline-tag">Lexical + dense</span></div>
    <p className="retrieval-intro">Build an index from a frozen corpus, then inspect ranked passages and the context that fits your budget. This preview does not generate answers or record an experiment run.</p>
    {!available && <p className="connection-message warning" role="status">Retrieval needs PostgreSQL and the current API. Check workspace setup.</p>}
    {available && !workerReady && <p className="connection-message warning" role="status">The worker is unavailable. New builds will wait in the durable queue.</p>}
    {fetchError && <p className="connection-message warning" role="alert">{fetchError instanceof Error ? fetchError.message : "Could not load retrieval resources."}</p>}
    {error && <p className="connection-message warning" role="alert">{error}</p>}
    {message && <p className="connection-message" role="status">{message}</p>}
    <form className="retrieval-form" onSubmit={event => { event.preventDefault(); void act(async () => {
      const index = indexSchema.parse(await requestJSON("indexes", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ corpus_version_id: corpusVersion, retrieval: method, chunking: { strategy, max_tokens: tokens, overlap_tokens: overlap } }) }));
      setSelectedIndex(index.id); setSearchId(""); setResult(null); setSource(null); await indexes.mutate();
      setMessage(index.state === "ready" ? "This configuration already has a ready index." : "Index queued. You can leave this page while the worker builds it.");
    }); }}>
      <div className="field"><label htmlFor="index-corpus">Published corpus</label><select id="index-corpus" value={corpusVersion} disabled={!available || busy || !versions.data?.length} onChange={event => setVersionId(event.target.value)}>
        {!versions.data?.length && <option value="">{versions.isLoading ? "Loading versions…" : "Publish a corpus first"}</option>}
        {versions.data?.map(item => <option key={item.id} value={item.id}>{item.corpusName} · v{item.version}</option>)}
      </select></div>
      <div className="field"><label htmlFor="index-method">Retrieval method</label><select id="index-method" value={method} disabled={busy} onChange={event => { setMethod(event.target.value); if (event.target.value === "dense") { setTokens(Math.min(tokens, 254)); setOverlap(Math.min(overlap, 253)); } }}><option value="lexical">Lexical · PostgreSQL full text</option><option value="dense">Dense · MiniLM cosine similarity</option></select></div>
      <div className="field"><label htmlFor="index-strategy">Chunking strategy</label><select id="index-strategy" value={strategy} disabled={busy} onChange={event => setStrategy(event.target.value)}><option value="section">Section boundaries</option><option value="fixed">Fixed token windows</option></select></div>
      <div className="field"><label htmlFor="chunk-tokens">Chunk token limit</label><input id="chunk-tokens" type="number" min={1} max={method === "dense" ? 254 : 4096} value={tokens} disabled={busy} required onChange={event => setTokens(Number(event.target.value))} /></div>
      <div className="field"><label htmlFor="chunk-overlap">Overlap tokens</label><input id="chunk-overlap" type="number" min={0} max={Math.min(tokens - 1, 1024)} value={overlap} disabled={busy} required onChange={event => setOverlap(Number(event.target.value))} /></div>
      <button className="button subtle" disabled={!available || !corpusVersion || busy}>{busy ? "Working…" : method === "dense" ? "Build dense index" : "Build lexical index"}</button>
    </form>
    <p className="muted-text">Lexical builds cache the pinned tokenizer. Dense builds also download MiniLM weights and embed chunks locally on the CPU. Dense chunks and queries fit 254 content tokens; no paid provider is needed.</p>
    <div className="field"><label htmlFor="active-index">Active index</label><select id="active-index" value={indexId} disabled={!available || busy || !indexes.data?.length} onChange={event => { setSelectedIndex(event.target.value); setSearchId(""); setResult(null); setSource(null); setMessage(""); }}>
      {!indexes.data?.length && <option value="">{indexes.isLoading ? "Loading indexes…" : "No indexes yet"}</option>}
      {indexes.data?.map(item => <option key={item.id} value={item.id}>{versions.data?.find(v => v.id === item.corpus_version_id)?.corpusName ?? "Corpus"} · {item.config.retrieval === "pgvector-exact-cosine-v1" ? "dense" : "lexical"} · {String((item.config.chunking as { strategy?: string })?.strategy ?? "chunks")} · {item.state} · {item.id.slice(0, 8)}</option>)}
    </select></div>
    {current && <div className="retrieval-index-status"><p><strong>{current.state === "ready" ? `${current.chunk_count} chunks ready` : `Build ${current.state}`}</strong> · {current.attempts} attempt{current.attempts === 1 ? "" : "s"}</p>
      {current.error_message && <p className="connection-message warning">{current.error_message}</p>}
      {current.state === "failed" && <button className="button subtle" disabled={busy} onClick={() => void act(async () => { await requestJSON(`indexes/${indexId}/retry`, { method: "POST" }); await indexes.mutate(); setMessage("Build queued for retry."); })}>Retry index build</button>}
    </div>}
    <form className="retrieval-form search-form" onSubmit={event => { event.preventDefault(); void act(async () => {
      setSource(null);
      const options = { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query, top_k: 5, context_tokens: budget }) };
      if (isDense) {
        const job = denseSearchSchema.parse(await requestJSON(`indexes/${indexId}/dense-searches`, options));
        setSearchId(job.id); setResult(null);
      } else {
        setSearchId("");
        setResult(searchSchema.parse(await requestJSON(`indexes/${indexId}/search`, options)));
      }
    }); }}>
      <div className="field"><label htmlFor="retrieval-query">Search the technical documents</label><input id="retrieval-query" value={query} maxLength={4000} required disabled={!available || busy} onChange={event => { setQuery(event.target.value); setSearchId(""); setResult(null); }} /></div>
      <div className="field"><label htmlFor="context-budget">Context token budget</label><input id="context-budget" type="number" min={0} max={8192} value={budget} required disabled={busy} onChange={event => { setBudget(Number(event.target.value)); setSearchId(""); setResult(null); }} /></div>
      <button className="button subtle" disabled={!available || current?.state !== "ready" || !query.trim() || busy || searching}>Inspect retrieval</button>
    </form>
    {searching && <p className="connection-message" role="status">Dense search {denseSearch.data?.state ?? "loading"}. The worker embeds the query locally, then searches all vectors in this index.</p>}
    {denseSearch.data?.state === "failed" && <div className="connection-message warning" role="alert"><p>{denseSearch.data.error_message}</p><button className="button subtle" disabled={busy} onClick={() => void act(async () => { await requestJSON(`dense-searches/${searchId}/retry`, { method: "POST" }); await denseSearch.mutate(); })}>Retry dense search</button></div>}
    {result && <div className="retrieval-results">
      <div className="section-topline"><h3>Results for “{result.query}”</h3><span className="muted-text">{result.returned_count} passage{result.returned_count === 1 ? "" : "s"} · top 5</span></div>
      <div className="source-section"><h3>Delivered context</h3><p>{result.context.token_count} / {result.context.token_budget} tokens · {result.context.truncated_chunk_ids.length} truncated · {result.context.omitted_chunk_ids.length} omitted</p>
        <pre>{result.context.text || "No source text delivered."}</pre></div>
      <h3>Ranked passages before packing</h3>
      {!result.hits.length && <p>No matching passages. Try terms that appear in the document.</p>}
      {result.hits.map(hit => <article className="source-section" key={hit.chunk.id}>
        <h4>Passage {hit.rank} · chunk {hit.chunk.ordinal + 1}</h4><p className="muted-text">{result.strategy === "pgvector-exact-cosine-v1" ? "Cosine similarity" : "Lexical rank score"} {hit.score.toFixed(4)} · {hit.chunk.token_count} tokens</p>
        <pre>{hit.chunk.text}</pre>
        <ul className="retrieval-lineage">{hit.chunk.spans.map((span, i) => <li key={i}><span>Section {span.section_id.slice(0, 8)} · characters {span.start_offset}–{span.end_offset}</span>{current && <button className="button subtle" onClick={() => setSource({ corpusVersion: current.corpus_version_id, section: span.section_id, start: span.start_offset, end: span.end_offset })}>Inspect source</button>}</li>)}</ul>
      </article>)}
      <p className="muted-text">Retrieval scores are not correctness scores. Dataset scoring and saved experiment traces arrive with durable runs.</p>
      {source && <SourceExcerpt source={source} onClose={() => setSource(null)} />}
    </div>}
  </section>;
}

function SourceExcerpt({ source, onClose }: { source: { corpusVersion: string; section: string; start: number; end: number }; onClose: () => void }) {
  const section = useSWR(`retrieval-source/${source.corpusVersion}/${source.section}`, async () => sectionSchema.parse(await requestJSON(`corpus-versions/${source.corpusVersion}/sections/${source.section}`)), { shouldRetryOnError: false });
  const text = section.data ? Array.from(section.data.text) : [];
  const start = Math.max(0, source.start - 160);
  const end = Math.min(text.length, source.end + 160);
  return <section className="source-section" aria-label="Canonical source excerpt">
    <div className="section-topline"><h3>Canonical source excerpt</h3><button className="button subtle" onClick={onClose}>Close source</button></div>
    {section.isLoading && <p role="status">Loading canonical evidence…</p>}
    {section.error && <p role="alert">Could not load the source. Close and try again.</p>}
    {section.data && <><p>{section.data.document_name ?? "Source document"} · {section.data.heading_path.join(" / ") || "Untitled section"}</p>
      <p className="muted-text">Canonical characters {source.start}–{source.end}, highlighted. Source offsets count Unicode code points.</p>
      <pre>{start > 0 ? "…" : ""}{text.slice(start, source.start).join("")}<mark>{text.slice(source.start, source.end).join("")}</mark>{text.slice(source.end, end).join("")}{end < text.length ? "…" : ""}</pre></>}
  </section>;
}
