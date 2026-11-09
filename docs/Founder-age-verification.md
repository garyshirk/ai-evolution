# Founder-age initialization verification

This refinement follows F.2 and does not begin F.3. Software version is 0.8.0; the previous approved baseline was cbd0fd6. Manual acceptance testing has passed and the changes are approved for release.

## Automated checks

```sh
.venv/bin/python -m unittest discover -s tests -q
.venv/bin/python -m pip check
git diff --check
```

The complete suite passed **213 tests in 12.078 seconds**, with zero failures/errors/skips on the reference macOS / Python 3.13.5 environment. It includes the previous 199 tests plus 14 founder-age tests. Dependencies and whitespace checks passed; no packages were installed. Pip emits the existing sandbox-cache warning only.

Existing mortality/clock/reporting/Poisson/reproduction fixtures that intentionally assume zero-age founders now explicitly request legacy mode. The default initialization fixture instead checks ages within the configured range. Their original mechanism assertions remain intact; no movement, energy, resource, reproduction, mutation or death implementation was changed.

New coverage:

- New default uniform ages, exclusive upper bound, reproducible seeded age assignments, broad uniform spread, and extreme finite lifespan bounds.
- The independent versioned age stream, unchanged non-age initialization, food, spawn scheduling, biological/global RNG states, same-seed reset/batching and different-seed assignments.
- Legacy initialization and 300-tick complete-state/RNG hashes captured from approved cbd0fd6 before implementation. This exact reference-hash test is restricted to macOS / Python 3.13.5; other environments skip that fixture rather than claim cross-runtime bit identity.
- Staggered exact lifespan deadlines with unchanged positive-energy removal, legacy simultaneous age death, and newborn age zero under uniform founders.
- Correct batch/direct-engine histories, mode metadata and individual current-age export.
- Older 0.6.0/0.7.0 files missing the new field normalize to zero without mutating input data or copying measurement histories. Old/new import, re-export and fresh replay preserve the appropriate mode, seed, initial state and complete configuration.
- Reset validation, applied-versus-pending exports, mode comparison as the only changed parameter, malformed/conflicting configuration rejection, required explicit mode in 0.8.0 exports, and headless default/legacy choices.

## Browser smoke verification

A separate preview was started at http://127.0.0.1:5058/ using the existing virtual environment, preserving the existing server on port 5057 and its in-memory results.

- Single Simulation initially selected Randomized (uniform). At seed 0 and time zero, founder 1 showed age approximately 87.053 and birth time −87.053, position (84.442, 75.795), speed 2.262, vision 5.330, energy 30 and generation 0.
- Selecting All zero (legacy) and Reset changed age/birth time to zero while the displayed position, traits and energy remained identical.
- Batch Experiments showed the same two-option selector, defaulting to uniform. A small two-run, 0.2-unit legacy batch completed; Open in Single Simulation restored zero mode and initial population 3.
- Restoring population 50 and uniform mode, then Reset, reproduced founder 1's original age and other initial values at time zero. The preview was left paused in that state for review.
- No JavaScript console errors were observed. No full 50-seed comparison, calibration or F.3 experiment was run. Existing JSON import/export/replay compatibility is additionally exercised by the automated API tests.

## Manual acceptance checklist

1. Open http://127.0.0.1:5058/ (or launch `.venv/bin/python -m ai_evolution serve --port 5058`). The existing port-5057 process remains the approved old version until explicitly restarted; export its in-memory results before restarting it.
2. In Single Simulation, keep a fixed seed and inspect several founder ages at time zero in uniform mode. Confirm ages lie in [0, max_lifespan), birth timestamps can be negative, energy remains the configured reserve, and founders are generation zero with no parent/offspring history.
3. Reset with the same mode/seed and confirm ages repeat. Switch to legacy and Reset: all founder ages must be zero while positions, traits, headings and food remain unchanged. Switching a pending selector alone should not alter the live run or export.
4. Run small batches in both modes, keeping all other parameters fixed. Check each export's batch and per-run founder_age_mode, then inspect and replay each run; the Single selector and initial state should match.
5. Import a saved approved F.2 batch without founder_age_mode. Confirm configuration inspection/re-export says zero and replay begins with all founders at age zero. The new default must not silently change this old experiment. A missing other required parameter should still reject import.
6. In Compare, select matched-seed current-version legacy/uniform batches and confirm founder_age_mode is the sole configuration change. Expect different demographic outcomes, not identical biological event streams after deaths differ.
7. Verify newborn age zero during reproduction and individual JSON current-age records. For a short, controlled lifespan test, use stationary/cost-free/no-food founders below reproduction threshold and a small lifespan; confirm uniform deadlines are spread while zero-age founders die at the original common deadline.
8. Manual acceptance is complete (see the results below). The full controlled comparison of founder-age effects remains follow-up work.

## Compatibility and scientific limits

See `R1-founder-ages.md`. Saved configurations must use the from_export parser (or the application's import path), rather than treating missing fields as new-experiment defaults. Re-exported legacy files gain an explicit zero field; their measurements and original version metadata are preserved. Earlier app versions may reject new exports. Replay retains the existing exact Python-version check; unsupported engine versions remain analysis-only.

Uniform ages describe initial demographic state only. They do not reconstruct past survival, costs, meals, reproduction or selection; founder reserves and generation are unchanged. Maximum lifespan, energy costs, resource rules, reproduction and mutation are unchanged. Changing age initialization can change ecological outcomes, RNG event consumption after initialization, and extinction probabilities. No favorable outcome or equilibrium interpretation is imposed.


## Successful manual acceptance — November 8, 2026

The user completed and approved manual acceptance testing of version 0.8.0:

- Randomized founders visibly began at different ages within the permitted lifespan.
- Legacy founders began at age zero and aged together.
- A randomized-age single simulation with Food Spawn Rate 1 and Initial Population 20 showed population growth, decline and eventual extinction.
- No unexpected behavior or application errors were observed.

Random initialization removes the artificial common age deadline of the original founder cohort. Severe declines still occurred under low food availability. These observations suggest resource limitations remain relevant, but do not isolate or quantify their causal contribution; additional controlled experiments are needed. Population dynamics and carrying capacity are reserved for F.5 calibration. No additional biological changes, F.3 or F.4 implementation was performed for this acceptance/release step.
