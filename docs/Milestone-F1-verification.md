# Milestone F.1 verification

## Automated checks

On November 7, 2026, using the existing Python 3.13.5 virtual environment:

```sh
.venv/bin/python -m unittest discover -s tests -q
.venv/bin/python -m pip check
git diff --check
```

All **161 tests passed in 9.788 seconds**, including all 145 Milestone E tests and 16 new batch tests. Dependency integrity and whitespace checks passed. Pip reports only the existing sandbox cache warning. No dependencies were installed.

New coverage includes configuration/defaults and workload validation, seed sequence and execution count, repeated seeded results, exact batch/single-engine state and RNG equality, retained history equivalence, initially empty/sub-tick extinction, aggregate denominators, cancellation before/during/between runs, completed-result preservation on cancellation, failure reporting, nonblocking requests and overlapping-start conflicts, detached individual results, JSON exports, complete-configuration time-zero replay, stale IDs, tab/assets, and configurable limits.

The first new test run exposed a test assertion comparing engine time 0.30000000000000004 with literal 0.3. The assertion now uses a floating comparison; no clock or biological code was changed.

## Browser smoke observations

In-app browser against localhost port 5054:

- Verified two tabs, defaults (20 runs, duration 2,000, seed 0), common controls, and all remaining SimulationConfig fields in Additional R1 parameters.
- Ran three simulations with seeds 10–12, duration 3, initial population 5 and initial food 20. Completed 3/3, all survived, average final population 5. Selected run 2 (seed 11), inspected its applied configuration/statistics and all three history charts.
- Downloaded real batch JSON and parsed it outside the browser. All three final-statistics dictionaries and all sampled histories matched three independently executed Simulation instances with the exported configuration and seeds.
- Open in Single Simulation selected seed 11 with population 5, initial food 20, and time zero; paused replay was immediately available. Returning to the batch preserved completed results/selection.
- Started a longer 20 × 2,000-unit request, observed current-run/time progress, switched to the Single tab and back while requests remained responsive, then cancelled. Status transitioned through cancelling to cancelled; no partial run was counted. A separate automated test verifies an already-completed report remains in cancelled exports.
- Ran two short simulations with max lifespan 0.15 and duration 1. Both were classified extinct at time 0.15, with five age deaths each and zero population; trait summaries were unavailable and population charts included terminal zero. This is an edge-case smoke test, not calibration or a changed default.
- At 1280×640 the full square Environment fit between y=185.8 and y=589.7 (size approximately 403.9). At 390×700 it fit between y=144.5 and y=440.6 (size approximately 296.1), with no horizontal page overflow. Viewport overrides were reset.
- No JavaScript console errors were observed. This verifies practical interaction, not native Safari, MacBook hardware performance, or large-workload throughput.

Final software version is 0.6.0. The server was restarted after final changes; restart intentionally clears batch memory. No extensive 20 × 2,000-unit experiment/calibration was completed. No commit or push was performed.

## Manual review procedure

1. Launch `.venv/bin/python -m ai_evolution serve --port 5054` and open http://127.0.0.1:5054/. Restart an older server first if it occupies that port.
2. In Single Simulation, verify Start/Pause/Single step, organism selection, existing reports, and CSV/JSON exports.
3. Switch to Batch Experiments. Use 3 runs, duration 3, starting seed 10, population 5, initial food 20; leave other defaults. Run Experiment and verify three seeds, duration endpoints, summaries and histories.
4. Select run 2; expand Applied configuration, then Open in Single Simulation. Verify seed 11 and time zero, resume or step, and return to the batch to verify results remain available.
5. Export Batch JSON. Inspect configuration, engine/Python versions, status, run count, per-run seeds/statistics/measurements and summary definitions. Save before starting another batch.
6. Start a longer batch and Cancel while the current time advances. Verify normal tab navigation remains responsive and completed reports survive cancellation.
7. For a fast extinction check, use duration 1 and Additional R1 parameters → Max lifespan 0.15. Verify exact extinction endpoints and unavailable traits. Restore lifespan 200 afterward.
8. Try invalid inputs and an excessive workload; verify an error without changing completed results. Resize the window and check that the Environment remains fully visible and controls/reports scroll within their panes.

## Limitations

See `R1-batch.md`: one in-memory batch per server, no restart persistence/resume; sequential CPU-bound worker; cancellation only between ticks; periodic resource checks are not a strict memory/time sandbox; limited retained history; large exports allocate memory; trait aggregates explicitly use survivors only. Partial cancelled runs are excluded, so incomplete-batch summaries may be biased. F.2–F.5 and biological/default changes are outside this implementation.


## Single Simulation Initial Population refinement

Added the main-control Initial Population input (default 50). It is applied on Reset, hydrated from the authoritative configuration on page initialization and batch replay, and validated as a nonnegative integer within the existing configurable application initial-population limit (default 500). Engine defaults and biological rules are unchanged.

The full suite passed **164 tests in 9.788 seconds**, including three new initial-population tests and an expanded batch replay/export regression. Tests cover default 50, custom/reset populations, zero, upper boundary, invalid types/ranges with atomic rejection, custom application limits, initial measurements, actual living counts, and exported configuration/records.

Browser smoke verified a fresh input of 50, Reset to 7 organisms at time zero, and a downloaded JSON file whose applied configuration, initial measurement, and seven living records agreed. Opening a batch run configured with 3 organisms filled the field with 3 and displayed three organisms at time zero; max remained 500. No JavaScript errors were observed. All changes remain uncommitted.
