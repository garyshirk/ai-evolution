# R1 batch experiments — Milestone F.1

## Execution and state ownership

`experiments/r1/batch.py` contains BatchConfig, BatchLimits, aggregate(), execute_batch(), and BatchRunner. It imports no Flask or UI code. BatchConfig nests the existing frozen SimulationConfig: no duplicate biological defaults or rules. Flask constructs one runner in its application factory. A daemon thread executes seeds sequentially, independently of the single-run engine and browser playback settings. Every run creates a new Simulation and its private seeded generator. No multiprocessing, scheduler framework, third-party dependencies, or database are introduced.

Only one batch may be running/cancelling per application; overlapping starts return conflict. Worker physics never holds the runner or single-run request lock. Short publication locks protect current progress and completed reports. `sleep(0)` between ticks yields execution to request threads; Python threads share the GIL and CPU, so concurrency is responsiveness, not parallel speedup. Run Flask in its supported threaded local-server mode, one process. Multiple server processes would have independent batch state.

A batch has an opaque ID and status idle/running/cancelling/completed/cancelled/failed. Polling every 750 ms returns progress, run summaries and aggregate statistics, not every stored history. Run detail is fetched on selection. Switching tabs keeps the DOM and results; opening the Batch tab drains/pauses single-run advancement, and returning does not auto-resume. A user can explicitly resume a single run while batch execution continues; they remain independent but share CPU.

Cancellation is checked before each run and each engine tick. It discards the unfinished current run and stops later runs; already completed reports remain accessible/exportable. A run reaching its endpoint while cancellation arrives may still be published as complete. It is valid for the final run to finish before cancellation is serviced, yielding completed rather than cancelled. No model rollback or forced killing is performed. There is no pause/resume for batches.

## Inputs and workload limits

Defaults: 20 runs, duration 2,000 simulated units, seed 0. Consecutive seeds are starting_seed through starting_seed + runs - 1, all JavaScript-safe integers. New batches default to randomized founder ages. The minimal Founder ages selector offers Randomized (uniform) or All zero (legacy), and the applied founder_age_mode is included in each full configuration. Older imported batches missing it retain zero-age founders. The browser exposes all SimulationConfig fields, with common population/food/cost/mutation controls first. Validation is authoritative on the server, using SimulationConfig plus batch-only limits. Invalid input does not replace the existing batch.

Duration must be positive and align with whole engine ticks, within relative floating rounding tolerance 1e-12. A run advances that many existing fixed-duration ticks or stops earlier at exact extinction. No partial artificial tick or overshooting duration rule is added. Terminal fractional tick times remain those produced by the existing engine. Changing dt still changes the underlying approved model; reporting follows the existing tick-aligned cadence.

Default BatchLimits:

| Limit | Value |
| --- | --- |
| Runs | 200 |
| Duration per run | 10,000 |
| Total requested ticks across runs | 2,000,000 |
| Initial population | 500 |
| Food cap | 2,000 |
| Conservative retained-measurement budget | 500,000 |
| Living population guard | 10,000 |
| Archived death-record guard per run | 100,000 |

The measurement estimate uses MetricsCollector's actual cadence and retention defaults, shared with Simulation. With N requested ticks and K ticks per sample, the per-run bound is `min(history_limit, 1 + floor(N / K)) + (1 if N % K else 0)`. This counts initialization and periodic samples, plus a possible terminal/current endpoint between sampling ticks. A terminal endpoint on a scheduled tick replaces that sample rather than adding another; earlier extinction cannot exceed the bound. Each run inherits the Milestone E retention policy (initial plus latest 9,999 recorded samples), with an optional current final endpoint outside that window. Dropped history and sequence gaps remain explicit.

For 50 runs of duration 2,000 with dt 0.1, N=20,000 and K=10. The estimate is 50 × 2,001 = **100,050 retained measurements**, within the unchanged 500,000 limit. The previous tick-based estimate incorrectly rejected this configuration at 500,050. Measurement interval, retention defaults, physics tick limits and biological rules are unchanged.

Limits can be configured programmatically with `create_app(batch_limits=BatchLimits(...))`; they are execution safeguards, not biological defaults. Settings returned to the UI reflect those limits. Runtime population/death-record guards are inspected every 20 ticks and at completion; if exceeded, the batch becomes failed, retains completed runs and reports the reason. The current run is omitted. The guards never cull organisms or alter energy/reproduction.

