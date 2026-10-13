# User flows

## Prepare a corpus
Create corpus → upload documents → inspect ingestion progress → inspect normalized sections and source locations → resolve failed documents → publish an immutable corpus version.
Uploads stay in a mutable draft until publication. Later changes create a new version. Scanned PDFs receive an explicit unsupported-content error.

## Curate a dataset
Choose corpus version → create/import questions → record answerability, reference answer, required facts, and evidence → review annotations → assign development/test split → publish dataset version. Imports validate all lines and return line-specific errors before committing a version.

## Run an experiment
Choose published corpus/dataset → choose retrieval, chunking, models, prompt, and budget → validate compatibility → view cost estimate or unavailable estimate → submit → follow progress → cancel or inspect final results.
Model configuration remains server-side. A run request returns a job identifier promptly; browser closure does not cancel execution.

## Compare
Select completed runs → see compatibility differences → review quality, coverage, latency, and cost → filter topic/difficulty → inspect paired question results → export.
Partial runs are inspectable but excluded from headline research comparisons by default. An exploratory override shows a persistent warning and paired sample count.

## Investigate a failure
Open question → read gold answer/evidence → inspect ranked retrieval and delivered context → compare generated answer and citations → inspect evaluator rationale or execution error → record human review.

## Empty and degraded states
No corpus: offer upload. No dataset: offer creation/import. No runs: offer configuration. No provider: explain configuration requirement. Failed request: retry with preserved input. Lost connection: keep last known data and label it stale. Bundled demo is read-only and explicitly labeled.
