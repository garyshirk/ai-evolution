# R1 statistical analysis and experiment comparison — F.2

## Ownership, compatibility and architecture

The existing R1 engine and RNG/biological configuration are unchanged. `statistics.py` contains reusable, deterministic functions over exported dictionaries; it never reruns simulations or reads model randomness. `library.py` owns validation and a bounded temporary experiment library, independent of Flask. `experiments.js` handles library/results/comparison controls; `statistical-chart.js` draws Canvas mean lines and percentile bands. Existing single-run/F.1 plotting is reused for individual histories.

Each library entry has a unique internal UUID, separate from the batch export ID, a mutable display name, the original batch report, and cached derived summaries/trajectories. Native completed runs are published by a completion callback; the library references their existing read-only dictionaries rather than copying all measurements. Starting a new batch replaces only the F.1 current-runner object, not library experiments. Renaming changes only the display name; exporting retains the F.1 schema 1 report, without adding internal library IDs/names. Publication ID/error fields are progress-API metadata only, not export-schema changes. Imports never merge run sets. The server owns entries and clients receive JSON views; internal report references are treated as immutable.

Run retains F.1 progress, cancellation, current partial-run inspection and export. Results manages the library, aggregate views and individual runs. Compare accepts two distinct library entries. Selecting an individual run reads that experiment, even after another batch replaces the runner. The top-level Single Simulation/Batch tabs and responsive world layout are preserved. Static scientific help explains drift, bottlenecks, survivorship, confounding and stochastic variation.

The library lives in the single Flask process. It survives tab navigation and browser reload/restart while the same server remains running, but no server restart. There is no database, disk cache, cloud storage, persistence/resumption or cross-process sharing. Export JSON for permanent storage. Removing an entry releases library ownership, but the current runner may independently retain that same completed batch until replacement.

## Validation and practical bounds

Imports accept compatible R1 batch schema version 1, including the existing F.1 `configuration`, `results`, `completed_runs`, `total_runs`, final status and engine/Python metadata. Single-simulation exports are rejected. Completed status requires all requested results. Finished cancelled/failed partial exports can also be imported; their requested/completed counts and incomplete-sample warning remain explicit. Running/cancelling exports are not accepted as finished experiments.

Validation requires complete SimulationConfig fields, consecutive unique seeds/run numbers, internally consistent final population/birth/death/status accounting, sorted finite measurement times, complete metric fields, valid trait/null semantics, initial/final endpoints, final-statistic agreement, and matching run/batch configurations and versions. Missing required measurements/metadata are errors. A missing interior scheduled observation or an explicit retention gap can still leave valid endpoint statistics; those files are accepted with aggregate trajectories disabled. Unknown scientific outcomes are never filled in. Imported summary values are not trusted: analysis is recomputed from validated run results and measurements.

Names are 1–120 printable characters, displayed using textContent/Option rather than HTML interpretation. Filenames supply import defaults. Nonfinite JSON constants/numbers, malformed JSON, unsupported schemas, inconsistent data and oversized requests produce useful errors without replacing existing entries.

Limits: 256 MiB per imported file/request, 8 experiments, 1,000,000 total retained measurements in the library; at most 1,000 runs, duration 1,000,000 and 10,001 samples per imported run; imported speed/vision bounds at most 1,000,000 and count fields at most 1,000,000,000. Aggregate schedules are bounded at 20,000 intervals. These are analysis/execution safeguards, not biological caps. Existing batch execution limits remain unchanged. 50–100 runs × 2,000 units at the standard one-unit reporting cadence fit the intended measurement budget. JSON parsing/exporting can temporarily allocate large buffers; limits are not a hard process-memory sandbox. Multiple large requests share CPU/memory.

On library-capacity exhaustion a newly completed batch remains completed/exportable in Run, with an explicit library error. Existing experiments are never evicted silently. Export, remove an entry and import the new completed batch to add it. Cancelled/failed runs are not auto-added; their finished partial exports can be imported explicitly.

## Independent observations and final statistics

Each completed simulation is one independent observation. Organisms and time samples are not independent experimental replicates. Cancelled partial or failed unfinished runs are not observations. Incomplete batches can be biased by which runs completed.

For final population, include extinct runs as zero. For inherited speed and vision, use each surviving run's final living-population mean, with equal weight per run regardless of its population size. Extinct traits are unavailable rather than zero. Every metric reports its contributing run count.

For sorted valid observations x:

- Mean: sum(x)/N.
- Median: middle observation, or mean of the two middle observations for even N.
- Minimum/maximum: observed extrema.
- Sample standard deviation: sqrt(sum((x−mean)^2)/(N−1)), N ≥ 2. For N < 2, SD is unavailable (N/A / JSON null).
- N = 0 gives unavailable mean/median/extrema as well.
- Extinction percentage: 100 × extinct completed runs / completed runs; unavailable if no runs completed.

This across-run sample SD differs from Milestone E's within-population trait SD, which uses N in its denominator. No p-values, hypothesis tests, confidence intervals or automatic significance claims are included.

## Observed bottlenecks

For each run, take the minimum population among retained measurements with simulated time strictly greater than zero, including its final endpoint. Exclude initialization. If there is no post-initial measurement (for example an initially empty world), the observed minimum is unavailable. The minimum-population distribution uses only runs with available minima and exposes its count and per-seed values.

