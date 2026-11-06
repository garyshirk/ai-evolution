# Milestone D verification

Date: November 6, 2026. Environment: Python 3.13.5, Flask 3.1.2, existing `.venv`. No dependencies were installed or updated.

## Automated checks

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m pip check
```

Initial implementation result: **105 tests passed**, including all 81 prior tests and 24 new reproduction/mutation/API tests. That suite ran in 6.438 seconds; dependency checks found no broken requirements. See the final-refinement results below for the current complete suite.

Prior checks retain their invariants. The resource-free founder test's name now describes its actual premise rather than saying reproduction is globally absent; CLI/page milestone expectations and the ledger helper were updated for the authorized new feature.

New checks cover strict >60 eligibility, affordability and a positive parent remainder, parent/child energy and overhead, one birth per parent per tick, newborn inactivity and inability to eat leftover food in its birth tick, exact inheritance, IDs/lineage/generations/birth times, offspring placement with reflected boundaries, age/starvation before reproduction, costs/meals before threshold evaluation, parent/offspring deaths, seeded reset and batching, storage-order independence, and headless/API equivalence with births.

Mutation tests verify independent per-trait settings, both signs, reflected limits including multiple overshoots, zero probability/magnitude behavior, overflow validation, and fixed-seed frequencies over 20,000 paired samples. Frequency, joint-event, and sign tolerances use expected sampling variation rather than a single-run evolutionary outcome.

## Headless smoke observations

Three seed-0 runs used the unchanged initial defaults, except for the resource reductions named below. Each advanced 1,000 ticks (100 simulated time units), with summaries sampled every 200 ticks. These are short smoke tests, not Milestone F calibration or evidence of long-term stability.

| Setting | Population at time 20 | Population at time 100 | Births at time 100 | Deaths at time 100 | Highest generation |
| --- | ---: | ---: | ---: | ---: | ---: |
| Defaults, food rate 8 | 95 | 181 | 132 | 1 | 4 |
| Replenishment off, initial food 200 | 75 | 67 | 28 | 11 | 3 |
| No initial food or replenishment | 50 | 29 | 0 | 21 | 0 |

The replenishment-off run reached a sampled population peak of 78 at time 60 before declining. Default mean inherited speed/vision at time 100 were approximately 2.727 / 8.300. These population means can change through selection, chance, and mutation; this check does not disentangle them or establish an optimal trait value. Energy-ledger residuals across the samples remained below 1e-8 energy units in absolute magnitude, consistent with accumulation of floating-point rounding error.

Births occurred readily under defaults; no immediate population explosion or extinction before reproduction was observed. Population grew more than threefold over this short baseline horizon. Stability, memory use, and eventual survival require later measurements; no parameters were tuned to force an outcome.

The existing headless CLI remains covered by subprocess tests and now accepts shared mutation probability/magnitude options. Engine/Python versions, parameters, summaries, transferred reserves, reproduction expenses, and mutation counts are present in JSON output.

## Browser smoke test

Started `.venv/bin/python -m ai_evolution serve --port 5052` and opened `http://127.0.0.1:5052` in the in-app browser.

Verified:

- Live births, population growth, highest generation, and inherited-trait means.
- Newborns appear in the organism dropdown; existing selected organisms remain inspectable as births occur.
- Parent ID, generation, founder lineage, birth time, current age, inherited traits, and offspring counts are displayed.
- Advanced speed/vision mutation probabilities and magnitudes apply through Reset; playback remains independent of physics.
- With mutation disabled in the browser smoke run, org 51 and parent 17 displayed identical speed (2.622) and vision (6.522), with child generation 1 and founder lineage 17.
- After restoring default mutation settings and resetting seed 0, 22 single steps reached the first birth at time 2.2. Org 51 had age zero, energy 25, idle mode and zero speed, parent 17, founder lineage 17, and generation 1. The preview was left paused at this state for review.
- No browser console errors were reported. Birth highlighting is visual only and uses the first 0.5 simulated time units of offspring age; it consumes no random draws.

## Scope and remaining concerns

No approved biological rule was changed. Newborn heading is seeded and uniform, and disk placement is uniform by area. Diagnostics distinguish offspring transfers from overhead; population energy is never increased by adding a child's reserve.

