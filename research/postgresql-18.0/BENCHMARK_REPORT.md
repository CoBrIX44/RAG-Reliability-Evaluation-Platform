# PostgreSQL18.0 held-out benchmark report

Generated at 2026-10-20T09:20:51.277215+00:00.

The primary factual-accuracy hypothesis is **not established**: answers lack valid recorded quality assessments. Observed retrieval results do not substitute for answer correctness.

Corpus:40 purposeful PostgreSQL18.0 pages. Dataset:150 reviewed questions (10 human/140 AI gold reviews);105 development/45 test across23 source families, including8 held-out groups. Same-assistant curation and incomplete relevance labels limit validity. All30 negatives concern missing instance data.

Controls:240-token chunks/32 overlap; top-k5; context1024; max output128; local Qwen0.5B; three repeats per held-out question. Repeats average per question before whole-group bootstrap and are not independent samples. Cache/shared-host timing are uncontrolled. Local energy and financial cost are unavailable.

| Cell | State | Succeeded/planned | Failed | Recall % | Scored/applicable |
|---|---|---:|---:|---:|---:|
| fixed/dense | completed | 135/135 | 0 | 82.35 | 102/102 |
| fixed/hybrid | completed | 135/135 | 0 | 85.29 | 102/102 |
| fixed/hybrid_rerank | completed | 135/135 | 0 | 94.12 | 102/102 |
| fixed/lexical | completed | 135/135 | 0 | 14.71 | 102/102 |
| section/dense | completed | 135/135 | 0 | 92.16 | 102/102 |
| section/hybrid | completed | 135/135 | 0 | 92.16 | 102/102 |
| section/hybrid_rerank | completed | 135/135 | 0 | 97.06 | 102/102 |
| section/lexical | completed | 135/135 | 0 | 14.71 | 102/102 |

## Frozen paired reports

Comparisons are explicitly exploratory. Missing answer scores stay unavailable. Index/chunking differences and other control exclusions remain in the saved reports. Effects and intervals below are percentage points, candidate minus baseline; multiple comparisons are unadjusted.

### section/dense vs section/hybrid_rerank

