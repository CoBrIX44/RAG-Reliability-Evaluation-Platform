# Source release checklist

M7 is delivered under the exploratory scope. Source-release readiness is a separate task; nothing here implies a public deployment, Git push, or published release.

- [x] Owner selected Apache-2.0 for original project code; root LICENSE and NOTICE added.
- [x] Third-party license inventory distinguishes GSAP, LGPL dependencies, fonts, model revisions, and PostgreSQL source quotations.
- [x] Local tracked-file / history scan completed with no credential-pattern or forbidden private-path findings (bounded scope below).
- [x] Publishable documentation keeps 10 human / 140 AI source-review provenance and unavailable answer-quality/cost limitations.
- [x] Beginner demo / new-workspace guide and one-question development fixture supplied.
- [x] Final current-tree check including new release files and fresh-checkout frontend verification recorded below.
- [ ] Owner commits reviewed release changes and pushes; newest GitHub workflow passes.
- [ ] Verify fresh full-workspace setup and the documented one-question model experiment independently of the private M7 environment.
- [ ] Review package-specific obligations before distributing compiled binaries, Docker images or model weights; source notices are not that binary audit.
- [ ] Prepare version/tag/release notes and approve publication. No release has been published by this audit.

## Audit boundaries

The 2026-10-20 local scan examined 252 tracked files and 409 historical text blobs across nine local commits/refs. It checked common credential/private-key token patterns, exact non-placeholder credential values from private `.env` without printing them, and forbidden tracked environment/data/cache/key/backup paths. No findings were reported. Historical text blobs were limited to 2 MiB; this is a heuristic local audit, not a guarantee or inspection of inaccessible remote refs, GitHub attachments, issue content, forks or prior remote caches. Keep GitHub secret scanning enabled if available, and never upload private backups or raw owner data as release attachments.

Untracked release additions need a final current-tree check. All private audit artifacts remain in ignored `artifacts/`; copies of the live configuration, datasets and full backups must never be placed in a public audit report. No history rewrite, remote visibility change, or credential rotation was performed because this audit did not identify exposed credentials.

## Public versus private material

Include original code, specifications, font licenses, PostgreSQL license/provenance, clearly synthetic examples/demo and the honest exploratory report. Keep `.env`, `runtime.env`, database dumps, original uploads, full backups, downloaded weights, owner review receipts and raw generated-answer review packs local. Research candidate JSON files are historical preparation material, not a portable copy of the corrected published snapshot.

For the release notes, link the report rather than attaching the private evidence/backup directories. Describe retrieval results as exploratory; do not claim validated accuracy, independent human validation, controlled warm/cold latency, measured financial cost or a production multi-user security boundary.

## Fresh-checkout verification — 2026-10-20

A separate local clone of commit603c98f was created under ignored data/release-audit/clean-checkout without private configuration, live database, or model caches. `npm ci` succeeded (zero reported npm vulnerabilities at that time), `npm run check` passed, and the production build succeeded. A temporary native server on3003 served that built clone; all four selected landing/demo Chromium checks passed in4.1s, covering native demo behavior with zero API calls, method interaction, navigation, reduced motion, theme/accessibility and mobile layout. These frontend checks do not prove a clean backend/model installation. The temporary audit server was stopped afterward.

The final current-tree scan covered258 tracked/untracked publishable files with no credential-pattern findings; local Markdown links in edited release documents resolved. `.env`, the private runtime.env backup, completion receipt and audit artifacts are ignored by Git. The prior all-local-history scan remains the historical scope described above. License/notices and documentation added after the cloned commit were checked separately; this is not a claim that those uncommitted changes already exist in a remote clone. No public release, push, history rewrite, live backend restart or new inference was performed.
