# Observation-time research

Status: implemented; real historical model validation BLOCKED by missing evidence.

## Evidence before prediction

Scheduled match time is neither actual start nor result availability. Historical
normalized records do not establish when their values were known. We retain them
and report UNKNOWN rather than backdating new observations.

The collector now archives original response bytes and retrieval metadata under
SHA-256 keys. Match observations record source receipt and processing timestamps.
Replay conservatively uses the later timestamp and requires it strictly before
prediction time. Collector clock accuracy and delayed collection remain limitations.
Raw statistics are archived, but statistics/rosters are not model features.

Snapshots freeze an observed pre-match schedule and participants. Later changes
cannot replace previously emitted features. Unchanged observations do not update
ratings twice. Corrections and retractions rebuild current state from the known
event history; past predictions are never rewritten. Training labels reflect
what was known at each training cutoff, not final hindsight labels.

## Small, explicit models

Elo v1's formula stays unchanged: initial 1500, K=32, scale=400. The old
`model:elo:v1` forecasts remain intact. Strict runs use `model:elo:v1:observed-v1`
to distinguish the evidence protocol without claiming a new formula.

Elo v2 candidates decay ratings toward 1500 with 30, 90, and 180 day half-lives.
Time since observed result is an explicit proxy, not measured competitive inactivity.
No candidate is assumed superior. Logistic regression (scaled features, C=1) and
histogram gradient boosting (100 iterations, 7 leaves, learning rate .05) use
Elo probability and observed recent form/opponent-strength features with missingness
indicators. Ninety days is a candidate feature window, not an empirically established
optimum. Map, roster, region, tier, patch, and head-to-head features remain unsupported.

ML training requires 100 labeled examples and both classes. Refits use UTC month
boundaries, frozen pre-match feature rows, and only labels available before cutoff.
Single-threaded fitting/prediction and recorded seeds/dependencies aid reproducibility.
Dataset, code, configuration, feature values, cutoff, and forecast are preserved in
hashed artifacts and model-run manifests. Cross-platform bitwise equivalence is not
guaranteed; platform and dependencies are recorded.

## Evaluation and promotion

Chronological validation and held-out test periods report accuracy, Brier, log loss,
10-bin calibration/ECE, common cohorts, recent 90 days, month, and event segments.
Validation labels must be available before the test boundary. An equal-probability
ensemble is evaluated on a common cohort. A supporting report needs sufficient
common validation/test examples and better Brier and log loss in both periods;
this is a review gate, not statistical proof or automatic promotion. Generation
requires explicit experimental opt-in and a matching supporting ensemble report.

Historical replay predicts at the observed scheduled deadline; live generation
predicts when the job runs. These horizons differ. Future evaluation should score
actual archived live forecasts at their recorded generation times.

The legacy scheduled-order diagnostic is reproducible but explicitly
NOT_LEAKAGE_SAFE. Its metrics cannot justify promotion. The current strict dataset
has zero supported predictions; all model comparisons remain BLOCKED.

## Storage and public API

Migration `a21d7b643f90` adds observations, model runs, and nullable forecast provenance.
PostgreSQL triggers reject UPDATE/DELETE of forecasts, observations, and runs.
This is application integrity protection, not protection against a database owner.
Old rows and unknown provenance remain unchanged. Content-addressed filesystem
storage needs a durable volume and backup; an S3 storage adapter is not implemented.

Production human writes default to disabled. A configured bearer operator token
allows writes; this is not multi-user identity/authorization. Reads expose stored
individual forecasts and provenance, with bounded pagination. There is no fabricated
consensus, hidden model replacement, or automatic infrastructure provisioning.
