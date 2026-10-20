# Transactions — synthetic development fixture

This short document is authored for testing the platform's ingestion and evaluation workflow. It is not an excerpt from the research corpus and is not a measured benchmark.

## Transaction grouping

A transaction groups operations into a single unit.

In this fixture, BEGIN starts a transaction and COMMIT ends it. The following SQL is illustrative source text; uploading the document does not execute it.

```sql
BEGIN;
SELECT 1;
COMMIT;
```
