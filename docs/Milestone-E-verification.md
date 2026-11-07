# Milestone E verification

Verified November 7, 2026 using Python 3.13.5 and the in-app browser, against the uncommitted Milestone E implementation (engine 0.5.0).

## Automated checks

- `.venv/bin/python -m unittest discover -s tests`: 141 tests passed in 8.710 seconds, including the previous 118 tests and 23 reporting tests.
- `.venv/bin/python -m pip check`: no broken requirements. The sandbox's unavailable pip cache produces a harmless cache warning.
- `git diff --check`: passed.
- No packages installed; Flask remains the only direct runtime dependency.

Tests cover known population moments and standard deviations, singleton/empty populations, histogram edges, initial/periodic/terminal sampling, tick-aligned custom intervals, batching/reset, cursor replacement and bounded retention, a 10,050-tick history, unchanged model/RNG state with reporting enabled versus disabled, deterministic CSV/JSON, CLI file export, headless/API equivalence, stale-run protection, and export/current-statistic consistency.

## Browser smoke observations

- Default seed 0 at 20× was paused at time 411.1 (4,111 ticks): population 138, births 335, deaths 247 (39 starvation, 208 age), highest generation 7. Population rose above 200 and subsequently declined and recovered; speed/vision means changed. Final mean inherited speed was approximately 3.534 and vision 8.446. This is one descriptive smoke run, not calibration or proof of selection.
- All three time-series charts and both histograms rendered and updated. Current statistics and distributions identified their current time separately from the latest periodic sample. Pause preserved measurements, and Reset cleared the old history.
- Real browser CSV and JSON downloads were parsed successfully: both contained 413 measurements (412 recorded samples plus the current 411.1 endpoint). Final population 138, seed 0, applied food rate 8 and initial food 200 agreed with the interface. Engine version was 0.5.0. Pending edits are separately covered by API tests.
- A second seed-0 run with zero initial food and zero replenishment reached extinction at time approximately 136.557, with 50 starvation deaths and no births. Playback stopped; all 138 samples, including exact extinction, remained available. Trait means/SDs became unavailable and histogram counts were all zero. Reload preserved this terminal history. Defaults were then restored and Reset verified.
- At 1280×640, the entire square Environment fit between approximately y=138.8 and y=589.7. At 390×700 it fit between y=97.5 and y=421.8, above independently scrolling controls. No page overflow was observed. Charts resized with their pane; temporary viewport overrides were removed.
- Accelerated playback remained usable with reports open, including Pause, Reset, scrolling, and downloads; no JavaScript errors were observed. This is an interaction smoke test, not a frame-rate benchmark or native Safari/hardware certification. Large populations remain computationally expensive in the existing biological resolver.

## Scope and limitations

Biological rules/defaults are unchanged. No Milestone F calibration, database, new traits, automatic scientific conclusions, commit, or push was performed.

Reporting retains the initial point plus the latest 9,999 measurements, with explicit gaps and dropped-sample metadata. Export before needed older samples are dropped. Existing organism death archives remain unbounded independently of reporting history. Chart rendering uses a bounded extrema envelope and at most four redraws per second; exports retain original sampled values.

The default sampling interval is exactly one simulated unit at dt=0.1. Custom dt that does not divide the requested interval rounds upward to a whole number of ticks (e.g. dt=0.3 gives 1.2 units); metadata reports this explicitly. This resolution convention avoids changing biological step timing or inventing interpolated states. See `R1-reporting.md` for full measurement and export definitions.


## Final reporting refinements

Added a speed-versus-vision Canvas scatter plot using paired traits from the authoritative current organism payload, and an additive JSON `living_organisms` snapshot. No biology/defaults, dependencies, or CSV columns changed.

Four additional tests cover exact individual fields and paired traits, overlapping/singleton/empty populations, exclusion of dead organisms, deterministic repeated exports, unchanged model/RNG trajectories, and API/export agreement. The full suite passed all 145 tests in 8.780 seconds, including all previous 141; `git diff --check` also passed.

Browser smoke verification confirmed 50 initial points, full-precision hover status, click selection in the inspector, and repeated nearby-point clicks cycling from org 36 to org 45. At 20× the plot updated to 122 living organisms at simulated time 599 (457 births, 385 deaths); no JavaScript errors were observed. A downloaded JSON report was parsed with 122 ID-sorted living entries and descendant lineage, generation, age, energy and offspring data. Earlier download verification also checked all nine fields for 50 founders. At 1280×640, the full Environment still fit between y=138.8 and y=589.7, with charts in the independently scrolling pane; viewport override was reset.

Dense points can overlap exactly and their opacity saturates; repeated clicks and the inspector dropdown provide individual access. Point coordinates are never jittered. This is descriptive reporting, not evidence that a cluster or offspring count establishes fitness or selection.
