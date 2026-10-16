"use client";

import Link from "next/link";
import { ComparisonCharts } from "@/components/comparison-charts";
import { ExportButton } from "@/components/export-button";
import { z } from "zod";
import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { comparisonSchema, type Report } from "@/lib/comparisons";
import { pageSchema, requestJSON } from "@/lib/documents";
import { displayState, metricNames, runSchema, strategyLabel } from "@/lib/runs";

const metricOrder = ["answer_correctness", "faithfulness", "citation_support", "abstention_quality", "retrieval_precision", "retrieval_recall", "context_recall"];
const stageNames: Record<string, string> = { question_wall_ms: "Question total", retrieval_wall_ms: "Retrieval total", generation_wall_ms: "Answer generation", pipeline_lexical_wall_ms: "Lexical search", pipeline_query_embedding_wall_ms: "Query embedding", pipeline_dense_search_wall_ms: "Dense search", pipeline_fusion_wall_ms: "Rank fusion", pipeline_reranking_wall_ms: "Reranking" };
const percent = (value: number | null | undefined) => value == null ? "unavailable" : `${(value * 100).toFixed(1)}%`;
const delta = (value: number | null | undefined) => value == null ? "unavailable" : `${value >= 0 ? "+" : ""}${(value * 100).toFixed(1)} pp`;
const ms = (value: number | null | undefined) => value == null ? "unavailable" : `${value.toLocaleString(undefined, { maximumFractionDigits: 1 })} ms`;

