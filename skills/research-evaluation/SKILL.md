---
name: rag-platform-research-evaluation
description: Implement evidence-grounded metrics and controlled RAG comparisons.
---

Read RESEARCH_PROTOCOL.md, DATASET_CARD.md, DATA_MODEL.md, and ACCEPTANCE_TESTS.md. Use published corpus/dataset versions and retain evaluator/model/prompt revisions.

Gold evidence uses canonical source spans and required-fact groups with alternatives. Deduplicate coverage. Persist pre-packing retrieval and delivered context separately. Keep correctness, faithfulness, citation support, and abstention separate. Handle undefined metrics explicitly.

Use independent hand-computed fixtures. Do not call a judged metric objective truth or a partial comparison a research winner. Aggregate repeated generations by question before paired statistics. Test-set labels are not tuning inputs. Record exclusions and judge/human disagreement.

Research artifacts contain actual outputs, provenance, manifests, sample counts, and limitations. Candidate questions require human review before benchmark publication.
