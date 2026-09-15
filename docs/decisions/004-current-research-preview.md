# Current research preview is separate from prospective evaluation

The upcoming API adds nullable `current_preview`; existing `forecasts` are unchanged.
Preview computation performs no database writes. Prospective generation and scoring
never import the preview module or its history. No schema change is required.

`python -m app.research.preview --export` reads a consistent, read-only snapshot of
the configured local database. It exports decisive completed series with known VLR
team identities into `app/research/preview_history.json`. This versioned research
dataset contains match/team VLR IDs, series scores and scheduled dates, its export
time, and a SHA-256 checksum. Export time is not historical availability. The file
is shipped in the API image so cloud database history need not be fabricated.

At request time, cloud match rows override matching VLR IDs (including retractions),
and new completed series join the base history. The merged rows are replayed in
scheduled-date/VLR-ID order using the unchanged Elo v1 formula. Future-dated,
tied, invalid and unknown-identity series are excluded. Unknown teams use 1500 and
are explicitly flagged. The response identifies the base dataset, effective dataset,
model version and computation time. It explicitly declares unknown availability and
exclusion from prospective scoring. This is current research, not a walk-forward
performance claim. Corrections outside the cloud data require re-export/redeployment.

The checked-in snapshot is a deliberately simple demo distribution mechanism.
Refresh it from the full local database after meaningful backfill changes, inspect
its diff/count/checksum, and redeploy. Do not export a tiny cloud database over the
full snapshot. No secret, observation timestamp or forecast is included. Git retains
prior snapshot versions. A missing/corrupt base produces an unavailable preview.

The frontend presents current previews prominently and saved forecasts separately,
even when probabilities match. Audit records are collapsed by default. Prospective
metrics continue to reflect only the existing frozen-forecast scoring pipeline.
