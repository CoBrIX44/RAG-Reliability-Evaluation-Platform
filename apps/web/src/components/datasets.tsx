"use client";

import { useRef, useState } from "react";

import useSWR from "swr";

import { allPages, corpusSchema, pageSchema, requestJSON, sectionSchema, versionSchema } from "@/lib/documents";

import { datasetSchema, datasetVersionSchema, emptyQuestion, questionSchema, type Question, type QuestionContent } from "@/lib/datasets";

export function DatasetWorkspace({ available }: { available: boolean }) {

  const [selected, setSelected] = useState("");

  const [name, setName] = useState("");

  const [corpusChoice, setCorpusChoice] = useState("");

  const [purpose, setPurpose] = useState<"research" | "development_fixture">("development_fixture");

  const [form, setForm] = useState<QuestionContent>({ ...emptyQuestion });

  const [editing, setEditing] = useState<Question | null>(null);

  const [busy, setBusy] = useState(false);

  const [error, setError] = useState("");

  const [message, setMessage] = useState("");

  const [sourceCursor, setSourceCursor] = useState(0);

  const [sourceId, setSourceId] = useState("");

  const [factIndex, setFactIndex] = useState(0);

  const [start, setStart] = useState(0);

  const [end, setEnd] = useState(0);

  const [alternative, setAlternative] = useState(false);

  const sourceText = useRef<HTMLPreElement>(null);

  const importPicker = useRef<HTMLInputElement>(null);

  const datasets = useSWR(available ? "datasets" : null, () => allPages("datasets", datasetSchema), { shouldRetryOnError: false });

  const corpusVersions = useSWR(available ? "dataset-corpus-choices" : null, async () => {

    const corpora = await allPages("corpora", corpusSchema);

    return (await Promise.all(corpora.map(async corpus => (await allPages(`corpora/${corpus.id}/versions`, versionSchema)).map(version => ({ ...version, label: `${corpus.name} · Version ${version.version}` }))))).flat();

  }, { shouldRetryOnError: false });

  const datasetId = selected || datasets.data?.[0]?.id || "";

  const dataset = datasets.data?.find(item => item.id === datasetId);

  const versionChoice = corpusChoice || corpusVersions.data?.[0]?.id || "";

  const questions = useSWR(available && datasetId ? `questions/${datasetId}` : null, () => allPages(`datasets/${datasetId}/questions`, questionSchema), { shouldRetryOnError: false });

  const versions = useSWR(available && datasetId ? `dataset-versions/${datasetId}` : null, () => allPages(`datasets/${datasetId}/versions`, datasetVersionSchema), { shouldRetryOnError: false });

  const sources = useSWR(available && dataset ? `dataset-sources/${dataset.corpus_version_id}/${sourceCursor}` : null,

    async () => pageSchema(sectionSchema).parse(await requestJSON(`corpus-versions/${dataset?.corpus_version_id}/sections?limit=20&cursor=${sourceCursor}`)), { shouldRetryOnError: false });

  const source = sources.data?.items.find(item => item.id === sourceId) || sources.data?.items[0];

  const sourceLength = source ? Array.from(source.text).length : 0;

  const loadError = datasets.error || corpusVersions.error || questions.error || versions.error || sources.error;

  const readyToPublish = available && !questions.error && !!questions.data?.length && questions.data.every(q => q.content.review_status === "reviewed" && q.content.split !== "unassigned");

  async function act(operation: () => Promise<void>) {

    setBusy(true); setError(""); setMessage("");

    try { await operation(); } catch (issue) { setError(issue instanceof Error ? issue.message : "The request failed."); }

    finally { setBusy(false); }

  }

  function setDraft(value: QuestionContent) { setForm({ ...value, review_status: "candidate", reviewer: "" }); }
  function edit(question: Question | null) {

    setEditing(question); setForm(question ? { ...question.content, review_status: "candidate", reviewer: "" } : { ...emptyQuestion }); setFactIndex(0);

    setMessage(question ? "Editing a draft. Review changes before marking it reviewed again." : ""); setError("");

  }

  function useSelection() {

    const selection = window.getSelection(), pre = sourceText.current;

    if (!pre || !selection?.rangeCount) return;

    const range = selection.getRangeAt(0);

    if (!pre.contains(range.startContainer) || !pre.contains(range.endContainer)) { setError("Select a passage inside the source text."); return; }

    const prefix = range.cloneRange(); prefix.selectNodeContents(pre); prefix.setEnd(range.startContainer, range.startOffset);

    const offset = Array.from(prefix.toString()).length; setStart(offset); setEnd(offset + Array.from(range.toString()).length);

  }

  function addEvidence() {

    if (!source || end <= start || end > sourceLength || !Array.from(source.text).slice(start, end).join("").trim()) { setError("Choose a nonempty passage within the source text."); return; }

    const span = { section_id: source.id, start_offset: start, end_offset: end };

    const groups = structuredClone(form.evidence_groups);

    let group = groups.find(item => item.fact_index === factIndex);

    if (!group) { group = { fact_index: factIndex, alternatives: [{ spans: [] }] }; groups.push(group); }

    if (alternative && group.alternatives[0].spans.length) group.alternatives.push({ spans: [span] });

    else group.alternatives[group.alternatives.length - 1].spans.push(span);

    setDraft({ ...form, evidence_groups: groups }); setError("");

  }

  return <section className="dataset-workspace" aria-label="Dataset curation workspace">

    {!available && <div className="connection-message warning" role="status">Dataset curation needs PostgreSQL and current migrations. Check workspace setup.</div>}

    <div className="corpus-toolbar"><div className="field"><label htmlFor="dataset">Active dataset</label><select id="dataset" value={datasetId} disabled={!available || busy || !datasets.data?.length} onChange={event => { setSelected(event.target.value); setSourceCursor(0); setSourceId(""); edit(null); }}>

      {!datasets.data?.length && <option value="">{datasets.isLoading ? "Loading datasets…" : "Create your first dataset"}</option>}{datasets.data?.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select>

      {dataset && <span className="muted-text">{dataset.purpose === "development_fixture" ? "Development fixture · not a research benchmark" : "Research dataset · owner-reviewed labels"}</span>}</div>

      <form className="dataset-create-form" onSubmit={event => { event.preventDefault(); void act(async () => {

        const value = datasetSchema.parse(await requestJSON("datasets", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, purpose, corpus_version_id: versionChoice }) }));

        await datasets.mutate(); setSelected(value.id); setName(""); setSourceCursor(0); setSourceId(""); edit(null); setMessage(`Created ${value.name}.`);

      }); }}><div className="field"><label htmlFor="dataset-name">New dataset name</label><input id="dataset-name" value={name} maxLength={160} disabled={!available || busy} onChange={event => setName(event.target.value)} required /></div>

        <div className="field"><label htmlFor="dataset-corpus">Published corpus</label><select id="dataset-corpus" value={versionChoice} disabled={!available || busy || !corpusVersions.data?.length} onChange={event => setCorpusChoice(event.target.value)}>

          {!corpusVersions.data?.length && <option value="">Publish a corpus in Documents first</option>}{corpusVersions.data?.map(version => <option key={version.id} value={version.id}>{version.label}</option>)}</select></div>

        <div className="field"><label htmlFor="dataset-purpose">Dataset purpose</label><select id="dataset-purpose" value={purpose} disabled={!available || busy} onChange={event => setPurpose(event.target.value as typeof purpose)}><option value="development_fixture">Development fixture</option><option value="research">Research dataset</option></select></div>

        <button className="button subtle" type="submit" disabled={!available || busy || !versionChoice || !name.trim()}>Create dataset</button></form></div>

    <div role="status" aria-live="polite">{busy ? <p>Working…</p> : message && <p className="action-message">{message}</p>}</div>

    {(error || loadError) && <div className="connection-message warning dataset-error" role="alert">{error || (loadError instanceof Error ? loadError.message : "Could not load dataset data.")}{loadError && <button className="button subtle" onClick={() => { void datasets.mutate(); void questions.mutate(); void versions.mutate(); void corpusVersions.mutate(); void sources.mutate(); }}>Try again</button>}</div>}

    <div className="section-topline"><div><h2>Question drafts</h2><p className="muted-text">Labels stay candidates until you explicitly record a human review.</p></div><div className="inline-actions">

      <input className="file-picker" type="file" accept=".jsonl,.ndjson" ref={importPicker} aria-label="Choose a JSONL dataset" disabled={!available || !datasetId || busy} onChange={event => { const file = event.target.files?.[0]; if (!file) return; void act(async () => {

        if (file.size > 10_485_760) throw new Error("Choose a JSONL file smaller than 10 MB.");

        const body = new FormData(); body.append("file", file); await requestJSON(`datasets/${datasetId}/import`, { method: "POST", body }); await questions.mutate(); setMessage("Import complete. Check imported labels before publication."); if (importPicker.current) importPicker.current.value = "";

      }); }} />

      <button className="button subtle" disabled={!available || !datasetId || busy} onClick={() => importPicker.current?.click()}>Import JSONL</button><button className="button subtle" disabled={!datasetId || busy} onClick={() => edit(null)}>New question</button></div></div>

    {!questions.data?.length ? <p className="version-empty">No questions yet. Add a question and annotate its source evidence below.</p> : <ul className="question-list">{questions.data.map(question => <li key={question.id}><button onClick={() => edit(question)} disabled={busy}>{question.content.text}</button><span>{question.content.answerable ? "Answerable" : "Unanswerable"} · {question.content.review_status === "reviewed" ? `Reviewed by ${question.content.reviewer}` : "Candidate"} · {question.content.split}</span></li>)}</ul>}

    <div className="dataset-editor-grid"><form className="question-editor" onSubmit={event => { event.preventDefault(); void act(async () => {

      const value = questionSchema.parse(await requestJSON(`datasets/${datasetId}/questions${editing ? `/${editing.id}` : ""}`, { method: editing ? "PATCH" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(editing ? { expected_revision: editing.revision, content: form } : form) }));

      await questions.mutate(); setEditing(value); setForm(value.content); setMessage("Question saved. Published versions keep their original labels.");

    }); }}><h2>{editing ? "Edit question" : "Add question"}</h2><fieldset disabled={!available || !datasetId || busy} className="editor-fields">

      <div className="field"><label htmlFor="question-text">Question</label><textarea id="question-text" rows={3} maxLength={4000} required value={form.text} onChange={event => setDraft({ ...form, text: event.target.value })} /></div>

      <label className="checkbox-label"><input type="checkbox" checked={form.answerable} onChange={event => setDraft({ ...form, answerable: event.target.checked, required_facts: [], evidence_groups: [] })} />Answerable from this corpus</label>

      <div className="field"><label htmlFor="reference-answer">{form.answerable ? "Reference answer" : "Expected abstention"}</label><textarea id="reference-answer" rows={3} maxLength={16000} value={form.reference_answer} onChange={event => setDraft({ ...form, reference_answer: event.target.value })} /></div>

      {form.answerable && <div className="field"><label htmlFor="required-facts">Required facts · one per line</label><textarea id="required-facts" rows={3} value={form.required_facts.join("\n")} onChange={event => { setDraft({ ...form, required_facts: event.target.value ? event.target.value.split("\n") : [], evidence_groups: [] }); setFactIndex(0); }} /><small>Set facts before annotating. Changing this list clears its evidence annotations.</small></div>}

      <div className="two-fields"><div className="field"><label htmlFor="question-topic">Topic</label><input id="question-topic" maxLength={160} value={form.topic} onChange={event => setDraft({ ...form, topic: event.target.value })} /></div><div className="field"><label htmlFor="difficulty">Difficulty</label><select id="difficulty" value={form.difficulty} onChange={event => setDraft({ ...form, difficulty: event.target.value as QuestionContent["difficulty"] })}><option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option></select></div></div>

      <div className="two-fields"><div className="field"><label htmlFor="question-split">Split</label><select id="question-split" value={form.split} onChange={event => setDraft({ ...form, split: event.target.value as QuestionContent["split"] })}><option value="unassigned">Unassigned</option><option value="development">Development</option><option value="test">Held-out test</option></select></div><div className="field"><label htmlFor="split-group">Split group</label><input id="split-group" maxLength={160} value={form.split_group} onChange={event => setDraft({ ...form, split_group: event.target.value })} /></div></div>

      <p className="muted-text">Keep related questions in one split group. Development and test cannot share gold source sections.</p>

      <label className="checkbox-label"><input type="checkbox" checked={form.review_status === "reviewed"} onChange={event => setForm({ ...form, review_status: event.target.checked ? "reviewed" : "candidate" })} />I have reviewed this question, answer, and evidence</label>

      {form.review_status === "reviewed" && <div className="field"><label htmlFor="reviewer">Reviewer name</label><input id="reviewer" value={form.reviewer} maxLength={160} required onChange={event => setForm({ ...form, reviewer: event.target.value })} /></div>}

      <button className="button primary" type="submit" disabled={!form.text.trim() || (form.review_status === "reviewed" && !form.reviewer.trim())}>Save question</button>

    </fieldset></form><aside className="evidence-panel" aria-label="Gold evidence annotation"><h2>Supporting evidence</h2><p className="muted-text">Annotate each required fact against published source text.</p>

      <div className="field"><label htmlFor="evidence-source">Source section</label><select id="evidence-source" value={source?.id || ""} disabled={!available || !sources.data?.items.length || busy} onChange={event => { setSourceId(event.target.value); setStart(0); setEnd(0); }}>

        {!sources.data?.items.length && <option value="">No published source sections</option>}{sources.data?.items.map((section, index) => <option key={section.id} value={section.id}>{section.document_name || "Source"} · {section.heading_path.join(" / ") || `Section ${sourceCursor + index + 1}`}</option>)}</select></div>

      <div className="inline-actions source-pagination"><button className="button subtle" disabled={sourceCursor === 0 || busy} onClick={() => { setSourceCursor(Math.max(0, sourceCursor - 20)); setSourceId(""); setStart(0); setEnd(0); }}>Previous sources</button><button className="button subtle" disabled={!sources.data?.next_cursor || busy} onClick={() => { setSourceCursor(Number(sources.data?.next_cursor)); setSourceId(""); setStart(0); setEnd(0); }}>Next sources</button></div>

      {source && <><p className="eyebrow">{source.source.format}{source.source.page ? ` · Page ${source.source.page}` : source.source.start_line ? ` · Lines ${source.source.start_line}–${source.source.end_line}` : ""}</p><pre className="annotation-source" ref={sourceText} tabIndex={0} aria-label="Selectable source text">{source.text}</pre></>}

      {form.answerable && <fieldset disabled={!available || busy || !source || !form.required_facts.some(fact => fact.trim())} className="editor-fields">

        <div className="field"><label htmlFor="evidence-fact">Required fact</label><select id="evidence-fact" value={factIndex} onChange={event => setFactIndex(Number(event.target.value))}>{form.required_facts.map((fact, index) => <option key={index} value={index}>{index + 1}. {fact || "Unnamed fact"}</option>)}</select></div>

        <button className="button subtle" type="button" onClick={useSelection}>Use selected text</button><div className="two-fields"><div className="field"><label htmlFor="evidence-start">Start character</label><input id="evidence-start" type="number" min={0} max={sourceLength} value={start} onChange={event => setStart(Number(event.target.value))} /></div><div className="field"><label htmlFor="evidence-end">End character · exclusive</label><input id="evidence-end" type="number" min={1} max={sourceLength} value={end} onChange={event => setEnd(Number(event.target.value))} /></div></div>

        <button className="button subtle" type="button" onClick={() => { setStart(0); setEnd(sourceLength); }}>Use whole section</button><label className="checkbox-label"><input type="checkbox" checked={alternative} onChange={event => setAlternative(event.target.checked)} />Add as another acceptable alternative</label><button className="button subtle" type="button" disabled={end <= start} onClick={addEvidence}>Add evidence passage</button>

      </fieldset>}{form.evidence_groups.map(group => <article className="evidence-group" key={group.fact_index}><strong>Fact {group.fact_index + 1}: {form.required_facts[group.fact_index]}</strong>{group.alternatives.map((item, index) => <div key={index}><p>Alternative {index + 1} · {item.spans.length} required {item.spans.length === 1 ? "passage" : "passages"}</p>{item.spans.map((span, spanIndex) => <EvidenceQuote key={spanIndex} corpusId={dataset?.corpus_version_id || ""} span={span} />)}</div>)}<button className="button subtle" disabled={busy} onClick={() => setDraft({ ...form, evidence_groups: form.evidence_groups.filter(item => item.fact_index !== group.fact_index) })}>Remove fact evidence</button></article>)}

    </aside></div><section className="publication-section" aria-labelledby="dataset-versions-title"><div className="section-topline"><div><h2 id="dataset-versions-title">Published dataset versions</h2><p className="muted-text">Freeze questions, reviews, splits, and source annotations.</p></div><button className="button subtle" disabled={!readyToPublish || busy} onClick={() => { void act(async () => { const value = datasetVersionSchema.parse(await requestJSON(`datasets/${datasetId}/versions`, { method: "POST" })); await versions.mutate(); setMessage(`Dataset version ${value.version} is published.`); }); }}>Publish dataset</button></div>

      {!versions.data?.length ? <p className="version-empty">No published dataset yet. Review all questions, assign splits, and annotate required facts.</p> : <ul className="version-list">{versions.data.map(version => <li key={version.id}><strong>Version {version.version}</strong><span>{version.question_count} {version.question_count === 1 ? "question" : "questions"}</span><code title={version.manifest_hash}>{version.manifest_hash.slice(0, 12)}</code><a className="text-link" href={`/api/platform/dataset-versions/${version.id}/export`}>Export JSONL</a></li>)}</ul>}

    </section>

  </section>;

}

function EvidenceQuote({ corpusId, span }: { corpusId: string; span: { section_id: string; start_offset: number; end_offset: number } }) {

  const { data, error } = useSWR(`gold-source/${corpusId}/${span.section_id}`, async () => sectionSchema.parse(await requestJSON(`corpus-versions/${corpusId}/sections/${span.section_id}`)), { shouldRetryOnError: false });

  return <div>{error ? <p role="alert">Could not load this evidence passage.</p> : !data ? <p>Loading evidence…</p> : <><p className="muted-text">{data.document_name || "Source passage"} · Characters {span.start_offset}–{span.end_offset}</p><pre>{Array.from(data.text).slice(span.start_offset, span.end_offset).join("")}</pre></>}</div>;

}