The death archive remains in memory for inspection. With births enabled, it can grow without bound in long runs. Large populations also increase the cost of the straightforward event scans and full snapshots. No artificial population cap, forced survival, or silent history truncation was introduced. Address history/performance before extensive long-run analysis.

No full evolutionary charts, explicit fitness score, Milestone E work, or extensive calibration was performed. No commit or push was made.

## Final refinements and additional verification

The initial 105-test implementation was extended with `test_d_refinements.py` (13 tests). The complete suite now passes **118 tests**, with the final run completing in 8.294 seconds. No new dependencies or biological mechanisms were introduced. Default Initial Food remains 200 and Food / time remains 8.

### Heading independence

Reviewed the existing birth implementation: newborn heading already uses a separate `rng.random() * tau` draw after placement. It is not inherited. Added tests that reproduce the expected seeded draw, change the parent's heading without changing the child's draw, and deliberately allow an independent draw to equal the parent's heading. No artificial directional separation or heading-rule change was needed. Parent and child may subsequently pursue the same food.

### Responsive environment

The environment now occupies a viewport-fitted pane. Its canvas scales by the smaller available width/height factor; model dimensions and aspect ratio remain unchanged. Controls, statistics, Advanced settings, and inspection scroll in a separate pane. Narrow layouts stack the environment above scrolling controls. Resizing runs only renderer geometry; it makes no model calls or random draws.

Browser viewport checks in the in-app browser:

| Viewport | Canvas size | Entire environment visible | Page scrolling |
| --- | --- | --- | --- |
| 1280 × 640 | approximately 451 × 451 | Yes | None |
| 1024 × 600 | approximately 403 × 403 | Yes | None |
| 1440 × 800 | approximately 605 × 605 | Yes | None |
| 390 × 700 | approximately 324 × 324 | Yes | None |

Verified canvas picking on org 1 after resizing, its selected vision overlay, distinct food rendering, and usable inspection. Scrolling controls did not move the environment or page. These checks test viewport dimensions in the in-app browser, not a separate native Safari session.

### Fractional replenishment and Initial Food

- Engine tests used rates 0.05, 0.1, 0.5, and 1.0 over 1,000 simulated units per seed for ten fixed seeds. Aggregate expected spawn counts are 500, 1,000, 5,000, and 10,000. Observed counts were within five Poisson standard deviations, without hitting the cap. This verifies average arrival rate, not guaranteed uniform arrivals in individual short runs.
- Zero rate schedules no arrivals. Fractional rates replay identically under single and batched stepping.
- API tests cover Initial Food 0, 5, 10, 20, 50, and 200 crossed with rates 0, 0.05, 0.1, 0.5, and 1.0. Noninteger, negative, boolean, string/null, and over-cap counts are rejected atomically; the configured cap is respected. Same-seed initial positions replay and a different seed changes the distribution.
- Browser checks set Initial Food to 10 with each listed rate, then Reset and reload. Values persisted, displayed food count was 10 at time zero, and no errors appeared. The 0.5 spinner step does not prevent manually entering 0.05 or 0.1 because reset validation accepts real-valued rates independently of spinner increments.

### Mutation and complete reproducibility

- Tested probabilities 0, 0.05, and 1.0 crossed with magnitudes 0.05 and 0.1 over 5,000 paired samples per configuration. Verified marginal and joint frequencies, independent per-trait events, both signs, full-range scaling, and reflected limits at both magnitudes. No mutation-rule changes were necessary.
- In the browser, probability 1 for both traits and magnitude 0.1 produced org 51 at time 2.2 with speed 1.961 and vision 7.835, compared with parent 17's speed 2.622 and vision 6.522 (display-rounded). Speed decreased and vision increased, within their full-range perturbation bounds. The inspector displayed the offspring's lineage, age zero, and energy 25 correctly.
- A complete-trajectory test compares identical initial states and subsequent snapshots at several step boundaries across repeated seeds, single stepping, batches, reversed organism/food storage order, and two browser API schedules. It exercises replenishment, movement, eating, births, mutations, age deaths, archives, population trajectories, and final reset replay. Playback scheduling remains external to physics.

The existing long-run history-retention and calibration limitations still apply. Milestone E, commits, and pushes remain outside this task.
