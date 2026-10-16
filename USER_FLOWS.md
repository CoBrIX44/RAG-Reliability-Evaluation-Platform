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


## Implemented paired comparison workflow
Comparisons → choose baseline/candidate saved runs and explicit human/model assessment source → choose strict or explicit exploratory mode and bounded seed/resamples → submit frozen analysis → follow durable state → inspect controls, coverage, paired question means, exclusions and available group-bootstrap intervals → inspect timing/known usage/unavailable cost → reopen saved deep link or download frozen inputs. A later review needs a new comparison to enter the report. Charts/topic filters/full exports remain M6. No research winner is inferred automatically.

## M6 comparison, diagnosis and export journey
1. Open /comparisons, select saved baseline/candidate and assessment source, then optionally choose topic/difficulty. Create a new frozen report; inspect differences, interval availability, coverage and selected latency alongside full-run accounting.
2. Open a saved run, choose Open failure explorer (/runs/{runId}/failures), select source/topic/difficulty/issue, then follow the exact /runs/{runId}/results/{resultId} trace to retrieved/delivered/gold canonical evidence.
3. On a terminal run/report, create an evidence ZIP, wait for the durable job and download. Reloading rediscovers the retained job; failure allows a new submission with its own key.
4. Open /demo without a running API, choose complete-context or context-loss synthetic scenarios and inspect canonical fixture evidence. No run/review submission or model inference occurs.