Cancellation and guards cannot interrupt an individual engine tick, initialization, or final report construction. Pathological parameter settings or explosive populations can make a tick slow or consume substantial memory before the next guard. These are practical safeguards, not a hard memory/time sandbox. The default 20 × 2,000-unit workload can take substantial CPU time; start with a small batch for interface review. No extensive calibration was performed in F.1.

## Results and descriptive aggregates

Each completed run records its number, seed, full applied configuration, engine/Python version, final time/tick/terminal state, cumulative statistics, trait statistics, energy accounting, reporting metadata, and retained time series. `stop_reason` is duration or extinction, with boolean survived. Initial empty populations are extinct at time zero; populations going extinct exactly at the requested horizon count as extinct.

Per-run results reuse the existing experiment report conventions, excluding its final individual-organism list and current histograms. Batch inspection needs aggregates/history, not stored positions or full individual archives. The existing single-run JSON export remains unchanged. No new per-step individual-position storage is introduced.

Completed-run aggregates:

- Survival percentage = surviving completed runs / all completed runs × 100.
- Average final population = sum of final populations / all completed runs, including extinct populations as zero.
- Average final speed/vision = unweighted mean of final trait means across surviving completed runs. Extinct traits are undefined, not zero; their count and the trait denominator are explicit.
- No completed runs means unavailable averages/percentage, not zero evidence of survival. No survivors means unavailable trait means.
- Cancelled partial and failed unfinished runs are excluded. The completed/requested counts make that incomplete sampling explicit; cancellation can bias any observed summary.

The UI shows initial/cumulative/current statistics with the same definitions as Milestone E. Charts reuse its bounded Canvas line renderer and display gaps and unavailable means correctly. F.1 summary statistics remain unchanged. F.2 adds descriptive cross-batch analysis separately; no confidence intervals, reproductive fitness estimates, automatic conclusions, neutral traits or calibration are included.

## Replay and exports

Open in Single Simulation uses the server's stored completed result, protected by batch ID and run number, to instantiate a fresh paused engine at time zero with the exact seed and full SimulationConfig. It replaces the current single run and resets its histories, IDs and RNG. Existing visible parameter controls, including Initial Population, are updated; remaining configuration is retained by the authoritative engine. A normal subsequent Reset preserves those settings unless explicitly edited. No position history is needed because replay recomputes the run.

Batch JSON schema version 1 contains `configuration` (runs, duration, starting_seed, simulation), engine/Python versions, limits, batch ID/status/error, completed/total counts, progress, lightweight run summaries, detailed `results`, and `summary` with denominator definitions. Each result includes applied configuration and seed, sufficient to reproduce the run in the supported engine/runtime. Opaque batch IDs vary between experiments; compare seeded per-run results rather than requiring byte-identical whole batch files. No export timestamp or wall-clock values are used as model input.

The UI enables export once a batch is completed, cancelled, or failed. The API also supports an internally consistent snapshot of completed runs during execution, marked running/cancelling as appropriate. No CSV batch format or resumable checkpoint is added.

F.1 current-runner results are replaced by another validated batch; export partial/cancelled results first. In F.2, successfully completed batches are additionally added to a separate bounded experiment library, so starting another batch preserves those experiments. See `R1-statistics.md`. Browser reload can recover current progress/completed results from the same running server, although edited form values and selection may reset. Server shutdown/restart loses memory, stops the daemon worker, and does not resume interrupted work. Bounded summaries/history do not make JSON zero-cost; large exports may temporarily allocate additional memory. No batch persistence or application-exit cancellation workflow is implemented.

## HTTP endpoints

- GET /api/batch/settings: defaults, integer fields, configured limits.
- POST /api/batch: validate/start; body `{runs, duration, starting_seed, simulation}`; accepted 202, validation 400, active-batch conflict 409.
- GET /api/batch: current progress and lightweight completed-run summaries.
- POST /api/batch/cancel: body `{batch_id}`; stale ID conflict 409.
- GET /api/batch/<batch_id>/runs/<number>: detached completed report; missing/stale 404.
- GET /api/batch/export.json?batch_id=…: stable JSON snapshot; stale ID 409.
- POST /api/control with action replay_batch, batch_id, run_number and the existing run_id/expected_step protection: fresh replay, or conflict for stale selection/state.

Batch endpoints share the existing localhost-only, no-auth single-user scope. Do not expose this development server publicly. No external network calls occur during experiments.

The Single Simulation Initial Population input uses the existing shared `max_initial_population` execution limit (500 by default), returned as `population_limit` in single-run responses. Reset validation accepts only nonnegative integers within this limit and rejects invalid updates atomically. SimulationConfig and engine defaults remain unchanged; the limit applies to browser/API population requests, not biological population growth.
