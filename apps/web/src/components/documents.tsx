"use client";

import { useRef, useState } from "react";
import useSWR from "swr";
import { Icon } from "@/components/icon";
import { allPages, corpusSchema, documentSchema, requestJSON, sectionSchema, versionSchema } from "@/lib/documents";

export function DocumentWorkspace({ available, workerReady }: { available: boolean; workerReady: boolean }) {
  const [selected, setSelected] = useState("");
  const [documentId, setDocumentId] = useState("");
  const [name, setName] = useState("");
  const [message, setMessage] = useState("");
  const [actionError, setActionError] = useState("");
  const [busy, setBusy] = useState(false);
  const picker = useRef<HTMLInputElement>(null);
  const corpora = useSWR(available ? "corpora" : null, () => allPages("corpora", corpusSchema), { shouldRetryOnError: false });
  const corpusId = selected || corpora.data?.[0]?.id || "";
  const documents = useSWR(available && corpusId ? `documents/${corpusId}` : null,
    () => allPages(`corpora/${corpusId}/documents`, documentSchema), { refreshInterval: 3000, shouldRetryOnError: false });
  const versions = useSWR(available && corpusId ? `versions/${corpusId}` : null,
    () => allPages(`corpora/${corpusId}/versions`, versionSchema), { shouldRetryOnError: false });
  const evidence = useSWR(available && documentId ? `sections/${documentId}` : null,
    () => allPages(`documents/${documentId}/sections`, sectionSchema), { shouldRetryOnError: false });
  const currentDocument = documents.data?.find(doc => doc.id === documentId);
  const fetchError = corpora.error || documents.error || versions.error || evidence.error;
  const canPublish = available && !documents.error && !!documents.data?.length && documents.data.every(doc => doc.state === "ready");

  async function act(operation: () => Promise<void>) {
    setBusy(true); setMessage(""); setActionError("");
    try { await operation(); }
    catch (error) { setActionError(error instanceof Error ? error.message : "The request failed."); }
    finally { setBusy(false); }
  }

  return <section className="document-workspace" aria-label="Document corpus workspace">
    {!available && <div className="connection-message warning" role="status">Document uploads need PostgreSQL and the current migrations. Start the database, then refresh workspace setup.</div>}
    {available && !workerReady && <div className="connection-message warning" role="status">The worker is not connected. Uploads will wait safely in the queue until it starts.</div>}
    <div className="corpus-toolbar"><div className="field"><label htmlFor="corpus">Active corpus</label><select id="corpus" value={corpusId} disabled={!available || busy || !corpora.data?.length}
      onChange={event => { setSelected(event.target.value); setDocumentId(""); setMessage(""); setActionError(""); }}>
      {!corpora.data?.length && <option value="">{corpora.isLoading ? "Loading corpora…" : "Create your first corpus"}</option>}
      {corpora.data?.map(corpus => <option key={corpus.id} value={corpus.id}>{corpus.name}</option>)}
    </select></div>
      <form className="corpus-form" onSubmit={event => { event.preventDefault(); void act(async () => {
        const corpus = corpusSchema.parse(await requestJSON("corpora", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }) }));
        await corpora.mutate(); setSelected(corpus.id); setDocumentId(""); setName(""); setMessage(`Created ${corpus.name}.`);
      }); }}><div className="field"><label htmlFor="corpus-name">New corpus name</label><input id="corpus-name" maxLength={160} value={name} onChange={event => setName(event.target.value)} placeholder="e.g. PostgreSQL 17 manuals" disabled={!available || busy} required /></div>
        <button className="button subtle" disabled={!available || busy || !name.trim()} type="submit">Create corpus</button></form></div>
    <div role="status" aria-live="polite">{busy && <p className="action-message">Working…</p>}{message && <p className="action-message">{message}</p>}</div>
    {(actionError || fetchError) && <div className="connection-message warning" role="alert">{actionError || (fetchError instanceof Error ? fetchError.message : "Could not load corpus data.")}
      {fetchError && <button className="button subtle" disabled={busy} onClick={() => { void corpora.mutate(); void documents.mutate(); void versions.mutate(); void evidence.mutate(); }}>Try again</button>}</div>}
    <div className="section-topline document-actions"><div><h2>Source documents</h2><p className="muted-text">PDF · HTML · Markdown · UTF-8 text. Up to 50 MB per file.</p></div>
      <input ref={picker} className="file-picker" type="file" accept=".pdf,.html,.htm,.md,.markdown,.txt" aria-label="Choose a technical document" disabled={!available || !corpusId || busy}
        onChange={event => { const file = event.target.files?.[0]; if (!file) return; void act(async () => {
          if (file.size > 52_428_800) throw new Error("Choose a file smaller than 50 MB.");
          const body = new FormData(); body.append("file", file);
          const doc = documentSchema.parse(await requestJSON(`corpora/${corpusId}/documents`, { method: "POST", body }));
          await documents.mutate(); if (doc.state === "ready") setDocumentId(doc.id);
          setMessage(doc.state === "ready" ? "This document is already in the corpus." : `${doc.filename} is queued for extraction.`);
          if (picker.current) picker.current.value = "";
        }); }} />
      <button className="button primary" disabled={!available || !corpusId || busy} onClick={() => picker.current?.click()}><Icon name="documents" />Upload document</button></div>
    <div className="document-review-grid"><div className="table-frame">
      {documents.isLoading ? <div className="empty-state"><p>Loading documents…</p></div> : !documents.data?.length ? <div className="empty-state"><span className="empty-icon"><Icon name="documents" /></span><h3>Start with a source you trust.</h3><p>Create a corpus, then upload a technical document. Extraction keeps source locations and code formatting.</p></div> :
        <ul className="document-list">{documents.data.map(doc => <li key={doc.id} className={documentId === doc.id ? "selected" : ""}><div className="document-row"><div>
          <button className="document-name" disabled={doc.state !== "ready"} onClick={() => setDocumentId(doc.id)}>{doc.filename}</button>
          <p className="muted-text">{Math.max(1, Math.round(doc.byte_count / 1024))} KB{doc.state === "ready" ? ` · ${doc.section_count} source sections` : " · Original preserved"}</p></div><span className={`document-state ${doc.state}`}>{doc.state === "pending" ? "Queued" : doc.state === "processing" ? "Extracting" : doc.state === "ready" ? "Ready" : "Failed"}</span></div>
          {doc.error_message && <div className="document-failure"><p>{doc.error_message}</p><button className="button subtle" disabled={busy || !available} onClick={() => { void act(async () => { await requestJSON(`documents/${doc.id}/retry`, { method: "POST" }); await documents.mutate(); setMessage("Extraction queued for retry."); }); }}>Retry extraction</button></div>}
        </li>)}</ul>}
    </div><aside className="evidence-panel" aria-label="Extracted source evidence"><div className="section-topline"><h2>Source evidence</h2><span className="outline-tag">Canonical text</span></div>
      {!documentId ? <p className="muted-text">Select a ready document to inspect its extracted text and original source locations.</p> : evidence.isLoading ? <p>Loading source evidence…</p> : <><h3 className="evidence-filename">{currentDocument?.filename}</h3>
        {evidence.data?.map(section => <article className="source-section" key={section.id}><p className="eyebrow">{section.source.format}{section.source.page ? ` · Page ${section.source.page}` : section.source.start_line ? ` · Lines ${section.source.start_line}–${section.source.end_line}` : ""}{section.source.anchor ? ` · #${section.source.anchor}` : ""}</p>
          {section.heading_path.length > 0 && <p className="source-heading">{section.heading_path.join(" / ")}</p>}<pre>{section.text}</pre></article>)}</>}
    </aside></div>
    <section className="publication-section" aria-labelledby="versions-title"><div className="section-topline"><div><h2 id="versions-title">Published corpus versions</h2><p className="muted-text">Freeze ready evidence for reproducible experiments. Later uploads create a new draft.</p></div>
      <button className="button subtle" disabled={!canPublish || busy} onClick={() => { void act(async () => { const version = versionSchema.parse(await requestJSON(`corpora/${corpusId}/versions`, { method: "POST" })); await versions.mutate(); setMessage(`Version ${version.version} is published. Its evidence is immutable.`); }); }}>Publish version</button></div>
      {!versions.data?.length ? <p className="version-empty">No published versions yet. Every source must be ready before publication.</p> : <ul className="version-list">{versions.data.map(version => <li key={version.id}><strong>Version {version.version}</strong><span>{version.document_count} {version.document_count === 1 ? "document" : "documents"}</span><code title={version.manifest_hash}>{version.manifest_hash.slice(0, 12)}</code><span>Immutable</span></li>)}</ul>}
    </section>
  </section>;
}