[Saved comparison](http://localhost:3000/comparisons/44485f55-6ef6-4588-83ae-6fcee1316fec) · completed

| Metric | Delta pp | 95% interval pp | Paired questions/groups | Excluded |
|---|---:|---|---:|---:|
| faithfulness | unavailable | unavailable | 0/0 | 45 |
| context_recall | 4.90 | 0.00 to 10.83 | 34/8 | 11 |
| citation_support | unavailable | unavailable | 0/0 | 45 |
| retrieval_recall | 4.90 | 0.00 to 10.83 | 34/8 | 11 |
| abstention_quality | unavailable | unavailable | 0/0 | 45 |
| answer_correctness | unavailable | unavailable | 0/0 | 45 |
| retrieval_precision | 1.18 | 0.00 to 2.50 | 34/8 | 11 |

### section/dense vs section/hybrid

[Saved comparison](http://localhost:3000/comparisons/651ab5cf-94ed-4f19-9c41-fb8056ca3c3d) · completed

| Metric | Delta pp | 95% interval pp | Paired questions/groups | Excluded |
|---|---:|---|---:|---:|
| faithfulness | unavailable | unavailable | 0/0 | 45 |
| context_recall | 0.00 | 0.00 to 0.00 | 34/8 | 11 |
| citation_support | unavailable | unavailable | 0/0 | 45 |
| retrieval_recall | 0.00 | 0.00 to 0.00 | 34/8 | 11 |
| abstention_quality | unavailable | unavailable | 0/0 | 45 |
| answer_correctness | unavailable | unavailable | 0/0 | 45 |
| retrieval_precision | 0.00 | 0.00 to 0.00 | 34/8 | 11 |

### fixed/lexical vs fixed/dense

[Saved comparison](http://localhost:3000/comparisons/c5c3861e-2d55-4265-8622-c6964dc6a56d) · completed

| Metric | Delta pp | 95% interval pp | Paired questions/groups | Excluded |
|---|---:|---|---:|---:|
| faithfulness | unavailable | unavailable | 0/0 | 45 |
| context_recall | 63.73 | 48.33 to 79.17 | 34/8 | 11 |
| citation_support | unavailable | unavailable | 0/0 | 45 |
| retrieval_recall | 67.65 | 50.00 to 84.38 | 34/8 | 11 |
| abstention_quality | unavailable | unavailable | 0/0 | 45 |
| answer_correctness | unavailable | unavailable | 0/0 | 45 |
| retrieval_precision | 0.59 | -11.58 to 11.18 | 34/8 | 11 |

### section/lexical vs section/dense

[Saved comparison](http://localhost:3000/comparisons/a30451cc-440d-48b1-8225-14ada8f946ba) · completed

| Metric | Delta pp | 95% interval pp | Paired questions/groups | Excluded |
|---|---:|---|---:|---:|
| faithfulness | unavailable | unavailable | 0/0 | 45 |
| context_recall | 77.45 | 68.25 to 89.48 | 34/8 | 11 |
| citation_support | unavailable | unavailable | 0/0 | 45 |
| retrieval_recall | 77.45 | 68.25 to 89.48 | 34/8 | 11 |
| abstention_quality | unavailable | unavailable | 0/0 | 45 |
| answer_correctness | unavailable | unavailable | 0/0 | 45 |
| retrieval_precision | 4.71 | -7.27 to 15.72 | 34/8 | 11 |

### fixed/lexical vs section/lexical

[Saved comparison](http://localhost:3000/comparisons/a9c8a00b-f2a2-42ed-85bf-7b5a3e412077) · completed

| Metric | Delta pp | 95% interval pp | Paired questions/groups | Excluded |
|---|---:|---|---:|---:|
| faithfulness | unavailable | unavailable | 0/0 | 45 |
| context_recall | 0.00 | 0.00 to 0.00 | 34/8 | 11 |
| citation_support | unavailable | unavailable | 0/0 | 45 |
| retrieval_recall | 0.00 | 0.00 to 0.00 | 34/8 | 11 |
| abstention_quality | unavailable | unavailable | 0/0 | 45 |
| answer_correctness | unavailable | unavailable | 0/0 | 45 |
| retrieval_precision | 0.00 | 0.00 to 0.00 | 34/8 | 11 |

### fixed/dense vs section/dense

[Saved comparison](http://localhost:3000/comparisons/bcd3cd1d-f251-4ead-a805-6cc69f9b2dd3) · completed

| Metric | Delta pp | 95% interval pp | Paired questions/groups | Excluded |
|---|---:|---|---:|---:|
| faithfulness | unavailable | unavailable | 0/0 | 45 |
| context_recall | 13.73 | 0.95 to 26.88 | 34/8 | 11 |
| citation_support | unavailable | unavailable | 0/0 | 45 |
| retrieval_recall | 9.80 | -3.03 to 25.81 | 34/8 | 11 |
| abstention_quality | unavailable | unavailable | 0/0 | 45 |
| answer_correctness | unavailable | unavailable | 0/0 | 45 |
| retrieval_precision | 4.12 | 2.29 to 6.21 | 34/8 | 11 |

### fixed/hybrid vs section/hybrid

[Saved comparison](http://localhost:3000/comparisons/197fb1f1-c2d3-4284-a64f-ca7d871c659a) · completed

| Metric | Delta pp | 95% interval pp | Paired questions/groups | Excluded |
|---|---:|---|---:|---:|
| faithfulness | unavailable | unavailable | 0/0 | 45 |
| context_recall | 10.78 | -0.00 to 23.33 | 34/8 | 11 |
| citation_support | unavailable | unavailable | 0/0 | 45 |
| retrieval_recall | 6.86 | -3.03 to 20.84 | 34/8 | 11 |
| abstention_quality | unavailable | unavailable | 0/0 | 45 |
| answer_correctness | unavailable | unavailable | 0/0 | 45 |
| retrieval_precision | 4.12 | 2.29 to 6.21 | 34/8 | 11 |

### fixed/hybrid_rerank vs section/hybrid_rerank

[Saved comparison](http://localhost:3000/comparisons/cc935e55-437c-4bf3-9b32-080420e7629e) · completed

| Metric | Delta pp | 95% interval pp | Paired questions/groups | Excluded |
|---|---:|---|---:|---:|
| faithfulness | unavailable | unavailable | 0/0 | 45 |
| context_recall | 5.88 | 0.00 to 11.77 | 34/8 | 11 |
| citation_support | unavailable | unavailable | 0/0 | 45 |
| retrieval_recall | 2.94 | 0.00 to 8.57 | 34/8 | 11 |
| abstention_quality | unavailable | unavailable | 0/0 | 45 |
| answer_correctness | unavailable | unavailable | 0/0 | 45 |
| retrieval_precision | 3.53 | 1.82 to 4.89 | 34/8 | 11 |

## Observed timing and accounting

No subgroup filters were applied. Timing below uses saved full-run observation samples, not independent question means or a controlled hardware comparison. Question timers exclude queue/shared preparation and include per-call model hashing/loading. Run windows can include recovery gaps. See HARDWARE.md for the observed host and resource limits.

| Run | Stage | p50 seconds | p95 seconds | Measured/unavailable |
|---|---|---:|---:|---:|
| a7a16262-30f0-4d3d-9a89-c97e8c349f5a | question_wall_ms | 31.89 | 41.28 | 135/0 |
| a7a16262-30f0-4d3d-9a89-c97e8c349f5a | retrieval_wall_ms | 11.95 | 12.95 | 135/0 |
| a7a16262-30f0-4d3d-9a89-c97e8c349f5a | generation_wall_ms | 20.44 | 28.98 | 135/0 |
| 370f9de9-63d3-4e20-874e-8c9d695a8d79 | question_wall_ms | 33.00 | 38.64 | 135/0 |
| 370f9de9-63d3-4e20-874e-8c9d695a8d79 | retrieval_wall_ms | 16.47 | 16.90 | 135/0 |
| 370f9de9-63d3-4e20-874e-8c9d695a8d79 | generation_wall_ms | 16.32 | 21.89 | 135/0 |
| 370f9de9-63d3-4e20-874e-8c9d695a8d79 | pipeline_fusion_wall_ms | 0.00 | 0.00 | 135/0 |
| 370f9de9-63d3-4e20-874e-8c9d695a8d79 | pipeline_lexical_wall_ms | 0.01 | 0.01 | 135/0 |
| 370f9de9-63d3-4e20-874e-8c9d695a8d79 | pipeline_reranking_wall_ms | 8.11 | 8.41 | 135/0 |
| 370f9de9-63d3-4e20-874e-8c9d695a8d79 | pipeline_dense_search_wall_ms | 0.02 | 0.02 | 135/0 |
| 370f9de9-63d3-4e20-874e-8c9d695a8d79 | pipeline_query_embedding_wall_ms | 8.31 | 8.51 | 135/0 |
| b2b13ac5-5cb8-4870-ad74-159fb37aa53e | question_wall_ms | 27.89 | 38.19 | 135/0 |
| b2b13ac5-5cb8-4870-ad74-159fb37aa53e | retrieval_wall_ms | 9.45 | 12.67 | 135/0 |
| b2b13ac5-5cb8-4870-ad74-159fb37aa53e | generation_wall_ms | 18.53 | 27.34 | 135/0 |
| b2b13ac5-5cb8-4870-ad74-159fb37aa53e | pipeline_fusion_wall_ms | 0.00 | 0.00 | 135/0 |
| b2b13ac5-5cb8-4870-ad74-159fb37aa53e | pipeline_lexical_wall_ms | 0.01 | 0.02 | 135/0 |
| b2b13ac5-5cb8-4870-ad74-159fb37aa53e | pipeline_dense_search_wall_ms | 0.02 | 0.03 | 135/0 |
| b2b13ac5-5cb8-4870-ad74-159fb37aa53e | pipeline_query_embedding_wall_ms | 9.42 | 12.62 | 135/0 |
| ca66241c-ee2b-4956-a6af-d8252a789351 | question_wall_ms | 14.95 | 19.94 | 135/0 |
| ca66241c-ee2b-4956-a6af-d8252a789351 | retrieval_wall_ms | 0.02 | 0.02 | 135/0 |
| ca66241c-ee2b-4956-a6af-d8252a789351 | generation_wall_ms | 14.93 | 19.92 | 135/0 |
| 0781a58d-09e5-473b-8b1d-7c775507d4ab | question_wall_ms | 29.07 | 33.87 | 135/0 |
| 0781a58d-09e5-473b-8b1d-7c775507d4ab | retrieval_wall_ms | 8.73 | 9.53 | 135/0 |
| 0781a58d-09e5-473b-8b1d-7c775507d4ab | generation_wall_ms | 20.23 | 24.94 | 135/0 |
| 27cbf0cb-4a14-44ed-947c-2cd0a6913723 | question_wall_ms | 15.95 | 20.89 | 135/0 |
| 27cbf0cb-4a14-44ed-947c-2cd0a6913723 | retrieval_wall_ms | 0.02 | 0.02 | 135/0 |
| 27cbf0cb-4a14-44ed-947c-2cd0a6913723 | generation_wall_ms | 15.93 | 20.87 | 135/0 |
| 8c123798-3b39-4c52-be63-74b81910706d | question_wall_ms | 30.09 | 42.22 | 135/0 |
| 8c123798-3b39-4c52-be63-74b81910706d | retrieval_wall_ms | 8.75 | 12.51 | 135/0 |
| 8c123798-3b39-4c52-be63-74b81910706d | generation_wall_ms | 20.94 | 29.87 | 135/0 |
| 8c123798-3b39-4c52-be63-74b81910706d | pipeline_fusion_wall_ms | 0.00 | 0.00 | 135/0 |
| 8c123798-3b39-4c52-be63-74b81910706d | pipeline_lexical_wall_ms | 0.01 | 0.02 | 135/0 |
| 8c123798-3b39-4c52-be63-74b81910706d | pipeline_dense_search_wall_ms | 0.02 | 0.03 | 135/0 |
| 8c123798-3b39-4c52-be63-74b81910706d | pipeline_query_embedding_wall_ms | 8.71 | 12.45 | 135/0 |
| 70f96ac9-5739-49ba-8196-eeba2a84c8ad | question_wall_ms | 46.32 | 57.43 | 135/0 |
| 70f96ac9-5739-49ba-8196-eeba2a84c8ad | retrieval_wall_ms | 22.19 | 26.06 | 135/0 |
| 70f96ac9-5739-49ba-8196-eeba2a84c8ad | generation_wall_ms | 22.83 | 32.41 | 135/0 |
| 70f96ac9-5739-49ba-8196-eeba2a84c8ad | pipeline_fusion_wall_ms | 0.00 | 0.00 | 135/0 |
| 70f96ac9-5739-49ba-8196-eeba2a84c8ad | pipeline_lexical_wall_ms | 0.02 | 0.02 | 135/0 |
| 70f96ac9-5739-49ba-8196-eeba2a84c8ad | pipeline_reranking_wall_ms | 11.02 | 12.96 | 135/0 |
| 70f96ac9-5739-49ba-8196-eeba2a84c8ad | pipeline_dense_search_wall_ms | 0.02 | 0.03 | 135/0 |
| 70f96ac9-5739-49ba-8196-eeba2a84c8ad | pipeline_query_embedding_wall_ms | 11.32 | 13.32 | 135/0 |

Attempt counts, generation/judge token ledgers, unknown usage, queue/run windows and index-build measurements remain in each frozen report's accounting object and checked evidence ZIP. Local financial/energy cost remains unavailable rather than zero.

## Unvalidated answer quality

The local answer-review-pack.json contains up to30 real, unreviewed cases from15 question IDs, balanced across topics and both primary methods. Reviewers/judgments remain blank. This is not a human validation sample or calibrated model score. The owner selected exploratory delivery with answer quality unvalidated. Valid assessments are still needed for future factual-accuracy claims. New judgments require new explicitly frozen analyses; saved reports never backfill them.

## Evidence and recovery

Worker evidence ZIPs are checked against outer and per-entry SHA-256 values. Full inputs, controller receipts and frozen configuration stay under private data/. See completion/delivery.json for actual post-experiment backup status. Same-machine restore does not prove offsite recovery or historical bitwise inference replay.
