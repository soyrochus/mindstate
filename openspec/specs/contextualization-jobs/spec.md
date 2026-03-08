## Purpose
Define job-based graph contextualization triggering and status tracking.

## Requirements

### Requirement: `contextualize(n)` selects the n most recent non-contextualized items
The `contextualize(n)` operation SHALL select the `n` most recent `memory_items` where `contextualized_at IS NULL AND contextualization_skipped = FALSE`, ordered by `created_at DESC`. It SHALL enqueue a single `memory_contextualization_jobs` row covering all selected `memory_ids` and return a job reference immediately. Default `n` is 1.

#### Scenario: Default n=1 selects most recent eligible item
- **WHEN** `contextualize()` is called with no arguments and at least one non-contextualized item exists
- **THEN** exactly one item is selected (the most recently created non-contextualized item) and a job is enqueued

#### Scenario: n > available items processes all eligible
- **WHEN** `contextualize(n=10)` is called but only 3 eligible items exist
- **THEN** all 3 are selected and one job is created with `memory_ids` containing all 3

#### Scenario: No eligible items returns empty job
- **WHEN** `contextualize(n=5)` is called but all items have `contextualized_at IS NOT NULL` or `contextualization_skipped = TRUE`
- **THEN** a job response is returned with `queued_count = 0` and no job row is created

### Requirement: `contextualize(ids=[...])` targets specific items by UUID
The `contextualize(ids=[...])` operation SHALL accept a list of memory UUIDs and enqueue a contextualization job for those specific items, regardless of their current `contextualized_at` status. This allows forced re-contextualization and precise agent targeting.

#### Scenario: Specific IDs enqueued
- **WHEN** `contextualize(ids=["<uuid1>", "<uuid2>"])` is called
- **THEN** a job is created with `memory_ids = [uuid1, uuid2]` and `queued_count = 2`

#### Scenario: Already-contextualized items can be re-targeted
- **WHEN** `contextualize(ids=["<uuid>"])` is called for an item where `contextualized_at IS NOT NULL`
- **THEN** the item is re-processed; on completion `contextualized_at` is updated to the new timestamp

### Requirement: Job status lifecycle is queued → running → done | failed
A `memory_contextualization_jobs` row SHALL transition through statuses: `queued` (on creation), `running` (when the background thread begins processing), `done` (all items processed without error), `failed` (unrecoverable error). `started_at` is set on transition to `running`; `completed_at` is set on transition to `done` or `failed`.

#### Scenario: New job starts as queued
- **WHEN** `contextualize(n=1)` is called
- **THEN** the returned job has `status = "queued"` and `started_at = NULL`

#### Scenario: Job transitions to running
- **WHEN** the background thread picks up the job
- **THEN** the job row is updated to `status = "running"` and `started_at = NOW()`

#### Scenario: Completed job is marked done
- **WHEN** all items in the job have been processed without error
- **THEN** `status = "done"`, `completed_at = NOW()`, and `result` contains a summary JSON

#### Scenario: Job with processing error is marked failed
- **WHEN** an unrecoverable error occurs during processing
- **THEN** `status = "failed"`, `error` contains the error message, and `completed_at = NOW()`

### Requirement: Job status is pollable via HTTP
`GET /v1/memory/contextualize/{job_id}` SHALL return the current job status including `job_id`, `status`, `queued_count`, `started_at`, `completed_at`, and `result` (when done).

#### Scenario: Poll pending job
- **WHEN** `GET /v1/memory/contextualize/{job_id}` is called before the job completes
- **THEN** response includes `status = "queued"` or `"running"` and `completed_at = null`

#### Scenario: Poll completed job
- **WHEN** `GET /v1/memory/contextualize/{job_id}` is called after the job completes
- **THEN** response includes `status = "done"`, `completed_at` timestamp, and result summary

#### Scenario: Unknown job ID returns 404
- **WHEN** `GET /v1/memory/contextualize/{job_id}` is called with a non-existent UUID
- **THEN** HTTP 404 is returned

### Requirement: `POST /v1/memory/contextualize` accepts n-mode and ids-mode
The HTTP endpoint SHALL accept a JSON body with either `{"n": int}` or `{"ids": [str]}`. Both modes SHALL return `{"job_id": str, "queued_count": int, "status": "queued"}` immediately. The endpoint SHALL validate that exactly one of `n` or `ids` is provided.

#### Scenario: n-mode request
- **WHEN** `POST /v1/memory/contextualize` is called with `{"n": 3}`
- **THEN** a job is created and the response includes `job_id`, `queued_count` (≤ 3), and `status = "queued"`

#### Scenario: ids-mode request
- **WHEN** `POST /v1/memory/contextualize` is called with `{"ids": ["<uuid>"]}`
- **THEN** a job is created for that specific item and the response includes `job_id`, `queued_count = 1`, `status = "queued"`

#### Scenario: Neither n nor ids provided returns 422
- **WHEN** `POST /v1/memory/contextualize` is called with an empty body
- **THEN** HTTP 422 is returned

### Requirement: Failed items remain retry-eligible
Items that fail during contextualization (LLM error, AGE write failure) SHALL have `contextualized_at` left as NULL after the job completes. Running `contextualize(n)` again SHALL re-select these items for retry.

#### Scenario: Retry picks up previously failed item
- **WHEN** a contextualization job fails for an item and `contextualize(n=1)` is called again
- **THEN** the same item is selected again (it has `contextualized_at IS NULL`) and a new job is created

#### Scenario: Skipped items not retried
- **WHEN** `contextualization_skipped = TRUE` for an item
- **THEN** `contextualize(n)` does not select it regardless of `contextualized_at` value