export function ComparisonWorkspace({ available, workerReady, initialId }: { available: boolean; workerReady: boolean; initialId?: string }) {
  const router = useRouter();
  const [name, setName] = useState(""), [baseline, setBaseline] = useState(""), [candidate, setCandidate] = useState("");
  const [source, setSource] = useState("human"), [exploratory, setExploratory] = useState(false);
  const [topic, setTopic] = useState(""), [difficulty, setDifficulty] = useState("");
  const [seed, setSeed] = useState(0), [resamples, setResamples] = useState(1000);
  const [offset, setOffset] = useState(0), [busy, setBusy] = useState(false), [error, setError] = useState("");
  const submission = useRef<{ body: string; key: string } | null>(null);
  const runs = useSWR(available && !initialId ? "runs?limit=100" : null, async path => pageSchema(runSchema).parse(await requestJSON(path)), { shouldRetryOnError: false });
  const saved = useSWR(available && !initialId ? `comparisons?limit=20&cursor=${offset}` : null, async path => pageSchema(comparisonSchema).parse(await requestJSON(path)), { refreshInterval: 3000, shouldRetryOnError: false });
  const facets = useSWR(available && baseline && candidate ? `comparisons/facets?baseline_run_id=${baseline}&candidate_run_id=${candidate}` : null, async path => z.object({ topics: z.array(z.string()), difficulties: z.array(z.string()) }).parse(await requestJSON(path)), { shouldRetryOnError: false });
  if (initialId) return <><Link className="text-link" href="/comparisons">← All comparisons</Link><ComparisonDetail id={initialId} available={available} /></>;
  const loadError = runs.error || saved.error || facets.error;
  return <section className="comparison-workspace" aria-labelledby="comparison-title"><h2 id="comparison-title">Create a paired comparison</h2>
    <p>Choose a baseline and candidate. Freeze their current human reviews or model estimates, average repeats per question, and resample whole split groups. New reviews will not change this saved analysis.</p>
    {!available && <p className="connection-message warning" role="status">Comparisons need the current API and PostgreSQL. <Link href="/settings">Check workspace setup.</Link></p>}
    {available && !workerReady && <p className="connection-message warning">The worker is unavailable. Submitted analysis will wait in the durable queue.</p>}
    {loadError && <p role="alert" className="connection-message warning">Could not load comparison resources. <button className="text-link" onClick={() => { void runs.mutate(); void saved.mutate(); void facets.mutate(); }}>Retry loading</button></p>}
    {error && <p role="alert" className="connection-message warning">{error}</p>}
    {runs.isLoading && <p role="status">Loading saved runs…</p>}
    {runs.data && runs.data.items.length < 2 && <p>Save at least two experiment runs to compare them. <Link href="/experiments" className="text-link">Open experiments.</Link></p>}
    <form className="comparison-form" onSubmit={event => { event.preventDefault(); setBusy(true); setError("");
      const body = JSON.stringify({ name, baseline_run_id: baseline, candidate_run_id: candidate, assessment_source: source, exploratory, seed, resamples, topics: topic ? [topic] : [], difficulties: difficulty ? [difficulty] : [] });
      if (submission.current?.body !== body) submission.current = { body, key: crypto.randomUUID() };
      void requestJSON("comparisons", { method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": submission.current.key }, body }).then(value => { const record = comparisonSchema.parse(value); router.push(`/comparisons/${record.id}`); }).catch(cause => setError(cause instanceof Error ? cause.message : "Could not submit; inputs and retry key are preserved.")).finally(() => setBusy(false));
    }}>
      <div className="field"><label htmlFor="comparison-name">Comparison name</label><input id="comparison-name" required maxLength={160} value={name} disabled={busy} onChange={event => setName(event.target.value)} /></div>
      {(["baseline", "candidate"] as const).map(side => <div className="field" key={side}><label htmlFor={`comparison-${side}`}>{side === "baseline" ? "Baseline run" : "Candidate run"}</label><select id={`comparison-${side}`} required value={side === "baseline" ? baseline : candidate} disabled={busy || !available} onChange={event => { (side === "baseline" ? setBaseline : setCandidate)(event.target.value); setTopic(""); setDifficulty(""); }}><option value="">Choose a saved run</option>{runs.data?.items.map(run => <option key={run.id} value={run.id}>{run.id.slice(0, 8)} · {strategyLabel(run.manifest_summary.config.retrieval_strategy)} · {displayState(run.state)}{run.manifest_summary.purpose === "development_fixture" ? " · development fixture" : ""}</option>)}</select></div>)}
      <p className="muted-text">Shows the latest 100 saved runs. The candidate-minus-baseline difference is positive when the candidate score is higher. Retrieval scores do not need an answer judge.</p>
      <div className="field"><label htmlFor="comparison-source">Answer assessment source</label><select id="comparison-source" value={source} disabled={busy} onChange={event => setSource(event.target.value)}><option value="human">Human reviews</option><option value="model">Model estimates · uncalibrated</option></select></div>
      <div className="comparison-controls"><div className="field"><label htmlFor="comparison-topic">Question topic</label><select id="comparison-topic" value={topic} disabled={busy} onChange={event => setTopic(event.target.value)}><option value="">All topics</option>{facets.data?.topics.map(value => <option key={value} value={value}>{value}</option>)}</select></div><div className="field"><label htmlFor="comparison-difficulty">Question difficulty</label><select id="comparison-difficulty" value={difficulty} disabled={busy} onChange={event => setDifficulty(event.target.value)}><option value="">All difficulties</option>{facets.data?.difficulties.map(value => <option key={value} value={value}>{value}</option>)}</select></div></div><p className="muted-text">Filters create a new frozen subgroup analysis. Question timings follow the filters; run windows and usage still describe the full runs.</p>
      <div className="comparison-controls"><div className="field"><label htmlFor="comparison-seed">Bootstrap seed</label><input id="comparison-seed" required type="number" min={0} max={2147483647} value={seed} disabled={busy} onChange={event => setSeed(Number(event.target.value))} /></div><div className="field"><label htmlFor="comparison-resamples">Bootstrap resamples</label><input id="comparison-resamples" required type="number" min={200} max={5000} value={resamples} disabled={busy} onChange={event => setResamples(Number(event.target.value))} /></div></div>
      <label className="review-checkbox"><input type="checkbox" checked={exploratory} disabled={busy} onChange={event => setExploratory(event.target.checked)} />Allow exploratory analysis of partial runs or differing controls. Missing repeats and incompatible scoring policies are still excluded.</label>
      {exploratory && <p className="connection-message warning">Exploratory analysis reports the common available questions with a persistent warning. It cannot establish a controlled research winner.</p>}
      <button className="button primary" disabled={busy || !available || !baseline || !candidate || baseline === candidate}>{busy ? "Submitting analysis…" : "Create comparison"}</button>
    </form>
    <h2>Saved comparisons</h2>{saved.isLoading && <p role="status">Loading comparisons…</p>}{saved.data?.items.length === 0 && <p>No saved comparisons yet.</p>}
    <div className="run-list">{saved.data?.items.map(row => <div className="run-list-row" key={row.id}><Link className="text-link" href={`/comparisons/${row.id}`}>{row.manifest_summary.request.name}</Link><span>{row.state} · {row.manifest_summary.request.assessment_source} · {row.manifest_summary.request.exploratory ? "exploratory" : "strict"}</span></div>)}</div>
    <div className="evaluation-actions"><button className="button subtle" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 20))}>Previous comparisons</button><button className="button subtle" disabled={!saved.data?.next_cursor} onClick={() => setOffset(offset + 20)}>Next comparisons</button></div>
  </section>;
}

