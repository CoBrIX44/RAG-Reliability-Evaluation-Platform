"use client";

import { useRef, useState } from "react";
import useSWR from "swr";
import { allPages, requestJSON } from "@/lib/documents";
import { evaluationCoverageSchema, evaluationSchema, rubricSchema, type Claim, type Evaluation } from "@/lib/evaluations";
import { metricNames, type Result } from "@/lib/runs";

const names = ["answer_correctness", "faithfulness", "citation_support", "abstention_quality"];
const percent = (value: number | null | undefined) => value == null ? "unavailable" : `${(value * 100).toFixed(1)}%`;

export function AnswerEvaluation({ result }: { result: Result }) {
  const [open, setOpen] = useState(false);
  return <section className="answer-evaluation" aria-labelledby="answer-evaluation-title">
    <div className="section-topline"><h4 id="answer-evaluation-title">Answer evaluation</h4><button className="button subtle" aria-expanded={open} onClick={() => setOpen(!open)}>{open ? "Hide evaluations" : "Evaluate this answer"}</button></div>
    <p className="muted-text">Versioned model estimates and named human reviews are stored separately from the original run. Gold-label review does not review the generated answer.</p>
    {open && <EvaluationPanel result={result} />}
  </section>;
}

function EvaluationPanel({ result }: { result: Result }) {
  const path = `runs/${result.run_id}/results/${result.id}`;
  const records = useSWR(`${path}/evaluations`, () => allPages(`${path}/evaluations`, evaluationSchema), { refreshInterval: 3000, shouldRetryOnError: false });
  const rubric = useSWR("evaluation-rubric", async key => rubricSchema.parse(await requestJSON(key)), { shouldRetryOnError: false });
  const coverage = useSWR(`runs/${result.run_id}/evaluations`, async key => evaluationCoverageSchema.parse(await requestJSON(key)), { refreshInterval: 3000, shouldRetryOnError: false });
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  const [reviewOpen, setReviewOpen] = useState(false);
  const judgeKey = useRef<string | null>(null);
  const pending = records.data?.some(item => item.kind === "model" && ["pending", "running"].includes(item.state));
  const model = records.data?.find(item => item.kind === "model");
  const human = records.data?.find(item => item.kind === "human");
  const loadError = records.error || rubric.error || coverage.error;
  return <>
    {(records.isLoading || rubric.isLoading) && <p role="status">Loading evaluations…</p>}
    {loadError && <p role="alert" className="connection-message warning">Could not load evaluations. <button className="text-link" onClick={() => { void records.mutate(); void rubric.mutate(); void coverage.mutate(); }}>Retry evaluations</button></p>}
    {error && <p role="alert" className="connection-message warning">{error}</p>}
    {rubric.data && <details><summary>Rubric · {rubric.data.rubric.version}</summary><dl className="evaluation-rubric">{Object.entries(rubric.data.rubric).filter(([key]) => key !== "version").map(([key, value]) => <div key={key}><dt>{metricNames[key === "correctness" ? "answer_correctness" : key] ?? key}</dt><dd>{value}</dd></div>)}</dl></details>}
    <p className="muted-text">The local 0.5B self-judge is an uncalibrated estimate and can disagree with you. Check its rationale and evidence before drawing conclusions.</p>
    <div className="evaluation-actions">
      <button className="button subtle" disabled={busy || pending || records.isLoading || !rubric.data?.local_judge_enabled || !!loadError} onClick={() => {
        judgeKey.current ??= crypto.randomUUID(); setBusy(true); setError("");
        void requestJSON(`${path}/evaluations`, { method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": judgeKey.current }, body: "{}" }).then(value => { evaluationSchema.parse(value); judgeKey.current = null; return records.mutate(); }).catch(cause => setError(cause instanceof Error ? cause.message : "Judge submission failed; retry uses the same key.")).finally(() => setBusy(false));
      }}>{busy ? "Submitting judge…" : pending ? "Local judge queued / running…" : "Run local judge"}</button>
      <button className="button subtle" aria-expanded={reviewOpen} onClick={() => setReviewOpen(!reviewOpen)}>{reviewOpen ? "Close review form" : "Add human review"}</button>
    </div>
    {rubric.data && !rubric.data.local_judge_enabled && <p className="muted-text">Local judge is disabled in workspace settings. Human review is available.</p>}
    {records.data?.length === 0 && <p>No evaluations yet. Scores remain unavailable until a review or judge completes.</p>}
    {coverage.data && <details className="evaluation-summary"><summary>Scoring coverage for this run</summary><p>{coverage.data.eligible_answers}/{coverage.data.total_observations} observations have saved answers; {coverage.data.without_saved_answer} have no saved answer. Latest record per answer and source; a later failed job is unavailable rather than falling back to an older score.</p><div className="run-table-scroll" role="region" aria-label="Run answer scoring coverage" tabIndex={0}><table><thead><tr><th>Source / metric</th><th>Mean</th><th>Applicable</th><th>Scored</th><th>Errors</th><th>Unavailable</th></tr></thead><tbody>{(["model", "human"] as const).flatMap(source => names.map(name => { const metric = coverage.data!.sources[source][name]; return metric ? <tr key={`${source}-${name}`}><th scope="row">{source === "model" ? "Model" : "Human"} · {metricNames[name]}</th><td>{percent(metric.mean)}</td><td>{metric.applicable_count ?? `unknown (${metric.known_applicable_count} known)`}</td><td>{metric.scored_count}</td><td>{metric.error_count}</td><td>{metric.unavailable_count}</td></tr> : null; }))}</tbody></table></div><p className="muted-text">Claim applicability remains unknown until every eligible answer is assessed. These descriptive means count answer observations; paired research statistics aggregate repeats by question in the next comparison milestone.</p></details>}
    {(model || human) && <div className="evaluation-summary"><h5>Latest assessment from each source</h5><p className="pipeline-scroll-hint muted-text">Scroll the table horizontally to compare both sources and their difference.</p><div className="run-table-scroll" role="region" aria-label="Answer assessment comparison" tabIndex={0}><table><thead><tr><th>Metric</th><th>Model estimate</th><th>Human review</th><th>Difference</th></tr></thead><tbody>{names.map(name => {
      const a = model?.output?.metrics?.[name], b = human?.output?.metrics?.[name];
      const difference = a?.value != null && b?.value != null ? Math.abs(a.value - b.value) : null;
      return <tr key={name}><th scope="row">{metricNames[name]}</th><td>{percent(a?.value)}{a?.value != null && ` · ${a.numerator}/${a.denominator}`}</td><td>{percent(b?.value)}{b?.value != null && ` · ${b.numerator}/${b.denominator}`}</td><td>{difference == null ? "unavailable" : difference === 0 ? "Agreement" : `${(difference * 100).toFixed(1)} pp disagreement`}</td></tr>;
    })}</tbody></table></div><p className="muted-text">One saved answer observation; repeated generations are not independent questions. Each cell is scored or unavailable; failed jobs have no substitute score. Latest source records may be pending or failed.</p></div>}
    {reviewOpen && <HumanReviewForm result={result} path={path} onSaved={() => records.mutate()} />}
    {records.data?.map(item => <EvaluationRecord key={item.id} item={item} />)}
  </>;
}

function HumanReviewForm({ result, path, onSaved }: { result: Result; path: string; onSaved: () => Promise<unknown> }) {
  const question = result.trace.question.content, answer = result.trace.generation!;
  const [reviewer, setReviewer] = useState("");
  const [facts, setFacts] = useState<string[]>(question.required_facts.map(() => ""));
  const [claims, setClaims] = useState<Claim[]>([]), [noClaims, setNoClaims] = useState(false);
  const [rationale, setRationale] = useState(""), [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false), [error, setError] = useState(""), [saved, setSaved] = useState(false);
  const submission = useRef<{ body: string; key: string } | null>(null);
  const citationIds = [...answer.citations, ...answer.unknown_citations];
  function changeClaim(index: number, change: Partial<Claim>) { setClaims(previous => previous.map((claim, i) => i === index ? { ...claim, ...change } : claim)); }
  return <form className="human-review-form" onSubmit={event => { event.preventDefault(); setError(""); setSaved(false);
    if (!confirmed || (!noClaims && claims.length === 0) || facts.some(fact => !fact)) { setError("Assess every fact and all factual claims, or confirm there are no factual claims. Confirm your review before saving."); return; }
    const body = JSON.stringify({ reviewer, judgment: { facts, claims: noClaims ? [] : claims, no_factual_claims: noClaims, rationale } });
    if (submission.current?.body !== body) submission.current = { body, key: crypto.randomUUID() };
    setBusy(true);
    void requestJSON(`${path}/reviews`, { method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": submission.current.key }, body }).then(value => { evaluationSchema.parse(value); setSaved(true); void onSaved().catch(() => undefined); }).catch(cause => setError(cause instanceof Error ? cause.message : "Review could not be saved; your inputs are preserved.")).finally(() => setBusy(false));
  }}>
    <h5>Review the saved answer</h5><p>Read the generated answer, reference facts, and delivered context below. Assess every factual claim, including claims absent from the reference. Corrections are new reviews; earlier reviews stay visible.</p>
    {error && <p role="alert" className="connection-message warning">{error}</p>}{saved && <p role="status">Review saved. The original answer is unchanged.</p>}
    <fieldset disabled={busy || saved}><legend>Reviewer and fact coverage</legend>
      <label htmlFor="answer-reviewer">Reviewer name or label</label><input id="answer-reviewer" required maxLength={160} value={reviewer} onChange={event => setReviewer(event.target.value)} />
      {question.required_facts.map((fact, i) => <div className="field" key={i}><label htmlFor={`review-fact-${i}`}>Required fact {i + 1}: {fact}</label><select id={`review-fact-${i}`} required value={facts[i]} onChange={event => setFacts(previous => previous.map((value, j) => i === j ? event.target.value : value))}><option value="">Choose assessment</option><option value="covered">Covered by the answer</option><option value="missing">Missing from the answer</option><option value="contradicted">Contradicted by the answer</option></select></div>)}
      <label className="review-checkbox"><input type="checkbox" checked={noClaims} onChange={event => setNoClaims(event.target.checked)} />I assessed the entire answer and it has no factual claims (including an exact abstention).</label>
      {!noClaims && <><p className="muted-text">Quote each atomic factual claim exactly from the saved answer. Support is assessed against delivered context, independently of the reference answer.</p>{claims.map((claim, i) => <fieldset key={i} className="claim-review"><legend>Claim {i + 1}</legend><label htmlFor={`claim-text-${i}`}>Exact answer excerpt</label><textarea id={`claim-text-${i}`} required maxLength={2000} value={claim.text} onChange={event => changeClaim(i, { text: event.target.value })} /><label htmlFor={`claim-support-${i}`}>Support in delivered evidence</label><select id={`claim-support-${i}`} value={claim.support} onChange={event => changeClaim(i, { support: event.target.value as Claim["support"] })}><option value="uncertain">Uncertain</option><option value="supported">Supported</option><option value="unsupported">Unsupported</option></select>
        {!!citationIds.length && <div><p>Inline citations for this claim</p>{citationIds.map(id => <label className="review-checkbox" key={id}><input type="checkbox" checked={claim.citations.includes(id)} onChange={event => changeClaim(i, { citations: event.target.checked ? [...claim.citations, id] : claim.citations.filter(value => value !== id) })} />[{id}]</label>)}<label className="review-checkbox"><input type="checkbox" checked={claim.citations_supported} onChange={event => changeClaim(i, { citations_supported: event.target.checked })} />The selected citations support this claim.</label></div>}
        <button type="button" className="text-link" onClick={() => setClaims(previous => previous.filter((_, j) => i !== j))}>Remove claim {i + 1}</button></fieldset>)}<button type="button" className="button subtle" disabled={claims.length >= 50} onClick={() => setClaims(previous => [...previous, { text: "", support: "uncertain", citations: [], citations_supported: false }])}>Add factual claim</button></>}
      <label htmlFor="review-rationale">Review rationale</label><textarea id="review-rationale" required maxLength={4000} value={rationale} onChange={event => setRationale(event.target.value)} />
      <label className="review-checkbox"><input type="checkbox" required checked={confirmed} onChange={event => setConfirmed(event.target.checked)} />I reviewed all facts, all answer claims, and the delivered evidence under this rubric.</label>
      <button className="button primary" type="submit">{busy ? "Saving review…" : saved ? "Review saved" : "Save human review"}</button>
    </fieldset>
  </form>;
}

function EvaluationRecord({ item }: { item: Evaluation }) {
  return <details className="evaluation-record"><summary>{item.kind === "human" ? `Human review · ${item.reviewer}` : "Local model estimate"} · {item.state} · {new Date(item.created_at).toLocaleString()}</summary>
    <p className="muted-text">Rubric {item.manifest.rubric.version} · attempts {item.attempts} · manifest SHA-256 {item.manifest_hash}</p>
    {item.output?.error_code && <p className="connection-message warning">{item.output.error_code}: {item.output.error_message}</p>}
    {item.output?.judgment && <><p>{item.output.judgment.rationale}</p><p>Required facts: {item.output.judgment.facts.join(", ") || "none"}</p>{item.output.judgment.claims.map((claim, i) => <div key={i}><pre>{claim.text}</pre><p>{claim.support} · citations {claim.citations.join(", ") || "none"} · citation support {claim.citations_supported ? "yes" : "no"}</p></div>)}{item.output.judgment.no_factual_claims && <p>No factual claims assessed.</p>}</>}
    <details><summary>Evaluation manifest, raw response, and usage</summary><pre>{JSON.stringify({ manifest: item.manifest, output: item.output }, null, 2)}</pre></details>
  </details>;
}
