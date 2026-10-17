# Development execution inspection

Observed at 2026-10-17T10:14:58.190559+00:00. Development split only; the other six cells are unfinished. These are descriptive diagnostics, not a held-out finding or answer-quality assessment.

| Completed cell | Successful/planned | Retrieval recall | Delivered-context recall | Scored/applicable |
|---|---:|---:|---:|---:|
| fixed/lexical | 105/105 | 13.95% | 13.95% | 86/86 |
| section/dense | 105/105 | 87.79% | 87.79% | 86/86 |

Both runs scored all86 answerable development questions;19 unanswerable cases have no positive-evidence denominator. Recall uses canonical-group-union-v1 against known annotated evidence, not exhaustive relevance judgments. These two cells change both chunking and retrieval method, so their difference does not isolate either factor. No winner or accuracy improvement is established.

A deterministic ID-based inspection retained15 real traces per completed cell: three questions per topic, including one negative where available. All30 sampled answers omit parsed inline citations and the exact abstention marker; one section/dense sample reached the128-token ceiling. These are formatting/execution diagnostics, not proof of unsupported claims, incorrectness or semantic refusal quality. Full prompts, answers, delivered evidence and trace digests remain in the private development-inspection-20261017.json receipt.

No reviewer or judgment has been recorded for these30 cases. Correctness, faithfulness, citation support, abstention quality and cost remain unavailable. Existing gold source reviews do not assess generated answers.

Docker recovery resumed the existing fixed/dense run without replacing terminal runs. The API/worker retain source hash1123f6e613ba27ca7a9b1a97bbabe3159d6d074e1d101c8db8fbff041cda0f5e. Shared-host/cache timing remains uncontrolled. Qualification must still complete all840 development observations before controls freeze and held-out submission.
