# Prospective collection, freezing, and scoring

Status: implemented. Historical availability remains unknown and historical rules
are unchanged. This adds a separate protocol for actual live predictions.

## Evidence semantics

`received_at` is our receipt of source bytes, not their publication date.
`ingested_at` is application processing time. Conservative `available_at` in
datasets is the later timestamp; forecasts only read committed observations.
These are local observation semantics, not independently certified source timing.
Keep collector/database clocks synchronized. Scheduled time remains a proxy for
start; earlier corrected starts and already observed results disqualify scoring.

Raw bytes are saved before HTML parsing. An immutable retrieval receipt contains
URL, HTTP status, receipt time, hash, source, and capture version. Parse receipts
link to retrievals and record parser version, entity, time, and success/failure.
An observation links normalized match/team IDs, VLR identities/names, raw hash,
parse receipt, and listing evidence (the source of event/stage). Player/stat raw
capture remains supported, but player/roster inputs are not consumed by these
models and are not claimed to have a prospective feature history.

An `evidence_key` makes retrying the same retrieval/parser/entity/status idempotent.
A genuinely later fetch is a new observation even when content is unchanged; the
raw blob is deduplicated by content hash. Replays deduplicate unchanged results.
Existing observations receive null keys; no old evidence is backfilled.

## Freeze

Prospective source keys end in `:prospective-v1`. Generation requires a matching
committed scheduled observation no older than 900 seconds. It freezes participants,
deadline, probability, input dataset, feature vector, schedule observation, training
cutoff, code/dependency identity, and model configuration. The upcoming rows are
locked during persistence and deadlines are checked again immediately before insert.
No update/reforecast is allowed for an existing match/source pair.

Elo v1 remains the unchanged 1500/K32/400 formula. With no observed results it may
emit its explicit 1500 cold-start prior (50%), labeled accordingly. Capturing older
results today makes them usable for future forecasts; it does not establish their
historical availability. ML still requires sufficient observed training examples.
Experimental models require opt-in; no new model or ensemble is automatically
promoted. Historical replay reports and actual prospective reports stay separate.

## Result resolution

Scoring verifies persisted run/dataset/raw integrity and freeze time/identity, then
uses the latest observed result as of the report. It scores the saved probability,
never a regenerated prediction. Reversed participant order is handled explicitly;
replacement opponents, earlier starts, tied scores, and unresolved results remain
unscored with reasons. A later correction creates a new report snapshot; previous
reports and predictions remain immutable. Missing/corrupt artifacts fail the job.

Prospective accuracy, Brier and log loss are descriptive and separated by source.
Calibration bins/ECE are withheld below 100 outcomes per source. This threshold
is a display guard, not a statistical guarantee. Legacy forecasts and historical
experiments never contribute to these metrics.

## Jobs and failure behavior

One cycle synchronizes bounded recent results, synchronizes upcoming schedules,
generates forecasts from fresh evidence, and writes an immutable scoring report.
PostgreSQL session advisory locking prevents overlapping cycles across workers.
Collection failures stop forecasting for that cycle and produce a failed receipt.
Each normalized match transaction commits independently, so partial collection
remains inspectable after failure. No automatic data repair is attempted.

The local worker repeats with a 300-second delay after each cycle. External
schedulers can invoke `--once`; do not run both unnecessarily. STARTED and terminal
artifact receipts plus append-only PipelineRun rows record status. A hard process
kill can leave only STARTED; stale-run monitoring is required. The health command
requires a successful collection-enabled run within 15 minutes. It does not treat
`--no-collect` smoke runs as collector health. Logs and health signals are prepared
for CloudWatch; AWS resources and alarms are not provisioned.

Artifacts use a shared local directory/durable container volume. S3 compatibility
means stable content keys and portable JSON/raw bytes; a network S3 storage adapter
is still not implemented. Back up and restore the entire key hierarchy alongside
the database. Database owners and filesystem administrators are trusted operators,
not adversaries covered by append-only application protections.