function ComparisonDetail({ id, available }: { id: string; available: boolean }) {
  const record = useSWR(available ? `comparisons/${id}` : null, async path => comparisonSchema.parse(await requestJSON(path)), { refreshInterval: data => data && ["completed", "failed"].includes(data.state) ? 0 : 2000, shouldRetryOnError: false });
  const [metric, setMetric] = useState("answer_correctness");
  if (!available) return <p className="connection-message warning">Comparison needs the current API and database.</p>;
  if (record.error) return <p role="alert">Could not load comparison. <button className="text-link" onClick={() => { void record.mutate(); }}>Retry comparison</button></p>;
  if (!record.data) return <p role="status">Loading comparison…</p>;
  const row = record.data, request = row.manifest_summary.request;
  const report = row.output && "metrics" in row.output ? row.output : null;
  const selected = report?.metrics[metric];
  return <section className="comparison-detail" aria-labelledby="comparison-detail-title"><h2 id="comparison-detail-title">{request.name}</h2>
    <p className="muted-text">{row.state} · {request.assessment_source === "model" ? "Uncalibrated model estimates" : "Human review assessments"} · snapshot {new Date(row.manifest_summary.cutoff).toLocaleString()} · attempts {row.attempts}</p>
    <p><Link className="text-link" href={`/runs/${request.baseline_run_id}`}>Baseline run {request.baseline_run_id.slice(0, 8)}</Link> · <Link className="text-link" href={`/runs/${request.candidate_run_id}`}>Candidate run {request.candidate_run_id.slice(0, 8)}</Link></p>
    <a className="text-link" href={`/api/platform/comparisons/${id}/manifest`} download={`comparison-${id}-manifest.json`}>Download frozen comparison inputs</a>
    <p className="muted-text">Manifest SHA-256 {row.manifest_hash}</p><p>Question filters: topics {request.topics?.join(", ") || "all"}; difficulty {request.difficulties?.join(", ") || "all"}. Frozen reports do not change when filters or reviews change.</p><ExportButton kind="comparison" id={id} enabled={["completed", "failed"].includes(row.state)} />
    {request.exploratory && <p className="connection-message warning">Exploratory comparison · controls or coverage may differ. No research winner is inferred.</p>}
    {!row.output && <p role="status">Analysis {row.state}. The durable worker will compute the saved report.</p>}
    {row.output && "error_code" in row.output && <p role="alert" className="connection-message warning">{row.output.error_code}: {row.output.error_message}</p>}
    {report && <>
      {report.development_fixture && <p className="connection-message warning">Development fixture · not benchmark evidence.</p>}
      {report.strict_blocked && <p className="connection-message warning">Controls or run completion differ. Strict inference is blocked; descriptive paired values remain inspectable. An exploratory override is recorded only in a newly submitted comparison.</p>}
      <details><summary>Compatibility differences ({report.differences.length})</summary>{report.differences.length === 0 && <p>Recorded controls match. This does not verify hidden hardware or cache conditions.</p>}{report.differences.map(item => <div key={item.field}><h3>{item.field} · {item.blocks_strict ? "blocks strict analysis" : "recorded difference"}</h3><pre>{JSON.stringify({ baseline: item.baseline, candidate: item.candidate }, null, 2)}</pre></div>)}</details>
      <ComparisonCharts report={report} /><h3>Paired quality scores</h3><p>Question means after averaging repeats. Difference and 95% percentile intervals use candidate minus baseline, in percentage points. Resampling unit: whole split group; seed {request.seed}, {request.resamples} resamples.</p>
      <p className="pipeline-scroll-hint muted-text">Scroll the table horizontally to inspect differences, intervals, and sample counts.</p>
      <div className="run-table-scroll" role="region" aria-label="Paired quality comparison" tabIndex={0}><table><thead><tr><th>Metric</th><th>State</th><th>Baseline</th><th>Candidate</th><th>Difference</th><th>95% interval</th><th>Questions / groups</th><th>Excluded</th></tr></thead><tbody>{Object.entries(report.metrics).sort(([a], [b]) => metricOrder.indexOf(a) - metricOrder.indexOf(b)).map(([key, value]) => <tr key={key}><th scope="row">{metricNames[key] ?? key}</th><td>{value.state}</td><td>{percent(value.baseline_mean)}</td><td>{percent(value.candidate_mean)}</td><td>{delta(value.difference)}</td><td>{value.interval ? `${delta(value.interval.low)} to ${delta(value.interval.high)}` : "unavailable"}</td><td>{value.paired_question_count} / {value.group_count}</td><td>{value.excluded_question_count}</td></tr>)}</tbody></table></div>
      <div className="field"><label htmlFor="comparison-metric">Inspect metric coverage and question pairs</label><select id="comparison-metric" value={metric} onChange={event => setMetric(event.target.value)}>{Object.keys(report.metrics).map(key => <option key={key} value={key}>{metricNames[key] ?? key}</option>)}</select></div>
      {selected && <><p className="muted-text">{selected.interval_reason ?? "Interval computed over the paired split groups."}</p><div className="run-table-scroll" role="region" aria-label="Comparison scoring coverage" tabIndex={0}><table><thead><tr><th>Source</th><th>Planned</th><th>Applicable</th><th>Scored</th><th>Errors</th><th>Unavailable</th><th>Not applicable</th></tr></thead><tbody>{(["baseline", "candidate"] as const).map(side => { const count = selected[`${side}_coverage`]; return <tr key={side}><th scope="row">{side}</th><td>{count.planned_count}</td><td>{count.applicable_count ?? "unknown"}</td><td>{count.scored_count}</td><td>{count.error_count}</td><td>{count.unavailable_count}</td><td>{count.not_applicable_count}</td></tr>; })}</tbody></table></div>
        <details><summary>Paired question means ({selected.pairs.length}) and exclusions ({selected.exclusions.length})</summary>{selected.pairs.map(pair => <div key={pair.question_id} className="trace-passage"><p>{pair.question}</p><p className="muted-text">Group {pair.group} · baseline {percent(pair.baseline)} · candidate {percent(pair.candidate)} · {delta(pair.difference)}</p></div>)}{selected.exclusions.map(item => <p key={item.question_id}>Question {item.question_id}: {item.reason}</p>)}</details></>}
      <Accounting report={report} />
      <details><summary>Analysis limitations</summary><ul>{report.limitations.map(item => <li key={item}>{item}</li>)}</ul></details>
    </>}
  </section>;
}

