"use client";

import Link from "next/link";
import { useState } from "react";
import useSWR from "swr";
import { Icon } from "@/components/icon";
import { DocumentWorkspace } from "@/components/documents";
import { DatasetWorkspace } from "@/components/datasets";
import { ComparisonWorkspace } from "@/components/comparisons";
import { ExperimentWorkspace } from "@/components/experiments";
import { RetrievalWorkspace } from "@/components/retrieval";
import { sections, workspaceSchema, type Section, type WorkspaceStatus } from "@/lib/workspace";

const copy: Record<Section, { title: string; description: string }> = {
  experiments: { title: "Experiments", description: "A controlled workspace for questions, retrieval, and the evidence behind every answer." },
  documents: { title: "Documents", description: "Build a versioned corpus. Keep each answer connected to its original source." },
  datasets: { title: "Evaluation datasets", description: "Curate questions, reference answers, and supporting passages before you measure." },
  comparisons: { title: "Comparisons", description: "Compare retrieval methods under the same conditions, one question at a time." },
  settings: { title: "Workspace setup", description: "Check the services that power your local research environment." },
};

export function Workspace({ section, initialRunId, initialComparisonId, initialResultId, failureRunId }: { section: Section; initialRunId?: string; initialComparisonId?: string; initialResultId?: string; failureRunId?: string }) {
  const { data, error, isLoading, isValidating, mutate } = useSWR<WorkspaceStatus>("/api/workspace", fetchWorkspace, {
    refreshInterval: 15_000,
    shouldRetryOnError: false,
  });
  const workspace = data ?? null;
  const busy = isLoading || isValidating;
  const [menuOpen, setMenuOpen] = useState(false);
  const apiAvailable = workspace !== null && !error;
  const dbReady = apiAvailable && workspace.database.status === "ready";
  const current = failureRunId ? { title: "Run diagnostics", description: "Inspect frozen answers, retrieval coverage, and evaluation signals." } : copy[section];

  return <div className="app-shell">
    <a className="skip-link" href="#main">Skip to main content</a>
    <aside className="sidebar">
      <Link className="brand" href="/" aria-label="RAG Observatory home">
        <span className="brand-symbol"><Icon name="book" /></span>
        <span>RAG Observatory<small>RELIABILITY WORKSPACE</small></span>
      </Link>
      <button className="mobile-menu button subtle" onClick={() => setMenuOpen(!menuOpen)}
        aria-expanded={menuOpen} aria-controls="workspace-navigation"><Icon name="menu" />Navigation</button>
      <nav id="workspace-navigation" className={menuOpen ? "navigation open" : "navigation"} aria-label="Workspace">
        <p className="nav-label">WORKSPACE</p>
        {sections.filter((item) => item.id !== "settings").map((item) =>
          <Link className={`nav-link ${item.id === section ? "active" : ""}`} href={item.href}
            aria-current={item.id === section ? "page" : undefined} key={item.id}>
            <Icon name={item.id} />{item.label}<span className="active-marker" /></Link>)}
        <p className="nav-label system-label">ENVIRONMENT</p>
        <Link className={`nav-link ${section === "settings" ? "active" : ""}`} href="/settings"
          aria-current={section === "settings" ? "page" : undefined}><Icon name="settings" />Settings<span className="active-marker" /></Link>
      </nav>
      <div className="sidebar-note"><span className="eyebrow">FIRST RESEARCH DOMAIN</span>
        <strong>PostgreSQL documentation</strong><p>Versioned sources.<br />Evidence-grounded answers.</p>
        <span className="outline-tag">Local workspace</span>
      </div>
      <div className="sidebar-footer"><span className="tiny-mark">RO</span><span>Local workspace<small>v0.1.0</small></span></div>
    </aside>

    <div className="main-shell">
      <header className="topbar"><div className="breadcrumb">Workspace<span>/</span><strong>{section === "settings" ? "Settings" : current.title}</strong></div>
        <span className={`connection-pill ${apiAvailable ? "connected" : ""}`}><span className="status-dot" />
          {busy && !workspace ? "Checking API" : apiAvailable ? "API connected" : "API unavailable"}</span>
      </header>
      <main id="main" className="main-content" tabIndex={-1}>
        <div className="page-heading"><div><p className="eyebrow">RETRIEVAL · EVIDENCE · EVALUATION</p>
          <h1>{current.title}</h1><p className="page-description">{current.description}</p></div>
          {section !== "settings" && <Link className={`button ${(section === "documents" || section === "datasets" || section === "experiments") ? "subtle" : "primary"}`} href="/settings">View setup<Icon name="arrow" /></Link>}
        </div>

        {!initialRunId && !initialComparisonId && !failureRunId && <div className="foundation-notice"><span className="notice-label">LOCAL RELEASE</span>
          <p><Link className="text-link" href="/demo">Explore the read-only demo</Link>. Upload documents, curate reviewed datasets, and run lexical, dense, or hybrid retrieval with local CPU answers. Inspect saved retrieval metrics and question evidence.</p></div>}

        {section === "experiments" && <>
          <ExperimentWorkspace available={dbReady && !!workspace?.capabilities.includes("experiment_runs")} configured={!!workspace?.generation_configured} workerReady={workspace?.database.worker_status === "ready"} initialRunId={initialRunId} initialResultId={initialResultId} failureRunId={failureRunId} />
          {!initialRunId && !failureRunId && <RetrievalWorkspace available={dbReady && !!workspace?.capabilities.includes("lexical_indexing")} workerReady={workspace?.database.worker_status === "ready"} />}
          {!initialRunId && !failureRunId && <section className="workflow" aria-labelledby="workflow-title"><div className="section-topline"><h2 id="workflow-title">From source to finding</h2><span className="muted-text">The research workflow</span></div>
            <div className="workflow-steps">
              <WorkflowStep number="01" title="Prepare the evidence" text="Freeze a document corpus and annotate the passages that support each question." href="/documents" icon="documents" />
              <WorkflowStep number="02" title="Run controlled experiments" text="Keep the questions and answer model fixed. Change the retrieval strategy." href="/datasets" icon="experiments" />
              <WorkflowStep number="03" title="Understand the differences" text="Compare accuracy and latency, then inspect where an answer lost its grounding." href="/comparisons" icon="comparisons" />
            </div>
          </section>}
          <div className="research-footnote"><Icon name="book" /><p><strong>A reproducible comparison, by design.</strong> Corpus versions, dataset versions, model settings, and scoring rules travel with every run.</p></div>
        </>}

        {section === "documents" && <DocumentWorkspace available={dbReady && !!workspace?.capabilities.includes("document_ingestion")} workerReady={workspace?.database.worker_status === "ready"} />}
        {section === "datasets" && <DatasetWorkspace available={dbReady && !!workspace?.capabilities.includes("dataset_curation")} />}
        {section === "comparisons" && <ComparisonWorkspace available={dbReady && !!workspace?.capabilities.includes("paired_comparisons")} workerReady={workspace?.database.worker_status === "ready"} initialId={initialComparisonId} />}

        {section === "settings" && <section className="setup-section" aria-labelledby="services-title">
          <div className="section-topline"><h2 id="services-title">Service connections</h2>
            <button className="button subtle" disabled={busy} onClick={() => { void mutate(); }}><Icon name="refresh" />{busy ? "Checking…" : "Refresh connection"}</button></div>
          <div aria-live="polite" role="status" className={`connection-message ${error ? "warning" : ""}`}>
            {error ? `The API is unavailable. Start the API and refresh the connection.${workspace ? " Showing the last known service state below." : ""}` : !workspace ? "Checking the local services…" : dbReady ? "Database and schema are ready. Document ingestion, retrieval, and saved experiment runs are available." : workspace.database.message}
          </div>
          <dl className="service-list">
            <ServiceRow title="FastAPI" detail="Application API and capability discovery" state={apiAvailable ? "Connected" : busy && !workspace ? "Checking" : "Unavailable"} ready={apiAvailable} />
            <ServiceRow title="PostgreSQL + pgvector" detail="Persistent data, vector support, and schema migrations" state={workspace ? workspace.database.status === "ready" ? error ? "Last known: ready" : "Ready" : "Unavailable" : "Not checked"} ready={dbReady} />
            <ServiceRow title="Python worker" detail="Durable ingestion, indexing, retrieval, and answer runs" state={workspace?.database.worker_status === "ready" ? error ? "Last known: ready" : "Ready" : workspace?.database.worker_status === "stale" ? "Heartbeat stale" : "Not connected"} ready={apiAvailable && workspace?.database.worker_status === "ready"} />
            <ServiceRow title="Answer model" detail="Pinned Qwen2.5 0.5B on CPU; worker execution" state={workspace ? `${error ? "Last known: " : ""}${workspace.generation_configured ? "Configured" : "Not configured"}` : "Not checked"} ready={workspace?.judge_configured === true} />
            <ServiceRow title="Evaluation judge" detail="Optional local self-judge; uncalibrated model estimates" state={workspace ? `${error ? "Last known: " : ""}${workspace.judge_configured ? "Configured" : "Not configured"}` : "Not checked"} ready={workspace?.judge_configured === true} />
          </dl>
          <div className="setup-instructions"><h3>Start your local environment</h3><p>From the project root, with Docker installed and your environment file prepared:</p>
            <pre><code>docker compose up --build</code></pre><p>For native development, start the API and dashboard in separate terminals:</p>
            <pre><code>uv run uvicorn rag_api.main:app --reload{"\n"}npm run dev</code></pre>
            <p className="muted-text">Embedding and answer inference run locally when enabled. Model credentials stay on the server. Saved answers support versioned local judging and named human review.</p>
          </div>
        </section>}
        <footer className="workspace-footer"><span>RAG Observatory</span><span>Evidence first. Conclusions earned.</span></footer>
      </main>
    </div>
  </div>;
}

async function fetchWorkspace(url: string): Promise<WorkspaceStatus> {
  const response = await fetch(url, { cache: "no-store", signal: AbortSignal.timeout(8000) });
  if (!response.ok) throw new Error("API unavailable");
  return workspaceSchema.parse(await response.json());
}

function WorkflowStep({ number, title, text, href, icon }: { number: string; title: string; text: string; href: string; icon: Section }) {
  return <article className="workflow-step"><div className="step-marker"><span>{number}</span><Icon name={icon} /></div>
    <h3>{title}</h3><p>{text}</p><Link className="step-link" href={href}>{icon === "documents" ? "Documents" : icon === "experiments" ? "Evaluation datasets" : "Comparisons"}<Icon name="arrow" /></Link></article>;
}


function ServiceRow({ title, detail, state, ready }: { title: string; detail: string; state: string; ready: boolean }) {
  return <div className="service-row"><dt><strong>{title}</strong><span>{detail}</span></dt><dd className={ready ? "service-state ready" : "service-state"}>
    {ready && <Icon name="check" />}{state}</dd></div>;
}