Report counts and percentages for any post-initial observation ≤5, any observation exactly 1, and final extinction. Five is explicitly an exploratory warning threshold, not an established biological boundary. Threshold/exact-one percentages use runs with post-initial observations as denominator; the number without observations is separately displayed. Extinction percentage always uses all completed runs, including initially empty runs.

These are observed sampled minima, not continuous minima. In particular, a run can go from 2 to 0 between records without a recorded population of 1. Retention gaps and sampling can hide deeper bottlenecks. The UI states these limits rather than inferring unrecorded population states.

## Aggregate trajectories and percentile bands

A compatible experiment has one common effective sampling interval. Candidate times are its regular recorded schedule from zero through planned duration, plus the actual final-duration endpoint when off that schedule. At each time every living run must have an actual recorded observation. Alignment tolerance is relative 1e-10, with absolute tolerance min(1e-9, sampling interval × 1e-6), preventing tiny adjacent schedule times from merging. Endpoint validation similarly bounds absolute tolerance by dt. Recorded nonterminal samples off the shared schedule (except the common duration endpoint), inconsistent effective intervals, missing living observations or exported retention gaps disable the aggregate trajectory with a reason. No resampling, interpolation, last-value carry-forward or fabricated living-population observations are used.

An extinct run contributes known population zero at subsequent scheduled times through planned duration, including time zero for an initially extinct run. It contributes no traits at/after extinction. An off-grid terminal record informs extinction timing but is not inserted as a new common time for other living runs with no observation there. Final endpoint values/statistics remain available separately. All-extinct later trait means/bands are unavailable and remain blank, not zero.

At each supported time compute the mean and 10th/90th percentiles over the contributing values. Percentiles use linear interpolation between sorted order statistics at position (N−1)×p: x[floor(position)] + fractional_part×(x[ceil(position)]−x[floor(position)]). N=1 gives that same value for both percentiles. This interpolation is over the distribution of simultaneous observations, never over simulated time. Bands describe variation across runs, not uncertainty/confidence intervals for a population parameter.

Population count includes all completed runs; trait count includes runs with a living recorded population at that time. A time-index slider exposes contributor counts for every aggregate row, avoiding thousands of DOM table rows. There is a metric switch for population, inherited speed and inherited vision. Trait axes use configured limits; overlays use their union.

Calculations use all validated retained values. Derived results are cached at ingestion; library polling fetches metadata only. Canvas rendering alone uses a bounded first/last/mean/percentile-extrema envelope for long series, preserving null boundaries. Raw exported data and exact derived statistical values are not downsampled. Per-run inspection retains the original history and its gaps.

## A/B comparisons

Configuration tables include requested run count, duration, starting seed, actual completed seed set, and every SimulationConfig parameter. Changed values are highlighted; multiple configuration changes warn that no single effect is isolated. Actual seed lists remain explicit for incomplete batches.

Side-by-side descriptive statistics use identical definitions. Absolute differences are B−A. Percentage change is 100×(B−A)/A when both values exist and A is nonzero; otherwise unavailable (including numerical overflow). For percentages/rates, the absolute difference is in percentage points, while the relative change is still labeled percent. There are no undefined-value/zero-denominator substitutions.

Paired comparisons require exactly matching, nonempty completed seed sets. Each seed contributes B−A final population; trait differences require survival in both runs. Display every pair, the number of valid pairs and the same descriptive mean/sample-SD/median/range. Nonmatching sets receive only unpaired aggregate comparisons, with a reason. Matching seeds are useful controls but cannot guarantee the same random-event sequence after configurations diverge.

Direct trajectory overlay additionally requires equal durations (same alignment tolerance), compatible complete trajectories and matching recorded time axes. Otherwise overlay is disabled with an explanation. Final outcomes at different durations may still be displayed but carry a prominent different-endpoint warning; they are not equivalent-time outcomes. Different engine/Python versions also trigger a compatibility warning. Means use blue/orange A/B labels and matching translucent percentile bands.

## Replay policy and scope

Library replay reads the stored seed and complete applied configuration, initializes the existing engine paused at time zero, and updates visible Single Simulation fields including Initial Population. It does not require the experiment to remain in the current BatchRunner. Existing stale single-run/step protection remains in force, as does the configured application initial-population limit.

Software releases 0.6.0 (F.1) and 0.7.0 (F.2) replay with zero-age founders; release 0.8.0 supports uniform or zero modes. Python's complete version string must match the server. Legacy files missing founder_age_mode are normalized to zero before inspection, comparison, re-export and replay; all other required configuration fields remain mandatory. New 0.8.0 exports must explicitly specify the mode in batch and per-run configurations. Other releases/runtime versions remain analyzable but receive a clear replay-disabled explanation. This explicit compatibility list is not a promise of arbitrary future-version or cross-platform bit identity. F.2 statistical analysis changes no simulation behavior. The subsequent 0.8.0 founder-age refinement changes only the default initial age distribution and adds a separate age-only RNG; lifespan, costs, reproduction and mutation remain unchanged. See `R1-founder-ages.md`.

Changes in means, correlations or batch outcomes do not by themselves establish natural selection. Mutation, drift, bottlenecks, composition, environmental pressures and survivor conditioning can contribute. No reproductive fitness tracking, selection-versus-drift controls, calibration, formal hypothesis tests or F.3–F.5 work is included.
