# Third-party notices

Original project code is licensed under [Apache-2.0](LICENSE). That license does not relicense dependencies, model weights, source documents, fonts, or third-party material quoted in research records. Preserve upstream notices when redistributing those materials.

This inventory was reviewed on 2026-10-20 against the installed packages, lockfiles, and pinned model metadata. It is a source-release inventory, not an exhaustive license inventory of every transitive dependency or a binary/container redistribution checklist. `package-lock.json` and `uv.lock` record the complete resolved dependency graphs.

## Frontend dependencies

| Package | Pinned version | Upstream license |
|---|---|---|
| Next.js | 16.4.0 | MIT |
| React / React DOM | 19.3.0 | MIT |
| SWR | 2.5.1 | MIT |
| Zod | 4.6.6 | MIT |
| Lenis | 1.3.27 | [MIT](https://github.com/darkroomengineering/lenis/blob/main/LICENSE) |
| GSAP | 3.15.0 | [GSAP Standard No Charge License](https://gsap.com/community/standard-license/) |

GSAP is a separately licensed dependency, **not MIT or Apache-2.0**. Its terms include use restrictions; do not represent the complete dependency stack as exclusively OSI-licensed software. It is used here for interface animation, not an animation-authoring product. Keep its proprietary copyright/license headers intact in generated bundles. The application dependency is retained as explicitly requested by the owner.

## Python dependencies

The following licenses are declared by installed distribution metadata for the locked versions:

| Package | Version | Declared license |
|---|---|---|
| FastAPI | 0.143.0 | MIT |
| Uvicorn | 0.54.0 | BSD-3-Clause |
| pydantic-settings | 2.15.0 | MIT |
| SQLAlchemy | 2.1.4 | MIT |
| psycopg / psycopg-binary | 3.3.6 | LGPL-3.0-only |
| pypdf | 6.20.0 | BSD-3-Clause |
| Beautiful Soup | 4.15.0 | MIT |
| markdown-it-py | 4.2.0 | MIT; includes markdown-it notices |
| tokenizers | 0.23.3 | Apache-2.0 |
| huggingface-hub | 1.33.0 | Apache-2.0 |
| sentence-transformers | 6.1.0 | Apache-2.0; upstream NOTICE included in distribution |
| transformers | 5.19.0 | Apache-2.0 |
| torch | 2.14.1+cpu | Apache-2.0, Apache-2.0 WITH LLVM-exception, BSD-2-Clause, BSD-3-Clause, BSL-1.0, MIT (bundled components) |
| Alembic | 1.20.0 | MIT |
| python-multipart | 0.0.32 | Apache-2.0 |

These packages are installed by the package manager, not checked into this repository. Retain their distribution license/NOTICE files when packaging images or executables. Psycopg and its binary distribution remain under LGPL terms; the project's Apache license does not replace those obligations. See the [upstream Psycopg license](https://www.psycopg.org/psycopg3/docs/basic/install.html#binary-installation) and the installed distribution's `LICENSE.txt` before redistributing a binary image. PostgreSQL and pgvector container components also retain their upstream licenses.

## Bundled fonts

Instrument Serif, Ostrich Sans, IBM Plex Mono, and the retained historical Outfit assets are bundled under their respective SIL Open Font License 1.1 notices. Exact sources and hashes are in [the font directory](apps/web/src/app/fonts/README.md), `sources.json`, and `landing-sources.json`. Keep all four `*-OFL.txt` notices when distributing these assets. Reserved font names and modified-font rules remain governed by those notices.

## Downloaded models

Model weights are **not distributed in this repository**. Runtime downloads use pinned revisions; model-card metadata at each listed revision declares Apache-2.0:

| Purpose | Model | Revision |
|---|---|---|
| Embeddings and lexical chunk tokenizer | [all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) | `1110a243fdf4706b3f48f1d95db1a4f5529b4d41` |
| Answer generation / optional uncalibrated self-judge | [Qwen2.5-0.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct) | `7ae557604adf67be50417f59c2c2f167def9a775` |
| Reranking | [ms-marco-MiniLM-L6-v2](https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2) | `233902d25c440f23af6f7d6e94d2946bac0bee0a` |

Keep each model's license and notices if independently redistributing its weights. Other model variants may have different licenses; these entries do not authorize arbitrary replacements.

## Research documents and annotations

PostgreSQL documentation and quotations remain subject to the preserved [PostgreSQL license](research/postgresql-18.0/LICENSE.postgresql.txt). Source acquisition and exclusions are documented in [the benchmark README](research/postgresql-18.0/README.md). Original project-authored annotation text and examples fall under the project license; quoted source portions retain their source license. No standalone dataset license overrides those source notices.

Public preparation records include authored candidates; they are not a replacement for the final frozen, corrected dataset. Do not import historical candidates over reviewed snapshots. The report discloses 10 human / 140 AI gold source reviews and unvalidated generated-answer quality. Private uploads, live databases, raw answer-review packs, model caches, runtime configuration and full backups remain excluded from Git and release assets.