function Accounting({ report }: { report: Report }) {
  return <section className="comparison-accounting" aria-labelledby="accounting-title"><h3 id="accounting-title">Observed latency, usage, and cost</h3><p>Full run accounting, including questions outside any subgroup filter. These are descriptive measurements. Cache declarations are not automatically verified; generation includes model hashing/loading. Missing timing or usage remains unavailable.</p>{(["baseline", "candidate"] as const).map(side => {
    const value = report.accounting[side];
    return <section key={side} aria-label={`${side} accounting`}><h4>{side === "baseline" ? "Baseline" : "Candidate"}</h4><p>{value.successful_observations}/{value.planned_observations} successful · {value.failed_observations} failed · completion {percent(value.completion_rate)} · {value.attempt_count} question attempts</p><p>Run window: {ms(value.run_elapsed_ms)} · initial queue wait: {ms(value.queue_wait_ms)} · index build: {ms(value.index_build_ms)}</p><p>Cache condition: {displayState(value.measurement.cache_condition)} · operator declaration, not independently verified.</p>
      <p className="muted-text">{value.subgroup_stage_timings ? "Latency table: selected questions, including missing/error measurements." : "Latency table: full run (older report)."}</p><div className="run-table-scroll" role="region" aria-label={`${side} latency table`} tabIndex={0}><table><thead><tr><th>Stage</th><th>p50</th><th>p95</th><th>Measured</th><th>Unavailable</th></tr></thead><tbody>{Object.entries(value.subgroup_stage_timings ?? value.stage_timings).map(([stage, timing]) => <tr key={stage}><th scope="row">{stageNames[stage] ?? displayState(stage)}</th><td>{ms(timing.p50)}</td><td>{ms(timing.p95)}</td><td>{timing.scored_count}</td><td>{timing.unavailable_count}</td></tr>)}</tbody></table></div>
      {(["generation_usage", "judge_usage"] as const).map(key => <p key={key}>{key === "generation_usage" ? "Generation" : "All model-judge attempts"}: {value[key].recorded_call_count} recorded calls · {value[key].input_tokens ?? "unavailable"} input / {value[key].output_tokens ?? "unavailable"} output tokens · {value[key].potential_unobserved_call_count} potentially unobserved calls</p>)}
      <p>Cost: unavailable. {value.cost.reason}</p><details><summary>Measurement limitations and provenance</summary><ul>{value.limitations.map(item => <li key={item}>{item}</li>)}</ul><pre>{JSON.stringify(value, null, 2)}</pre></details>
    </section>;
  })}</section>;
}
