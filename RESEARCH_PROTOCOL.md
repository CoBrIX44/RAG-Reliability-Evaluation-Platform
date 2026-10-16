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


## Implemented answer-evidence-v1 rubric
Post-hoc evaluation records freeze the complete rubric and inputs independently of original run results. Correctness is required-fact coverage with any contradicted required fact forcing zero; no positive denominator for unanswerable questions. Faithfulness scores supported quoted answer claims against delivered evidence only; uncertain support receives no credit. Citation support scores factual claims with supporting valid inline citations against all factual claims, so missing/unknown/unsupported references receive zero. Exact abstentions/no factual claims have no faithfulness/citation denominator. Abstention quality here is binary exact INSUFFICIENT_EVIDENCE decision accuracy against frozen answerability, not semantic refusal detection. These operational definitions and reviewer claim segmentation limit interpretation.

Human fact/claim judgments, reviewer label and rationale are explicit new submissions; prior gold review is not answer approval. The optional local Qwen 0.5B judge is an uncalibrated self-judge baseline using the same model family as the generator. Record that dependence, raw prompt/output, token usage and strict validation state. Its actual development smoke failed the structured rubric; no quality score is inferred. Evaluate calibration/disagreement on a genuinely human-reviewed sample before research use. Never fabricate that sample or tune on test labels.

Coverage selects the latest record per answer/source, including pending/failed records. Keep human/model results separate, disclose missing applicability when claim decomposition is unavailable, and show paired available-value disagreement counts/exclusions. Observation means are descriptive; paired retrieval-strategy bootstrap analysis still aggregates repeats by question/group and is the next M5 task. Local CPU monetary/energy cost remains unavailable.


## Implemented paired-question-cluster-bootstrap-v1
Freeze both run and latest explicit-source evaluation selections before analysis. Average all planned repeats of each question; missing repeats or unavailable/errored metrics exclude that question. Pair only identical question revision/content/split-group definitions with matching scoring policy. Report coverage/exclusions and retain the frozen evaluation IDs; later reviews create a new analysis snapshot. Default strict inference blocks differing controlled inputs, partial runs or incomplete scoring. Exploratory overrides stay labeled, retain common complete question pairs and do not combine mismatched scoring policies. A mixed rubric/model policy across paired questions blocks one shared interval.

For each available metric, estimate the equally weighted mean paired question delta (candidate minus baseline). Sample split_group clusters with replacement, retaining every question delta in each sampled cluster, then recompute the question-weighted mean. Percentile95% endpoints use linear interpolation at (n-1)*p with recorded Python runtime, Random seed and resample count. Fewer than two independent groups yields no interval. More than one group is only a software minimum, not assurance of adequate research power. Multiple metrics remain exploratory and unadjusted. Development fixtures and singleton summaries cannot establish factual-accuracy improvements.

Timing summaries are available observed sample p50/p95 with measured/missing counts, not portable latency guarantees. Run windows include preparation/recovery; final question timers exclude shared preparation/queue but include per-call model hashing/loading. Operator cold/warm cache declarations require notes and are not automatically verified. Use a documented controlled acquisition protocol and reference hardware for the eventual benchmark. Attempt generation usage is counted once; all recorded judge calls, including invalid structured output, are disclosed. Interrupted/failed-call usage can remain unknown. Local CPU energy/hardware/pricing is unmeasured; cost remains unavailable. Actual controlled research executions and human benchmark labels remain M7 work.

## Implemented subgroup analysis and diagnostics (M6)
Analysis version paired-question-cluster-bootstrap-v2 freezes sorted topic/difficulty selections and filters both run question universes and observations before computing question means, exclusions and group bootstrap. Changing filters creates a new immutable comparison. Old v1 reports remain readable. Singleton groups still have no interval; unavailable answer scores remain unavailable. Do not choose a winning subgroup after inspecting held-out results without disclosing exploratory selection.

Selected question stage timings are recomputed with explicit measured/unavailable counts. Attempt usage, run windows and full-run accounting remain separate and labeled, including observations outside the subgroup. Charts supplement the coverage tables and never plot missing values as zero. Failure categories describe retrieval/context/execution/assessment signals; citation syntax and missing review alone do not establish factual error. The offline demo is synthetic and cannot supply benchmark labels or results.
