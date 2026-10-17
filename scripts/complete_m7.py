"""Resume M7 qualification, held-out execution and evidence delivery without changing workers.

Only lightweight orchestration runs here. Inference, comparisons and ZIP generation use
the existing durable worker. This never invents answer judgments or auto-completes M7.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from rag_core.runs import ExperimentCreate, digest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/research/postgresql-18.0"
WORK = SOURCE / "completion"
API = "http://127.0.0.1:8000/api/v1"
SCOPE_PATH = ROOT / "research/postgresql-18.0/DELIVERY_SCOPE.json"
TERMINAL = {"completed", "completed_with_errors", "failed", "cancelled"}


def now() -> str:
    return datetime.now(UTC).isoformat()


def save(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def call(path: str, body: Any = None, key: str | None = None) -> Any:
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Idempotency-Key"] = key
    request = urllib.request.Request(
        API + path, data=None if body is None else json.dumps(body).encode(), headers=headers
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read(32 * 1024 * 1024 + 1)
    if len(raw) > 32 * 1024 * 1024:
        raise ValueError("API response exceeds the bounded campaign size")
    return json.loads(raw)


def items(path: str) -> list[Any]:
    rows, cursor = [], 0
    for _ in range(20):
        page = call(f"{path}?limit=100&cursor={cursor}")
        rows.extend(page["items"])
        if page["next_cursor"] is None:
            return rows
        cursor = page["next_cursor"]
    raise ValueError("Campaign pagination limit exceeded")


def key_for(kind: str, body: Any) -> str:
    return "m7-" + kind + "-" + digest(body)


def verify_config(manifest: dict[str, Any], request: dict[str, Any]) -> None:
    if any(manifest.get(key) != request[key] for key in ["dataset_version_id", "index_id"]) or any(
        manifest["config"].get(key) != value
        for key, value in request.items()
        if key not in {"name", "dataset_version_id", "index_id"}
    ):
        raise ValueError("Run configuration differs from its exact prepared request")


def qualify(definition: dict[str, Any], runs: dict[str, Any], manifests: dict[str, Any]) -> str:
    """Completion is necessary for qualification, but never an answer-quality judgment."""
    cells = {cell["cell"] for cell in definition["cells"]}
    if len(cells) != 8 or set(runs) != cells or set(manifests) != cells:
        raise ValueError("Qualification requires all eight exact development cells")
    for cell in cells:
        manifest = manifests[cell]
        request = next(c["request"] for c in definition["cells"] if c["cell"] == cell)
        verify_config(manifest, request)
        if (
            manifest["dataset_hash"] != definition["dataset_manifest_hash"]
            or manifest["dataset_version_id"] != definition["dataset_version_id"]
            or manifest["config"]["split"] != "development"
            or manifest["config"]["repeats"] != 1
            or len(manifest["questions"]) != 105
            or any(q["content"]["split"] != "development" for q in manifest["questions"])
        ):
            raise ValueError("Development qualification lineage/split/repeat changed")
        run = runs[cell]
        if run["state"] in TERMINAL and (
            run["state"] != "completed"
            or run["completed_count"] != 105
            or run["failed_count"]
            or run["total_count"] != 105
        ):
            return "development_requires_attention"
    if len({digest(m["execution"]) for m in manifests.values()}) != 1:
        raise ValueError("Development runs use different execution identities")
    universes = {
        digest(sorted((q["id"], q["revision"], digest(q["content"])) for q in m["questions"]))
        for m in manifests.values()
    }
    if len(universes) != 1:
        raise ValueError("Development cells use different question revisions or gold")
    if any(r["state"] != "completed" for r in runs.values()):
        return "waiting_for_development"
    return "qualified"


def heldout_requests(definition: dict[str, Any]) -> list[dict[str, Any]]:
    requests = []
    for cell in definition["cells"]:
        value = dict(cell["request"])
        value.update(
            name="PG18 held-out: " + cell["cell"],
            split="test",
            repeats=3,
            measurement_notes=(
                "Held-out execution after complete development qualification; unchanged budgets. "
                "Three greedy repeats; uncontrolled cache; sequential worker. "
                "No quality endorsement."
            ),
        )
        value = ExperimentCreate.model_validate(value).model_dump(mode="json")
        requests.append({"cell": cell["cell"], "request": value})
    if len(requests) != 8 or any(x["request"]["split"] != "test" for x in requests):
        raise ValueError("Use only the fixed eight-cell held-out matrix")
    return requests


def verify_terminal(run: dict[str, Any], manifest: dict[str, Any], locked: dict[str, Any]) -> None:
    expected = set(locked["test_question_ids"])
    if (
        manifest["dataset_hash"] != locked["dataset_manifest_hash"]
        or digest(manifest["execution"]) != locked["execution_sha256"]
        or manifest["config"]["split"] != "test"
        or manifest["config"]["repeats"] != 3
        or {q["id"] for q in manifest["questions"]} != expected
        or len(expected) != 45
        or any(q["content"]["split"] != "test" for q in manifest["questions"])
        or run["total_count"] != 135
    ):
        raise ValueError("Held-out execution differs from the locked controls")


def select_review_questions(questions: list[Any]) -> list[str]:
    """Three questions/topic, including one negative where available, selected by ID only."""
    selected = []
    for topic in sorted({q["content"]["topic"] for q in questions}):
        group = sorted(
            [q for q in questions if q["content"]["topic"] == topic], key=lambda q: q["id"]
        )
        negatives = [q for q in group if not q["content"]["answerable"]]
        chosen = negatives[:1]
        chosen += [q for q in group if q not in chosen][: 3 - len(chosen)]
        selected.extend(q["id"] for q in chosen)
    if len(selected) != 15 or len(set(selected)) != 15:
        raise ValueError("Review sample requires15 unique stratified questions")
    return selected


def snapshot_runs(submissions: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    runs, manifests = {}, {}
    for cell, entry in submissions.items():
        runs[cell] = call("/runs/" + entry["run_id"])
        manifests[cell] = call("/runs/" + entry["run_id"] + "/manifest")
    return runs, manifests


def freeze(
    campaign: dict[str, Any], runs: dict[str, Any], manifests: dict[str, Any]
) -> dict[str, Any]:
    definition = campaign["definition"]
    if qualify(definition, runs, manifests) != "qualified":
        raise ValueError("Cannot freeze before successful full development qualification")
    dataset = read(SOURCE / "published-dataset-01.json")
    if digest(dataset["manifest"]) != definition["dataset_manifest_hash"]:
        raise ValueError("Frozen local dataset differs from the development input")
    expected_development = sorted(
        (q["id"], q["revision"], digest(q["content"]))
        for q in dataset["manifest"]["questions"]
        if q["content"]["split"] == "development"
    )
    observed_development = sorted(
        (q["id"], q["revision"], digest(q["content"]))
        for q in next(iter(manifests.values()))["questions"]
    )
    if observed_development != expected_development:
        raise ValueError("Development question universe differs from the published snapshot")
    result = {
        "schema": "m7-locked-controls-v1",
        "delivery_scope": read(SCOPE_PATH),
        "frozen_at": now(),
        "dataset_version_id": definition["dataset_version_id"],
        "dataset_manifest_hash": definition["dataset_manifest_hash"],
        "development_definition_sha256": campaign["definition_sha256"],
        "development_runs": {
            c: {"id": r["id"], "manifest_hash": r["manifest_hash"]} for c, r in runs.items()
        },
        "execution_sha256": digest(next(iter(manifests.values()))["execution"]),
        "test_question_ids": sorted(
            q["id"] for q in dataset["manifest"]["questions"] if q["content"]["split"] == "test"
        ),
        "requests": heldout_requests(definition),
        "decision": (
            "Retain all proposed budgets/methods unchanged after complete software qualification; "
            "no optimization on held-out outputs or answer-quality selection."
        ),
        "answer_quality": "Unassessed; source-reviewed gold is not generated-answer review.",
    }
    if len(result["test_question_ids"]) != 45:
        raise ValueError("Wrong held-out question universe")
    summaries = {cell: items("/runs/" + run["id"] + "/results") for cell, run in runs.items()}
    if any(
        len(rows) != 105 or any(r["state"] != "succeeded" for r in rows)
        for rows in summaries.values()
    ):
        raise ValueError("Qualification result rows are incomplete")
    save(WORK / "development-results.json", summaries)
    result["development_results_sha256"] = digest(summaries)
    save(WORK / "locked-controls.json", result)
    return result


def submit_tests(locked: dict[str, Any], state: dict[str, Any]) -> None:
    for cell in locked["requests"]:
        name, value = cell["cell"], cell["request"]
        experiment = call("/experiments", value)
        body = {"lock_sha256": digest(locked), "cell": name, "experiment_id": experiment["id"]}
        entry = state.setdefault("test_runs", {}).setdefault(
            name, {"experiment_id": experiment["id"], "key": key_for("test", body)}
        )
        if entry["experiment_id"] != experiment["id"] or entry["key"] != key_for("test", body):
            raise ValueError("Stored submission key differs from locked controls")
        save(WORK / "state.json", state)  # Before POST, including ambiguous network failures.
        run = call("/experiments/" + experiment["id"] + "/runs", {}, entry["key"])
        manifest = call("/runs/" + run["id"] + "/manifest")
        verify_config(manifest, value)
        verify_terminal(run, manifest, locked)
        entry.update(run_id=run["id"], manifest_hash=run["manifest_hash"])
        entry.setdefault("submitted_at", now())
        save(WORK / "state.json", state)
        save(WORK / ("manifest-" + run["id"] + ".json"), manifest)


def review_pack(runs: dict[str, Any], manifests: dict[str, Any]) -> None:
    if (WORK / "answer-review-pack.json").exists():
        return
    questions = manifests["section/dense"]["questions"]
    selected = select_review_questions(questions)
    cases = []
    for cell in ["section/dense", "section/hybrid_rerank"]:
        run_id = runs[cell]["id"]
        rows = items("/runs/" + run_id + "/results")
        for qid in selected:
            row = next((r for r in rows if r["question_id"] == qid and r["repeat"] == 0), None)
            if row is None or row["state"] != "succeeded":
                continue
            trace = call("/runs/" + run_id + "/results/" + row["id"])["trace"]
            cases.append(
                {
                    "run_id": run_id,
                    "result_id": row["id"],
                    "cell": cell,
                    "question": trace["question"],
                    "answer": trace["generation"]["answer"],
                    "delivered_evidence": trace["generation"]["context"],
                    "trace_url": f"http://localhost:3000/runs/{run_id}/results/{row['id']}",
                    "review_status": "unreviewed",
                    "reviewer": None,
                    "judgment": None,
                }
            )
    save(
        WORK / "answer-review-pack.json",
        {
            "generated_at": now(),
            "purpose": (
                "Unreviewed30-case calibration/review preparation, "
                "not a scored evaluation or representative accuracy estimate."
            ),
            "selection": (
                "15 question IDs: three per topic, one negative where available; "
                "both primary methods; repeat0. No output-based selection."
            ),
            "cases": cases,
        },
    )


def submit_analyses(runs: dict[str, Any], state: dict[str, Any]) -> None:
    pairs = [("section/dense", "section/hybrid_rerank"), ("section/dense", "section/hybrid")]
    pairs += [(f"{s}/lexical", f"{s}/dense") for s in ["fixed", "section"]]
    pairs += [
        (f"fixed/{m}", f"section/{m}") for m in ["lexical", "dense", "hybrid", "hybrid_rerank"]
    ]
    for baseline, candidate in pairs:
        name = baseline + " vs " + candidate
        body = {
            "name": "PG18 exploratory: " + name,
            "baseline_run_id": runs[baseline]["id"],
            "candidate_run_id": runs[candidate]["id"],
            "assessment_source": "human",
            "exploratory": True,
            "seed": 0,
            "resamples": 1000,
        }
        row = call("/comparisons", body, key_for("comparison", body))
        state.setdefault("comparisons", {})[name] = row["id"]
        save(WORK / "state.json", state)


def download_export(job: dict[str, Any]) -> None:
    destination = WORK / "evidence" / (job["id"] + ".zip")
    expected = job["output"]["sha256"]
    if destination.exists():
        if file_hash(destination) != expected:
            raise ValueError("Existing evidence bytes changed")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_suffix(".partial")
    size, hashed = 0, hashlib.sha256()
    with (
        urllib.request.urlopen(API + "/exports/" + job["id"] + "/download", timeout=60) as response,
        temp.open("wb") as stream,
    ):
        while chunk := response.read(1024 * 1024):
            size += len(chunk)
            if size > 200 * 1024 * 1024:
                raise ValueError("Evidence ZIP exceeds bounded operator download size")
            hashed.update(chunk)
            stream.write(chunk)
    if hashed.hexdigest() != expected or size != job["output"]["bytes"]:
        raise ValueError("Evidence download checksum or size mismatch")
    with ZipFile(temp) as archive:
        if (
            len(archive.infolist()) > 20000
            or sum(i.file_size for i in archive.infolist()) > 256 * 1024 * 1024
        ):
            raise ValueError("Evidence archive expands beyond the verification bound")
        checksums = json.loads(archive.read("checksums.json"))
        if set(archive.namelist()) != set(checksums) | {"checksums.json"}:
            raise ValueError("Evidence entry inventory mismatch")
        for name, sha in checksums.items():
            h = hashlib.sha256()
            with archive.open(name) as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    h.update(chunk)
            if h.hexdigest() != sha:
                raise ValueError("Evidence member checksum mismatch")
    temp.replace(destination)


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def percent(value: Any) -> str:
    return "unavailable" if value is None else f"{100 * value:.2f}"


def seconds(value: Any) -> str:
    return "unavailable" if value is None else f"{value / 1000:.2f}"


def report(runs: dict[str, Any], comparisons: dict[str, Any]) -> None:
    lines = [
        "# PostgreSQL18.0 held-out benchmark report",
        "",
        "Generated at " + now() + ".",
        "",
        (
            "The primary factual-accuracy hypothesis is **not established**: answers lack "
            "valid recorded quality assessments. Observed retrieval results do not substitute for "
            "answer correctness."
        ),
        "",
        (
            "Corpus:40 purposeful PostgreSQL18.0 pages. Dataset:150 reviewed questions "
            "(10 human/140 AI gold reviews);105 development/45 test across23 source families, "
            "including8 held-out groups. Same-assistant curation and incomplete relevance labels "
            "limit validity. All30 negatives concern missing instance data."
        ),
        "",
        (
            "Controls:240-token chunks/32 overlap; top-k5; context1024; max output128; local "
            "Qwen0.5B; three repeats per held-out question. Repeats average per question before "
            "whole-group bootstrap and are not independent samples. Cache/shared-host timing are "
            "uncontrolled. Local energy and financial cost are unavailable."
        ),
        "",
        "| Cell | State | Succeeded/planned | Failed | Recall % | Scored/applicable |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for cell, run in sorted(runs.items()):
        metric = run["metrics"].get("retrieval_recall", {})
        lines.append(
            f"| {cell} | {run['state']} | {run['completed_count']}/{run['total_count']} | "
            f"{run['failed_count']} | {percent(metric.get('mean'))} | "
            f"{metric.get('scored_count', 'unavailable')}/"
            f"{metric.get('applicable_count', 'unavailable')} |"
        )
    lines += [
        "",
        "## Frozen paired reports",
        "",
        (
            "Comparisons are explicitly exploratory. Missing answer scores stay unavailable. "
            "Index/chunking differences and other control exclusions remain in the saved reports. "
            "Effects and intervals below are percentage points, candidate minus baseline; "
            "multiple comparisons are unadjusted."
        ),
        "",
    ]
    for name, row in comparisons.items():
        lines += [
            f"### {name}",
            "",
            f"[Saved comparison](http://localhost:3000/comparisons/{row['id']}) · {row['state']}",
            "",
            "| Metric | Delta pp | 95% interval pp | Paired questions/groups | Excluded |",
            "|---|---:|---|---:|---:|",
        ]
        for metric, value in (row.get("output") or {}).get("metrics", {}).items():
            interval = value.get("interval")
            ci = (
                "unavailable"
                if interval is None
                else f"{percent(interval['low'])} to {percent(interval['high'])}"
            )
            lines.append(
                f"| {metric} | {percent(value.get('difference'))} | {ci} | "
                f"{value.get('paired_question_count', 0)}/{value.get('group_count', 0)} | "
                f"{value.get('excluded_question_count', 0)} |"
            )
        lines.append("")
    lines += [
        "## Observed timing and accounting",
        "",
        "No subgroup filters were applied. Timing below uses saved full-run observation samples, "
        "not independent question means or a controlled hardware comparison. Question timers "
        "exclude queue/shared preparation and include per-call model hashing/loading. Run windows "
        "can include recovery gaps. See HARDWARE.md for the observed host and resource limits.",
        "",
        "| Run | Stage | p50 seconds | p95 seconds | Measured/unavailable |",
        "|---|---|---:|---:|---:|",
    ]
    seen = set()
    for name, row in comparisons.items():
        for side, account in (row.get("output") or {}).get("accounting", {}).items():
            run_id = row.get("manifest_summary", {}).get(side, {}).get("id", name + "/" + side)
            if run_id in seen:
                continue
            seen.add(run_id)
            for stage, values in account.get("stage_timings", {}).items():
                lines.append(
                    f"| {run_id} | {stage} | {seconds(values.get('p50'))} | "
                    f"{seconds(values.get('p95'))} | {values.get('scored_count', 0)}/"
                    f"{values.get('unavailable_count', 0)} |"
                )
    lines += [
        "",
        "Attempt counts, generation/judge token ledgers, unknown usage, queue/run windows and "
        "index-build measurements remain in each frozen report's accounting object and checked "
        "evidence ZIP. Local financial/energy cost remains unavailable rather than zero.",
        "",
    ]
    lines += [
        "## Unvalidated answer quality",
        "",
        (
            "The local answer-review-pack.json contains up to30 real, unreviewed cases from15 "
            "question IDs, balanced across topics and both primary methods. Reviewers/judgments "
            "remain blank. This is not a human validation sample or calibrated model score. "
            "The owner selected exploratory delivery with answer quality unvalidated. "
            "Valid assessments are still needed for future factual-accuracy claims. New judgments "
            "require new explicitly frozen analyses; saved reports never backfill them."
        ),
        "",
        "## Evidence and recovery",
        "",
        (
            "Worker evidence ZIPs are checked against outer and per-entry SHA-256 values. Full "
            "inputs, controller receipts and frozen configuration stay under private data/. "
            "See completion/delivery.json for actual post-experiment backup status. Same-machine "
            "restore does not prove offsite recovery or historical bitwise inference replay."
        ),
        "",
    ]
    path = ROOT / "research/postgresql-18.0/BENCHMARK_REPORT.md"
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def completion_policy(
    runs: dict[str, Any], comparisons: dict[str, Any], scope: dict[str, Any]
) -> dict[str, Any]:
    approved = (
        scope.get("schema") == "m7-delivery-scope-v1"
        and scope.get("mode") == "exploratory_retrieval"
        and scope.get("authorization")
        == "Deliver an exploratory report with answer quality unvalidated"
        and scope.get("answer_quality") == "unvalidated"
        and scope.get("human_calibration") == "not_performed"
        and scope.get("primary_factual_accuracy_hypothesis") == "not_established"
    )
    execution_complete = len(runs) == 8 and all(
        r["state"] == "completed"
        and r["completed_count"] == r["total_count"] == 135
        and r["failed_count"] == 0
        and r.get("cancelled_count", 0) == 0
        for r in runs.values()
    )
    analysis_complete = len(comparisons) == 8 and all(
        c["state"] == "completed" for c in comparisons.values()
    )
    return {
        "delivery_scope": scope,
        "answer_quality": "unvalidated",
        "human_calibration": "not_performed",
        "primary_factual_accuracy_hypothesis": "not_established",
        "execution_complete": execution_complete,
        "analysis_complete": analysis_complete,
        # Caller applies this only after verified exports/report/isolated restoration.
        "m7_complete": approved and execution_complete and analysis_complete,
    }


def finish_handoff(delivery: dict[str, Any]) -> None:
    if not (
        delivery.get("m7_complete") is True
        and delivery.get("restore_status") == "passed"
        and delivery.get("execution_complete") is True
        and delivery.get("analysis_complete") is True
    ):
        raise ValueError("Cannot finalize documentation before verified exploratory delivery")
    marker = "<!-- m7-exploratory-delivery:" + digest(delivery) + " -->"
    text = (
        "\n\n## M7 exploratory delivery completed\n\n"
        + marker
        + "\n\nRecorded at "
        + delivery["completed_at"]
        + ". All eight development runs qualified; all eight held-out runs completed "
        "135 successful observations each (1,080 held-out observations); all eight exploratory "
        "comparisons and requested evidence exports completed. Outer/member checksums and the "
        "post-experiment manifest-bound isolated restore passed. See "
        "research/postgresql-18.0/BENCHMARK_REPORT.md and private "
        "data/research/postgresql-18.0/completion/delivery.json for actual evidence.\n\n"
        "M7 is complete only under the owner's exploratory-retrieval delivery scope. "
        "Answer quality is unvalidated; human calibration was not performed; the primary "
        "factual-accuracy hypothesis is not established. Missing quality/cost remain unavailable. "
        "The backup captures experiments/evidence before this terminal receipt/document update; "
        "same-machine recovery is not offsite recovery or inference replay. No commit/push or "
        "public deployment is implied.\n"
    )
    for name in ["TASKS.md", "CODEX_HANDOFF.md", "AGENTS.md"]:
        path = ROOT / name
        current = path.read_text(encoding="utf-8")
        if marker in current:
            continue
        if name == "TASKS.md":
            current = current.replace(
                "- [ ] Run controlled experiments and export evidence-backed report.",
                "- [x] Run exploratory experiments and export an evidence-backed report "
                "(answer quality unvalidated).",
                1,
            ).replace(
                "- [ ] Verify backup/restore, operations guide, and final handoff.",
                "- [x] Verify backup/restore, operations guide, and exploratory final handoff.",
                1,
            )
        path.write_text(current + text, encoding="utf-8", newline="\n")


def step(state: dict[str, Any]) -> str:
    campaign = read(SOURCE / "development-execution.json")
    runs, manifests = snapshot_runs(campaign["submissions"])
    status = qualify(campaign["definition"], runs, manifests)
    state["development_progress"] = {
        c: {k: r[k] for k in ["state", "completed_count", "failed_count", "total_count"]}
        for c, r in runs.items()
    }
    if status != "qualified":
        return status
    locked_path = WORK / "locked-controls.json"
    locked = read(locked_path) if locked_path.exists() else freeze(campaign, runs, manifests)
    if locked.get("delivery_scope") != read(SCOPE_PATH):
        raise ValueError("Delivery scope differs from its frozen authorization")
    if locked["development_definition_sha256"] != campaign["definition_sha256"]:
        raise ValueError("Qualification campaign changed after controls froze")
    if locked["requests"] != heldout_requests(campaign["definition"]) or locked[
        "execution_sha256"
    ] != digest(next(iter(manifests.values()))["execution"]):
        raise ValueError("Locked controls or execution identity changed")
    submit_tests(locked, state)
    runs, manifests = snapshot_runs(state["test_runs"])
    for cell, run in runs.items():
        request = next(c["request"] for c in locked["requests"] if c["cell"] == cell)
        verify_config(manifests[cell], request)
        verify_terminal(run, manifests[cell], locked)
    state["test_progress"] = {
        c: {k: r[k] for k in ["state", "completed_count", "failed_count", "total_count"]}
        for c, r in runs.items()
    }
    if any(r["state"] not in TERMINAL for r in runs.values()):
        return "waiting_for_heldout"
    save(WORK / "terminal-runs.json", runs)
    review_pack(runs, manifests)
    submit_analyses(runs, state)
    comparisons = {name: call("/comparisons/" + cid) for name, cid in state["comparisons"].items()}
    if any(c["state"] not in {"completed", "failed"} for c in comparisons.values()):
        return "waiting_for_comparisons"
    save(WORK / "comparisons.json", comparisons)
    sources = [("run", r["id"]) for r in runs.values()]
    sources += [("comparison", c["id"]) for c in comparisons.values() if c["state"] == "completed"]
    for kind, source_id in sources:
        body = {"source_kind": kind, "source_id": source_id}
        job = call("/exports", body, key_for("export", body))
        state.setdefault("exports", {})[source_id] = job["id"]
        save(WORK / "state.json", state)
    jobs = [call("/exports/" + jid) for jid in state["exports"].values()]
    if any(j["state"] not in {"completed", "failed"} for j in jobs):
        return "waiting_for_exports"
    if any(j["state"] != "completed" for j in jobs):
        return "export_requires_attention"
    for job in jobs:
        download_export(job)
    save(WORK / "verified-exports.json", jobs)
    report(runs, comparisons)
    backup = ROOT / "data/backups/m7-post-experiments-01"
    if not (backup / "backup-manifest.json").exists():
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/backup_workspace.py"),
                "create",
                "--directory",
                str(backup),
            ],
            cwd=ROOT,
            check=True,
            timeout=1200,
        )
    if not (backup / "restore-report.json").exists():
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/backup_workspace.py"),
                "verify",
                "--directory",
                str(backup),
            ],
            cwd=ROOT,
            check=True,
            timeout=1200,
        )
    restore = read(backup / "restore-report.json")
    if restore["status"] != "passed" or restore["backup_manifest_sha256"] != file_hash(
        backup / "backup-manifest.json"
    ):
        raise ValueError("Post-experiment restore report does not bind the backup")
    policy = completion_policy(runs, comparisons, locked["delivery_scope"])
    delivery_path = WORK / "delivery.json"
    delivery = (
        read(delivery_path)
        if delivery_path.exists()
        else {
            "completed_at": now(),
            "backup": str(backup),
            "restore_status": "passed",
            **policy,
        }
    )
    if any(delivery.get(k) != v for k, v in policy.items()):
        raise ValueError("Existing terminal delivery differs from its frozen policy/results")
    save(delivery_path, delivery)
    if policy["m7_complete"]:
        finish_handoff(delivery)
    return "completed_exploratory" if policy["m7_complete"] else "delivery_requires_attention"


def advance(state: dict[str, Any]) -> None:
    """Retry a bounded transient outage; data/configuration errors always stop immediately."""
    try:
        state["phase"] = step(state)
        state.pop("last_error", None)
        state.pop("consecutive_api_errors", None)
    except Exception as error:
        transient = isinstance(error, (urllib.error.URLError, TimeoutError, ConnectionError))
        if isinstance(error, urllib.error.HTTPError):
            transient = error.code in {408, 429, 500, 502, 503, 504}
        if transient:
            state["consecutive_api_errors"] = state.get("consecutive_api_errors", 0) + 1
        state["phase"] = (
            "waiting_for_api"
            if transient and state["consecutive_api_errors"] < 5
            else "requires_attention"
        )
        state["last_error"] = {"type": type(error).__name__, "message": str(error)[:1000]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watch", action="store_true")
    args = parser.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    # OS-released lock prevents two native controllers from racing receipt files.
    with (WORK / "controller.lock").open("a+b") as lock:
        if lock.tell() == 0:
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        path = WORK / "state.json"
        state = read(path) if path.exists() else {"started_at": now(), "schema": "m7-completion-v1"}
        previous = None
        while True:
            advance(state)
            state["observed_at"] = now()
            save(path, state)
            summary = {
                k: state[k]
                for k in ["phase", "development_progress", "test_progress", "last_error"]
                if k in state
            }
            if summary != previous:
                print(json.dumps(summary), flush=True)
                previous = summary
            if not args.watch or state["phase"] not in {
                "waiting_for_development",
                "waiting_for_heldout",
                "waiting_for_comparisons",
                "waiting_for_exports",
                "waiting_for_api",
            }:
                break
            time.sleep(30)


if __name__ == "__main__":
    main()
