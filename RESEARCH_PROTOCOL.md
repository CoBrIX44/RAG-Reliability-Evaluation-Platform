# Research protocol

## Hypothesis and scope
Test whether hybrid retrieval and reranking improve reference-fact correctness over dense retrieval on a fixed PostgreSQL technical-document corpus. Report trade-offs in latency, cost, and evidence coverage, including null findings.

## Corpus and dataset
Choose one explicitly numbered PostgreSQL documentation release during corpus setup; never crawl a moving current URL for a benchmark. Record URLs, acquisition date, source license/attribution, file checksums, extraction version, and excluded pages. Do not claim the release has already been selected or acquired.

Begin with 150 human-reviewed questions and expand toward 1,000. Cover SQL behavior, configuration, indexes, transactions, and troubleshooting, with single-passage, multi-passage, and unanswerable cases. Proposed answerability balance: 80% answerable/20% unanswerable. A 30-question smoke fixture is a development aid, not the published benchmark.

Assign 70% development/30% held-out test by topic/source-section groups where feasible; deduplicate paraphrases across splits. Freeze the split before tuning. Do not train/tune on held-out answers. Document coverage gaps and any unavoidable cross-topic source overlap. The platform owner supplies or reviews gold labels; generated candidates never count as reviewed automatically.

## Controlled comparisons
Lexical baseline; dense; hybrid reciprocal-rank fusion; hybrid plus cross-encoder reranker. Lexical retrieval initially uses PostgreSQL full-text ranking, not a claim of BM25. Fixed-token and section-aware chunking share normalized source units. Tune on development only. Vary one factor at a time, then selected combinations. Hold answer model, prompt, corpus, evaluation rubric, and context-token ceiling constant. Record candidate count, top-k, fusion weights, reranker, context packing, chunk tokens/overlap, tokenizer, and truncation.

## Retrieval metric definitions
Gold evidence consists of canonical source spans grouped into required facts with acceptable alternative spans. Deduplicate retrieved coverage by canonical source location. A fact is covered when the union of retrieved spans fully contains every span in at least one accepted alternative for that group. Each alternative may require multiple jointly supporting spans; any complete alternative suffices. The implemented matching policy is canonical-group-union-v1. Persist this exact matching policy and version. Report evidence-group recall@k as covered required groups / total required groups. Report passage precision@k as returned passages covering at least one accepted evidence span / passages actually returned; additionally report returned count. Empty retrieval has precision 0 on applicable answerable cases. Exclude unanswerable cases from positive-evidence precision/recall and report their abstention separately.

Score retrieval before context packing and evidence coverage after packing separately. Chunk precision is sensitive to chunk size; report token budget and evidence-group coverage together and avoid interpreting it as a universally fair cross-chunking winner. Annotations establish known relevant evidence, not exhaustive relevance judgments across the entire corpus.

## Answer metrics
Correctness: required-fact coverage plus contradiction assessment against a versioned rubric. Faithfulness: supported factual claims / evaluable factual claims against delivered context. Citation support: cited claims supported by cited passages; record citation completeness separately. Abstention: appropriate refusal on unanswerable questions plus false abstention on answerable questions. Zero factual claims makes faithfulness undefined, not perfect. These are separate dimensions, never a hidden composite score.

LLM-judged metrics are estimates with model/prompt versions, raw structured rationale, and validation state. Missing judge configuration yields unavailable metrics. Inspect a stratified human-reviewed sample (proposed minimum 30 cases) and report judge/human disagreement; human review is not replaced by automated scores.

## Reliability, timing, and cost
Persist all attempts, stage timings, index-build duration, first-run/warm-cache conditions, provider usage, and explicit pricing snapshot. Report end-to-end and per-stage p50/p95, plus completion rate. Unknown cost is null; pricing-based values are estimates. A crashed call can be billed without known usage; expose that uncertainty.

## Analysis and reproducibility
Primary outcome: paired test-set correctness difference against dense baseline. Report effect sizes and 95% paired bootstrap intervals over question groups, with recorded resampling seed/count; exploratory comparisons are labeled and multiple-comparison limitations disclosed. Stochastic answer/judge repeats (proposed three) are aggregated per question before interval estimation. Confidence intervals describe the evaluated sample/procedure, not all PostgreSQL questions.

Export immutable manifest, hashes, Git revision, dependency locks, provider/model revisions, prompts, evaluator versions, hardware/runtime metadata, per-question results, and exclusions. Hosted inference can change and need not be bitwise deterministic. Never label a partial run as the winner; show planned/applicable/scored/error counts and compute paired summaries only on the disclosed common set.

## References
- Precision/recall foundations: https://nlp.stanford.edu/IR-book/html/htmledition/evaluation-of-unranked-retrieval-sets-1.html
- Separate RAG evaluation dimensions: https://arxiv.org/abs/2309.15217

## Implemented M4 baseline limitations
M4 supplies one explicitly approved free local CPU answer model with greedy decoding. It records exact prompts/artifacts/library/runtime identities, evidence budgets, question-repeat counts, and raw output/timing traces. Context packing uses the answer tokenizer and full prompts exceeding 2048 input tokens fail rather than silently truncate. Shared model preparation and queue time are outside per-question stage times; generation wall time includes hashing/loading. Use run timestamps for the broader execution window. These are software execution traces; controlled first/warm conditions and aggregate p50/p95 analysis remain M5 work.

The one live reviewed transaction fixture belongs to development_fixture and is separate from the future benchmark. Raw generated answers have no automatic quality endorsement. Exact refusal marker and syntactic citations do not score abstention or support; those metrics and cost remain unavailable. Greedy repeats may produce identical answers and must not inflate independent question counts or bootstrap sample size.
