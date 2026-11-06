# Milestone C verification

Date: November 5, 2026. Environment: Python 3.13.5, Flask 3.1.2, existing `.venv`.

## Automated verification

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m pip check
```

Final result: **81 tests passed** in 5.877 seconds; no broken requirements. No dependencies were installed or updated for this milestone.

The previous 49 tests remain in the suite, with scope-sensitive expectations updated for the authorized ecology. Clock-only and movement-only checks disable unrelated costs, spawning, or age limits in their fixtures. Initialization, traits, IDs, lineage, RNG isolation, headless execution, reset/replay, snapshot isolation, and UI/API controls retain their original invariants. The former constant-state biological check now verifies absence of reproduction and mutation, including archived dead founders.

There are 30 focused survival tests and two additional API tests. Coverage includes:

- Vision inclusion/exclusion, nearest-visible selection, search/pursuit speeds.
- Food crossed between endpoints, reflection, multiple wall contacts, tangent/overlap/stationary contacts, tick-end contacts, stopping after a meal, and next-tick eligibility.
- Earliest arrival regardless of organism ID, seeded ties, coupled multiple-food conflicts, approximately uniform ownership over fixed seed sets, and reversed storage order.
- Baseline, nonlinear vision, nonlinear movement, actual reflected distance, stationary upkeep, immediate starvation position, death/food equality, food rescue before depletion, age death, and ledger reconciliation across seeded small worlds.
- Positive exponential waiting times and sample mean, cap discard behavior, actual spawn times, no pre-spawn eating, no automatic regeneration at consumed locations, no events after extinction, and deterministic spawning/replay.
- Population never increasing, exact terminal state, automatic API pause, retained death details, final batch truncation, parameter-reset validation, and headless/API equivalence.

A diagonal-pursuit regression tests multiple headings: the intended target's consumption event and movement stop share one analytic entry time. Browser verification revealed that independently rounded stop/intersection roots could otherwise leave an organism just outside its target indefinitely; that defect was corrected and the complete suite rerun.

## Browser smoke test

Started the updated application with:

```sh
.venv/bin/python -m ai_evolution serve --port 5051
```

Opened `http://127.0.0.1:5051` in the in-app browser. Verified live food consumption, pursuit speed, changing energy, organism selection/vision overlay, playback, pause, and reset controls.

A temporary stress run used food rate zero and very high movement/vision costs through the existing reset-only controls. It became extinct, automatically paused, disabled further stepping, retained food/death statistics, and kept the selected dead organism inspectable. No model code or default values were changed for this check. Reset restored the approved defaults.

After the pursuit correction, a normal default seed-0 run reached simulated time 200 (2,000 ticks), consuming 1,682 food items. It ended with 50 age deaths, zero starvation deaths, and 58 remaining food items. The extinction notification appeared and inspection retained final energy, traits, age, location, and cause. These are observations from one smoke-test run, not calibration or a biological conclusion. No browser console errors were reported.

## Scope and known limitations

- No reproduction, mutation, evolutionary fitness, full charts, or calibration. All founder-only runs under the default lifespan must end by time 200.
- Same-version/runtime reproducibility; strict computed arrival equality with narrowly documented geometric roundoff repair. See `R1-model.md` for numerical assumptions and tick-duration sensitivity.
- Chronological resolution uses straightforward scans with bounding-box filtering, not a spatial index. Achieved fast-forward speed depends on workload; physics steps are never skipped.
- Death records retain the finite founder population for inspection. Review retention before future births can create unbounded histories.
- Canvas renders authoritative snapshots without interpolation. One controlling local browser tab is supported.
- Milestone D has not begun. No commit or push was performed.
