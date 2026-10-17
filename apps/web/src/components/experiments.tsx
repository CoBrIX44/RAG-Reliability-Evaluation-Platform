"use client";

import Link from "next/link";
import { ExportButton } from "@/components/export-button";
import { FailureExplorer } from "@/components/failure-explorer";
import { AnswerEvaluation } from "@/components/answer-evaluation";
import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { allPages, pageSchema, requestJSON, sectionSchema } from "@/lib/documents";
import { datasetSchema, datasetVersionSchema } from "@/lib/datasets";
import { indexSchema } from "@/lib/indexes";
import { attemptSchema, displayState, experimentSchema, metricNames, resultSchema, resultSummarySchema, runSchema, terminal, strategyLabel, rankingLabel, type Result, type Run } from "@/lib/runs";

export function ExperimentWorkspace({ available, configured, workerReady, initialRunId, initialResultId, failureRunId }: { available: boolean; configured: boolean; workerReady: boolean; initialRunId?: string; initialResultId?: string; failureRunId?: string }) {
  const router = useRouter();
  const [name, setName] = useState("");
  const [datasetId, setDatasetId] = useState("");
  const [indexId, setIndexId] = useState("");
  const [retrievalStrategy, setRetrievalStrategy] = useState("index");
  const [candidateK, setCandidateK] = useState(20);
  const [rrfK, setRrfK] = useState(60);
  const [split, setSplit] = useState("development");
  const [topK, setTopK] = useState(5);
  const [budget, setBudget] = useState(1024);
  const [output, setOutput] = useState(128);
  const [repeats, setRepeats] = useState(1);
  const [seed, setSeed] = useState(0);
  const [cacheCondition, setCacheCondition] = useState("uncontrolled");
  const [measurementNotes, setMeasurementNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [offset, setOffset] = useState(0);
  const [runFilter, setRunFilter] = useState("all");
  const submission = useRef<{ fingerprint: string; key: string } | null>(null);
  const versions = useSWR(available ? "experiment-datasets" : null, async () => {
    const datasets = await allPages("datasets", datasetSchema);
    return (await Promise.all(datasets.map(async dataset => (await allPages(`datasets/${dataset.id}/versions`, datasetVersionSchema)).map(version => ({ ...version, name: dataset.name, purpose: dataset.purpose, corpus: dataset.corpus_version_id }))))).flat();
  }, { shouldRetryOnError: false });
  const indexes = useSWR(available ? "retrieval-indexes" : null, () => allPages("indexes", indexSchema), { refreshInterval: 5000, shouldRetryOnError: false });
  const experiments = useSWR(available ? "saved-experiments" : null, () => allPages("experiments", experimentSchema), { shouldRetryOnError: false });
  const runs = useSWR(available ? `runs?limit=20&cursor=${offset}` : null, async path => pageSchema(runSchema).parse(await requestJSON(path)), { refreshInterval: 3000, shouldRetryOnError: false });
  const selectedDataset = versions.data?.find(item => item.id === datasetId) ?? versions.data?.[0];
  const readyIndexes = indexes.data?.filter(item => item.state === "ready" && item.corpus_version_id === selectedDataset?.corpus && (retrievalStrategy === "index" || item.config.retrieval === "pgvector-exact-cosine-v1")) ?? [];
  const selectedIndex = readyIndexes.find(item => item.id === indexId) ?? readyIndexes[0];
  const loadError = versions.error || indexes.error || runs.error || experiments.error;
  const visibleRuns = runs.data?.items.filter(run => runFilter === "all" || (runFilter === "active" ? !terminal(run.state) : runFilter === "completed" ? run.state === "completed" : run.failed_count > 0 || run.state === "failed" || run.state === "completed_with_errors")) ?? [];

  if (failureRunId) return <FailureExplorer runId={failureRunId} available={available} />;
  return <section className="experiment-workspace" aria-labelledby="experiment-title">
    {initialRunId ? <><Link className="text-link" href="/experiments">← All experiments</Link><RunDetail key={initialRunId} id={initialRunId} available={available} initialResultId={initialResultId} /></> : <>
      <section className="saved-runs" aria-label="Saved experiment runs">
      <div className="section-topline run-list-toolbar"><div><h2>Recent experiment runs</h2><p className="muted-text">Saved results on page {Math.floor(offset / 20) + 1}</p></div>
        <label className="run-filter">Show<select aria-label="Filter saved runs on this page" value={runFilter} onChange={event => setRunFilter(event.target.value)}><option value="all">All runs</option><option value="active">Active</option><option value="completed">Completed</option><option value="attention">Needs attention</option></select></label>
      </div>
      {runs.isLoading && <p role="status">Loading saved runs…</p>}
      {runs.data && !runs.data.items.length && <div className="table-frame empty-state"><h3>No saved runs yet.</h3><p>Start a run from a published dataset. Results and evidence will appear here as each question completes.</p></div>}
      {!!runs.data?.items.length && !visibleRuns.length && <p className="connection-message" role="status">No runs match this filter on the current page. Choose All runs or another page.</p>}
      {!!visibleRuns.length && <div className="run-list">{visibleRuns.map(run => <div className="run-list-row" data-state={run.state} key={run.id}>
        <div><Link className="text-link" href={`/runs/${run.id}`}>{experiments.data?.find(item => item.id === run.experiment_id)?.name ?? `Run ${run.id.slice(0, 8)}`}</Link><p className="muted-text">{strategyLabel(run.manifest_summary.config.retrieval_strategy)} · {run.manifest_summary.purpose === "development_fixture" ? "Development fixture" : "Research dataset"} · {new Date(run.created_at).toLocaleString()}</p></div>
        <div><span className={`run-state ${run.state.includes("errors") || run.state === "failed" ? "has-errors" : ""}`}>{displayState(run.state)}</span><p className="muted-text">{run.completed_count + run.failed_count}/{run.total_count} observations · {run.failed_count} failed</p></div>
      </div>)}</div>}
      {(offset > 0 || runs.data?.next_cursor) && <div className="inline-actions source-pagination"><button className="button subtle" disabled={offset === 0 || runs.isLoading} onClick={() => setOffset(Math.max(0, offset - 20))}>Newer runs</button><button className="button subtle" disabled={!runs.data?.next_cursor || runs.isLoading} onClick={() => setOffset(Number(runs.data?.next_cursor))}>Older runs</button></div>}
      </section>
      <details id="experiment-configuration" className="tool-disclosure experiment-composer" open>
        <summary><span>New experiment</span><span className="muted-text">Configure a controlled comparison</span></summary><div className="disclosure-body">
      <div className="section-topline"><h2 id="experiment-title">Run an experiment</h2><span className="outline-tag">Local CPU baseline</span></div>
      <p className="retrieval-intro">Freeze a reviewed dataset and a ready index. Compare an index baseline with hybrid rank fusion or cross-encoder reranking while keeping the local answer model and evidence budget fixed.</p>
      {!available && <p className="connection-message warning" role="status">Runs need PostgreSQL and the current API. <Link href="/settings">Check workspace setup.</Link></p>}
      {available && !configured && <p className="connection-message warning" role="status">Local answer generation is disabled. Enable LOCAL_GENERATION_ENABLED in the server environment and restart the API and worker.</p>}
      {available && !workerReady && <p className="connection-message warning" role="status">The worker is unavailable. Submitted runs will wait in the durable queue.</p>}
      {loadError && <p className="connection-message warning" role="alert">{loadError instanceof Error ? loadError.message : "Could not load experiment resources."} <button className="text-link" onClick={() => { void versions.mutate(); void indexes.mutate(); void runs.mutate(); void experiments.mutate(); }}>Retry loading</button></p>}
      {error && <p className="connection-message warning" role="alert">{error}</p>}
      {available && !versions.isLoading && versions.data?.length === 0 && <p className="connection-message">Publish a reviewed dataset in <Link className="text-link" href="/datasets">Datasets</Link> to enable a run. Candidate questions cannot be run.</p>}
      <form className="experiment-form" onSubmit={event => { event.preventDefault(); setBusy(true); setError(""); void (async () => {
        try {
          const payload = { name, dataset_version_id: selectedDataset?.id, index_id: selectedIndex?.id, split, top_k: topK, context_tokens: budget, max_new_tokens: output, repeats, seed, cache_condition: cacheCondition, measurement_notes: measurementNotes, retrieval_strategy: retrievalStrategy, candidate_k: candidateK, rrf_k: rrfK };
          const fingerprint = JSON.stringify(payload);
          if (submission.current?.fingerprint !== fingerprint) submission.current = { fingerprint, key: crypto.randomUUID() };
          const experiment = experimentSchema.parse(await requestJSON("experiments", { method: "POST", headers: { "Content-Type": "application/json" }, body: fingerprint }));
          const run = runSchema.parse(await requestJSON(`experiments/${experiment.id}/runs`, { method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": submission.current.key }, body: "{}" }));
          await runs.mutate(); await experiments.mutate();
          router.push(`/runs/${run.id}`);
        } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not submit the run. Your inputs are preserved."); }
        finally { setBusy(false); }
      })(); }}>
        <div className="field"><label htmlFor="experiment-name">Experiment name</label><input id="experiment-name" required maxLength={160} value={name} disabled={busy} onChange={event => setName(event.target.value)} placeholder="Section chunks · dense baseline" /></div>
        <div className="field"><label htmlFor="experiment-dataset">Published dataset</label><select id="experiment-dataset" value={selectedDataset?.id ?? ""} disabled={busy || !versions.data?.length} onChange={event => { setDatasetId(event.target.value); setIndexId(""); }}>
          {!versions.data?.length && <option value="">{versions.isLoading ? "Loading datasets…" : "No published dataset"}</option>}
          {versions.data?.map(item => <option key={item.id} value={item.id}>{item.name} · v{item.version}{item.purpose === "development_fixture" ? " · development fixture" : ""}</option>)}
        </select></div>
        <div className="field"><label htmlFor="experiment-strategy">Experiment retrieval strategy</label><select id="experiment-strategy" value={retrievalStrategy} disabled={busy} onChange={event => { setRetrievalStrategy(event.target.value); setCandidateK(Math.max(candidateK, topK)); setIndexId(""); }}><option value="index">Index baseline · lexical or dense</option><option value="hybrid">Hybrid · reciprocal-rank fusion</option><option value="hybrid_rerank">Hybrid · fusion + cross-encoder</option></select></div>
        <div className="field"><label htmlFor="experiment-index">Ready index · matching corpus</label><select id="experiment-index" value={selectedIndex?.id ?? ""} disabled={busy || !readyIndexes.length} onChange={event => setIndexId(event.target.value)}>
          {!readyIndexes.length && <option value="">{retrievalStrategy === "index" ? "Build an index for this corpus first" : "Build a dense index for this corpus first"}</option>}
          {readyIndexes.map(item => <option key={item.id} value={item.id}>{item.config.retrieval === "pgvector-exact-cosine-v1" ? "Dense" : "Lexical"} · {String((item.config.chunking as { strategy?: string })?.strategy ?? "chunks")} · {item.chunk_count} chunks · {item.id.slice(0, 8)}</option>)}
        </select></div>
        <div className="field"><label htmlFor="experiment-split">Dataset split</label><select id="experiment-split" value={split} disabled={busy} onChange={event => setSplit(event.target.value)}><option value="development">Development</option><option value="test">Test</option></select></div>
        <div className="field"><label htmlFor="experiment-top-k">Retrieved passages</label><input id="experiment-top-k" type="number" min={1} max={50} required value={topK} disabled={busy} onChange={event => { setTopK(Number(event.target.value)); if (retrievalStrategy !== "index") setCandidateK(Math.max(candidateK, Number(event.target.value))); }} /></div>
        <div className="field"><label htmlFor="experiment-budget">Evidence token budget</label><input id="experiment-budget" type="number" min={0} max={1536} required value={budget} disabled={busy} onChange={event => setBudget(Number(event.target.value))} /></div>
        {retrievalStrategy !== "index" && <><div className="field"><label htmlFor="experiment-candidates">Candidates per arm / reranker</label><input id="experiment-candidates" type="number" min={topK} max={50} required value={candidateK} disabled={busy} onChange={event => setCandidateK(Number(event.target.value))} /></div><div className="field"><label htmlFor="experiment-rrf">RRF rank constant</label><input id="experiment-rrf" type="number" min={1} max={1000} required value={rrfK} disabled={busy} onChange={event => setRrfK(Number(event.target.value))} /></div><p className="muted-text experiment-advanced">Hybrid uses the same frozen chunks for both search arms. Equal-weight RRF combines their ranks; the cross-encoder reranks the best fused candidates before final top-k selection. Ranking scores are not probabilities or correctness scores. The first reranked run prepares a pinned public CPU model.</p></>}
        <details className="experiment-advanced"><summary>Answer settings and repeat policy</summary><div className="experiment-form">
          <div className="field"><label htmlFor="experiment-output">Maximum answer tokens</label><input id="experiment-output" type="number" min={1} max={256} required value={output} disabled={busy} onChange={event => setOutput(Number(event.target.value))} /></div>
          <div className="field"><label htmlFor="experiment-repeats">Repeats per question</label><input id="experiment-repeats" type="number" min={1} max={3} required value={repeats} disabled={busy} onChange={event => setRepeats(Number(event.target.value))} /></div>
          <div className="field"><label htmlFor="experiment-seed">Base seed</label><input id="experiment-seed" type="number" min={0} max={2147483644} required value={seed} disabled={busy} onChange={event => setSeed(Number(event.target.value))} /></div>
          <div className="field"><label htmlFor="experiment-cache">Cache condition · operator declaration</label><select id="experiment-cache" value={cacheCondition} disabled={busy} onChange={event => setCacheCondition(event.target.value)}><option value="uncontrolled">Uncontrolled</option><option value="operator_cold_cache">Operator prepared cold cache</option><option value="operator_warm_cache">Operator prepared warm cache</option></select></div>
          <div className="field"><label htmlFor="experiment-measurement">Measurement preparation notes</label><textarea id="experiment-measurement" maxLength={1000} required={cacheCondition !== "uncontrolled"} value={measurementNotes} disabled={busy} onChange={event => setMeasurementNotes(event.target.value)} /></div>
        </div><p className="muted-text">Cache preparation is your declaration and is not automatically verified. Answer models load in fresh CPU processes per call. Do not label cache conditions as controlled without preparing and documenting them.</p><p className="muted-text">Greedy CPU generation. Repeats are fresh executions with seed + repeat; they do not create new independent questions. Evidence uses the answer tokenizer; the full prompt is checked against a 2,048-token limit.</p></details>
        <button className="button primary" disabled={busy || !available || !configured || !selectedDataset || !selectedIndex}>{busy ? "Submitting…" : "Start run"}</button>
      </form>
      </div></details>
    </>}
  </section>;
}

function RunDetail({ id, available, initialResultId }: { id: string; available: boolean; initialResultId?: string }) {
  const [selected, setSelected] = useState(initialResultId ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const run = useSWR(available ? `runs/${id}` : null, async path => runSchema.parse(await requestJSON(path)), { refreshInterval: data => data && terminal(data.state) ? 0 : 1500, shouldRetryOnError: false });
  const results = useSWR(run.data ? [`runs/${id}/results`, run.data.state, run.data.completed_count + run.data.failed_count] : null, ([path]) => allPages(path, resultSummarySchema), { refreshInterval: terminal(run.data?.state ?? "") ? 0 : 2000, shouldRetryOnError: false });
  const attempts = useSWR(run.data ? [`runs/${id}/attempts`, run.data.state, run.data.completed_count + run.data.failed_count] : null, ([path]) => allPages(path, attemptSchema), { refreshInterval: terminal(run.data?.state ?? "") ? 0 : 2000, shouldRetryOnError: false });
  const resultId = selected || results.data?.[0]?.id;
  const trace = useSWR(resultId ? `runs/${id}/results/${resultId}` : null, async path => resultSchema.parse(await requestJSON(path)), { shouldRetryOnError: false });
  const row = run.data;
  const loadError = run.error || results.error || trace.error || attempts.error;
  if (!available) return <p className="connection-message warning" role="status">Connect the API and database to open this saved run.</p>;
  return <div className="run-detail">
    {loadError && <p className="connection-message warning" role="alert">{loadError instanceof Error ? loadError.message : "Could not load this run."} <button className="text-link" onClick={() => { void run.mutate(); void results.mutate(); void trace.mutate(); void attempts.mutate(); }}>Retry loading</button></p>}
    {run.isLoading && <p role="status">Loading run…</p>}
    {row && <>
      <div className="section-topline"><h2 id="experiment-title">Run {row.id.slice(0, 8)}</h2><span className="outline-tag">{row.manifest_summary.purpose === "development_fixture" ? "Development fixture · not benchmark evidence" : "Research dataset"}</span></div>
      <div className="run-progress"><div><strong className="run-state">{displayState(row.state)}{row.cancel_requested && !terminal(row.state) ? " · cancellation requested" : ""}</strong><p role="status">{row.completed_count} succeeded · {row.failed_count} failed · {row.cancelled_count} cancelled / {row.total_count} planned observations</p></div>
        {!terminal(row.state) && <button className="button subtle" disabled={busy || row.cancel_requested} onClick={() => { setBusy(true); setError(""); void requestJSON(`runs/${id}/cancel`, { method: "POST" }).then(() => run.mutate()).catch(cause => setError(cause instanceof Error ? cause.message : "Cancellation failed.")).finally(() => setBusy(false)); }}>{row.cancel_requested ? "Stopping…" : "Cancel run"}</button>}
      </div>
      {error && <p className="connection-message warning" role="alert">{error}</p>}
      {row.error_message && <p className="connection-message warning" role="alert">{row.error_code}: {row.error_message} Completed results remain available.</p>}
      <p className="muted-text">{strategyLabel(row.manifest_summary.config.retrieval_strategy)} · Corpus {row.manifest_summary.corpus_version_id.slice(0, 8)} · dataset {row.manifest_summary.dataset_version_id.slice(0, 8)} · {row.attempts} worker claim(s)</p>
      <p><a className="text-link" href={`/api/platform/runs/${id}/manifest`} download={`run-${id}.json`}>Download frozen run manifest</a></p>
      <Link className="text-link" href={`/runs/${id}/failures`}>Open failure explorer</Link><ExportButton kind="run" id={id} enabled={terminal(row.state)} /><Metrics run={row} />
      <section className="question-results" aria-labelledby="questions-title"><div className="section-topline"><h2 id="questions-title">Question results</h2><span className="muted-text">Frozen question revision · repeat</span></div>
        {results.isLoading && <p role="status">Loading question results…</p>}
        {results.data && !results.data.length && <p className="connection-message">No question results have been published yet. Checkpoints appear below while the worker executes.</p>}
        <div className="question-choices">{results.data?.map(item => <button className={`question-choice ${item.id === resultId ? "selected" : ""}`} key={item.id} aria-pressed={item.id === resultId} onClick={() => setSelected(item.id)}><span>{item.question}</span><small>r{item.question_revision} · repeat {item.repeat + 1} · {item.state}{item.error_code ? ` · ${item.error_code}` : ""}</small></button>)}</div>
        {trace.isLoading && <p role="status">Loading question trace…</p>}
        {trace.data && <QuestionTrace key={trace.data.id} result={trace.data} corpusVersion={row.manifest_summary.corpus_version_id} />}
      </section>
      <details className="run-checkpoints"><summary>Worker attempts and checkpoints ({attempts.data?.length ?? 0})</summary><p className="muted-text">Interrupted attempts can contain retrieval checkpoints without a saved answer. They are excluded from final result scores.</p>{attempts.data?.map(item => <details key={item.id}><summary>Question {item.question_id.slice(0, 8)} · repeat {item.repeat + 1} · attempt {item.ordinal} · {item.state}</summary><pre>{JSON.stringify(item.trace, null, 2)}</pre>{item.error_code && <p>{item.error_code}</p>}</details>)}</details>
    </>}
  </div>;
}

function Metrics({ run }: { run: Run }) {
  return <section className="run-metrics" aria-labelledby="metrics-title"><h2 id="metrics-title">Metrics and coverage</h2><p className="muted-text">These metrics were recorded during run execution. Canonical source spans score retrieval before and after context packing. Post-hoc answer scores and scoring coverage are in each question’s Answer evaluation panel below. Energy, hardware cost, and provider cost are unavailable.</p>
    <div className="run-table-scroll" role="region" aria-label="Run metrics table" tabIndex={0}><table><thead><tr><th scope="col">Metric</th><th scope="col">Mean</th><th scope="col">Scored / applicable</th><th scope="col">Errors</th></tr></thead><tbody>{Object.entries(run.metrics).map(([key, metric]) => <tr key={key}><th scope="row">{metricNames[key] ?? key}</th><td>{metric.mean === null ? displayState(metric.state) : `${(metric.mean * 100).toFixed(1)}%`}</td><td>{metric.scored_count} / {metric.applicable_count ?? "unavailable"}</td><td>{metric.error_count}</td></tr>)}</tbody></table></div>
  </section>;
}

function PipelineTrace({ retrieval, published }: { retrieval: Result["trace"]["retrieval"]; published: boolean }) {
  const pipeline = retrieval?.pipeline;
  if (!pipeline) return null;
  const reranker = pipeline.reranker;
  const final = retrieval.strategy === "hybrid-rrf-cross-encoder-v1";
  return <section className="pipeline-trace" aria-labelledby="pipeline-title"><h4 id="pipeline-title">Fusion and reranking</h4>
    <p className="muted-text">{pipeline.lexical.length} lexical + {pipeline.dense.length} dense candidates · {pipeline.fused.length} unique chunks · candidate depth {pipeline.candidate_k} · RRF constant {pipeline.rrf_k} · equal arm weights</p>
    <p className="muted-text">{reranker ? `Reranker: ${reranker.metadata.contract.model_id} @ ${reranker.metadata.contract.revision.slice(0, 8)}. Scores are raw logits, not probabilities or answer correctness.` : "RRF adds reciprocal ranks; a chunk contributes once per arm. No reranker output is available for this trace."}</p>
    <p className="muted-text pipeline-scroll-hint">Scroll horizontally to see every ranking column.</p>
    <div className="run-table-scroll" role="region" aria-label="Fusion and reranking table" tabIndex={0}><table><thead><tr><th scope="col">Chunk</th><th scope="col">Lexical rank</th><th scope="col">Dense rank</th><th scope="col">RRF score</th><th scope="col">Reranker logit</th><th scope="col">Final rank</th></tr></thead><tbody>{pipeline.fused.map(candidate => {
      const position = reranker?.passage_ids.indexOf(candidate.chunk_id) ?? -1;
      const selected = retrieval.hits.find(hit => hit.chunk.id === candidate.chunk_id);
      return <tr key={candidate.chunk_id}><th scope="row"><abbr title={candidate.chunk_id}>{candidate.chunk_id.slice(0, 8)}</abbr></th><td>{pipeline.lexical.find(hit => hit.chunk_id === candidate.chunk_id)?.rank ?? "not returned"}</td><td>{pipeline.dense.find(hit => hit.chunk_id === candidate.chunk_id)?.rank ?? "not returned"}</td><td>{candidate.score.toFixed(6)}</td><td>{position < 0 ? "not scored" : reranker?.scores[position].toFixed(4)}</td><td>{!published ? "unavailable" : selected && (final || !reranker) ? selected.rank : "not selected"}</td></tr>;
    })}</tbody></table></div>
    <details><summary>Fusion/reranker contracts and stage timings</summary><p className="muted-text">Milliseconds include child startup and model loading where applicable.</p><pre>{JSON.stringify(pipeline, null, 2)}</pre></details>
  </section>;
}

export function QuestionTrace({ result, corpusVersion, readOnly = false, demoSources }: { result: Result; corpusVersion: string; readOnly?: boolean; demoSources?: Record<string, { id: string; heading_path: string[]; text: string; document_name?: string; source: { format: string; page?: number } }> }) {
  const [source, setSource] = useState<{ section: string; start: number; end: number } | null>(null);
  const original = useSWR(source && !demoSources ? `corpus-versions/${corpusVersion}/sections/${source.section}` : null, async path => sectionSchema.parse(await requestJSON(path)), { shouldRetryOnError: false });
  const sourceData = source && demoSources ? demoSources[source.section] : original.data;
  const trace = result.trace, question = trace.question.content, answer = trace.generation;
  function spanLink(span: { section_id: string; start_offset: number; end_offset: number }, label: string) {
    return <button className="text-link" onClick={() => setSource({ section: span.section_id, start: span.start_offset, end: span.end_offset })}>{label} · {span.start_offset}–{span.end_offset}</button>;
  }
  return <article className="question-trace" aria-labelledby="trace-title">
    <h3 id="trace-title">Question trace</h3><p className="trace-question">{question.text}</p><p className="muted-text">{question.topic} · {question.difficulty} · {question.split} · {question.answerable ? "Answerable" : "Unanswerable"} · {readOnly ? "synthetic fixture annotations" : `reviewed by ${question.reviewer}`}</p>
    {trace.error && <p className="connection-message warning" role="alert">{trace.error.stage}: {trace.error.code} — {trace.error.message}</p>}
    <h4>{readOnly ? "Illustrative answer" : "Generated answer"}</h4>{answer ? <><pre className="answer-text">{answer.answer || "Empty model output"}</pre><p className="muted-text">{answer.input_tokens ?? "unavailable"} input / {answer.output_tokens ?? "unavailable"} output tokens · finish: {readOnly ? "not executed (fixture)" : answer.finish_reason} · exact abstention marker: {answer.abstained ? "yes" : "no"}</p>{answer.finish_reason === "length" && <p className="connection-message warning">The answer reached its token limit and may be incomplete.</p>}<p className="muted-text">Recognized references: {answer.citations.join(", ") || "none"} · unknown references: {answer.unknown_citations.join(", ") || "none"}. Citation syntax alone does not establish support. {readOnly ? "No answer-quality assessment was performed in this fixture." : "Inspect answer evaluations below."}</p></> : <p className="connection-message">Answer unavailable. Inspect the execution error and retained retrieval evidence.</p>}
    {answer && !readOnly && <AnswerEvaluation result={result} />}
    <PipelineTrace retrieval={trace.retrieval ?? trace.retrieval_candidates} published={!!trace.retrieval} />
    {trace.retrieval_candidates && <details className="retained-candidates"><summary>Retained candidates before reranking ({trace.retrieval_candidates.hits.length})</summary><p className="muted-text">This checkpoint precedes reranking and does not establish a final retrieval score.</p>{trace.retrieval_candidates.hits.map(hit => <div className="trace-passage" key={hit.chunk.id}><strong>Fused candidate {hit.rank} · RRF {hit.score.toFixed(6)}</strong><pre>{hit.chunk.text}</pre>{hit.chunk.spans.map((span, i) => <div key={i}>{spanLink(span, `Candidate source ${span.section_id.slice(0, 8)}`)}</div>)}</div>)}</details>}
    <div className="trace-evidence-grid">
      <section aria-labelledby="retrieved-title"><h4 id="retrieved-title">Retrieved passages</h4><p className="muted-text">Recall: {trace.retrieval_scores?.recall == null ? "unavailable / not applicable" : `${(trace.retrieval_scores.recall * 100).toFixed(1)}%`} · {trace.retrieval?.returned_count ?? 0} passages before packing</p>{trace.retrieval?.hits.map(hit => <div className="trace-passage" key={hit.chunk.id}><strong>Rank {hit.rank} · {rankingLabel(trace.retrieval?.strategy)} {hit.score.toFixed(4)}</strong><pre>{hit.chunk.text}</pre>{hit.chunk.spans.map((span, i) => <div key={i}>{spanLink(span, `Original source ${span.section_id.slice(0, 8)}`)}</div>)}</div>)}{trace.retrieval?.hits.length === 0 && <p>No passages retrieved.</p>}</section>
      <section aria-labelledby="context-title"><h4 id="context-title">Delivered context</h4>{answer ? <><p className="muted-text">{answer.context.token_count}/{answer.context.token_budget} evidence tokens · recall {trace.context_scores?.recall == null ? "unavailable / not applicable" : `${(trace.context_scores.recall * 100).toFixed(1)}%`}</p><p className="muted-text">{answer.context.truncated_chunk_ids.length} truncated · {answer.context.omitted_chunk_ids.length} omitted</p>{answer.context.passages.map((passage, i) => <div className="trace-passage" key={passage.id}><strong>[P{i + 1}] · {passage.token_count} {readOnly ? "illustrative tokens" : "answer-tokenizer tokens"}</strong><pre>{passage.text}</pre>{passage.spans.map((span, j) => <div key={j}>{spanLink(span, `Delivered source ${span.section_id.slice(0, 8)}`)}</div>)}</div>)}{!answer.context.passages.length && <p>No evidence delivered.</p>}</> : <p>Delivered context unavailable.</p>}</section>
    </div>
    <section className="gold-evidence" aria-labelledby="gold-title"><h4 id="gold-title">Gold evidence and reference answer</h4><pre>{question.reference_answer}</pre>{question.required_facts.map((fact, i) => <p key={i}>Required fact {i + 1}: {fact}</p>)}{question.evidence_groups.map((group, i) => <div key={i}><strong>Fact {group.fact_index + 1}</strong>{group.alternatives.map((alternative, j) => <div key={j}><p className="muted-text">Accepted alternative {j + 1} · all spans required</p>{alternative.spans.map((span, k) => <div key={k}>{spanLink(span, `Gold source ${span.section_id.slice(0, 8)}`)}</div>)}</div>)}</div>)}{!question.evidence_groups.length && <p>No positive gold evidence for this question.</p>}</section>
    {source && <section className="source-section" aria-label="Original canonical source"><div className="section-topline"><h4>Original canonical source</h4><button className="button subtle" onClick={() => setSource(null)}>Close source</button></div>{original.isLoading && <p role="status">Loading source…</p>}{original.error && <p role="alert">Could not load the original source. <button className="text-link" onClick={() => { void original.mutate(); }}>Retry source</button></p>}{sourceData && <><p className="muted-text">{sourceData.document_name ?? "Published source"} · {sourceData.heading_path.join(" / ")} · {sourceData.source.format}{sourceData.source.page ? ` page ${sourceData.source.page}` : ""} · section {source.section} · Unicode offsets {source.start}–{source.end}</p><pre className="source-text">{Array.from(sourceData.text).slice(0, source.start).join("")}<mark>{Array.from(sourceData.text).slice(source.start, source.end).join("")}</mark>{Array.from(sourceData.text).slice(source.end).join("")}</pre></>}</section>}
    <details><summary>{readOnly ? "Fixture prompt, metadata, and annotations" : "Executed prompt, runtime, timings, and attempts"}</summary>{answer && <><p className="muted-text">Prompt SHA-256: {answer.prompt_hash}</p><pre>{answer.prompt}</pre><pre>{JSON.stringify(answer.metadata, null, 2)}</pre></>}<p className="muted-text">Query embedding metadata</p><pre>{JSON.stringify(trace.retrieval?.embedding ?? { state: "not_applicable" }, null, 2)}</pre><p className="muted-text">Stage wall times in milliseconds; generation includes model hashing/loading. Shared preparation and queue time are outside these question timings.</p><pre>{JSON.stringify(trace.timings, null, 2)}</pre><ul>{result.attempts.map(attempt => <li key={attempt.id}>Attempt {attempt.ordinal}: {attempt.state}{attempt.error_code ? ` · ${attempt.error_code}` : ""}</li>)}</ul></details>
  </article>;
}
