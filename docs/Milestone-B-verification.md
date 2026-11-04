# Milestone B verification

## Automated checks

Environment: Python 3.13.5, Flask 3.1.2, existing project `.venv`.

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m pip check
```

Result: all 49 tests passed; no broken requirements. The 29 Milestone A tests remain, with the unchanged-organism assertion revised to permit authorized movement while preserving checks for unchanged food, energy, traits, lineage, and population. There are 11 movement tests and 9 Flask/API tests.

Coverage includes persistent search, speed fraction, turn probability, exact wall endpoints, multiple reflections, corner reflection, zero speed, fixed dt, seed replay/reset, canonical organism ordering, overlapping organisms, world bounds, API pause/resume/single-step/reset, stale/duplicate request rejection, empty populations, invalid inputs, static resources, and equivalent single/batched/headless execution.

Playback equivalence is checked at equal physics-step counts using different request batch sizes; wall-clock delivery times are deliberately not model inputs.

## Local browser smoke test

Started `.venv/bin/python -m ai_evolution serve --port 5050` and opened `http://127.0.0.1:5050` in the in-app browser.

Verified:

- Page initializes paused with 50 organisms and 200 food items.
- Single step advances exactly one tick (time 0.1).
- Organism selection displays position, inherited traits, current search speed, constant energy, age, parent/generation, and offspring count.
- 20× playback advances the world; Pause preserves the resulting state and restores single-step availability.
- Seed 42 takes effect through Reset; the next single step displays the corresponding new organism state.
- Selected vision overlay and distinct food/organism rendering are visible.
- The layout fits the inspected desktop viewport without horizontal overflow.

Overlap selection has a deterministic engine test; the UI additionally provides repeated-click cycling and a dropdown containing every organism, so occlusion does not prevent inspection. Full browser automation across viewport sizes is not part of this milestone.

## Scope and limitations

Canvas draws authoritative tick snapshots without interpolation. At slow playback, visible movement occurs in discrete fixed ticks. Background-tab throttling and local throughput can lower achieved playback speed, but never skip physics steps. The single-run local server is intended for one controlling browser tab.

No Milestone C mechanisms, statistical charts, calibration, commits, or pushes were performed.
