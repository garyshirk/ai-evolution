# Founder-age initialization — software 0.8.0

This is an initialization refinement following F.2, not F.3. It allows controlled comparisons of a synchronized founder cohort and a cohort with distributed remaining lifetimes. It does not establish that either initialization is an equilibrium population or a better biological model.

## Configuration and interface

`SimulationConfig.founder_age_mode` accepts exactly:

- `uniform`: default for new experiments. Ages are uniform over zero inclusive through max_lifespan exclusive.
- `zero`: legacy initialization. Every founder begins at age zero.

Both Single Simulation and Batch Experiments offer a single Founder ages selector, labeled Randomized (uniform) / All zero (legacy). Single Simulation changes apply on Reset; Start/Resume preserves the current experiment. Batch parameters are captured at Run Experiment. Opening a completed/imported run in Single Simulation restores the full applied configuration, including the age mode and Initial Population, at time zero.

Headless usage:

```sh
.venv/bin/python -m ai_evolution headless --seed 42 --steps 100 --founder-age-mode uniform
.venv/bin/python -m ai_evolution headless --seed 42 --steps 100 --founder-age-mode zero
```

No configurable distribution editor, age-dependent costs, additional evolving trait or new organism behavior is introduced.

## Representation and unchanged mechanisms

Simulation time begins at zero. For a founder with initial age A, birth_time is −A (zero is stored as positive 0.0). Existing age_at(t) = t − birth_time therefore yields A at initialization. Founder generation remains zero, parent remains null, founder lineage remains its own identifier, offspring_count remains zero, and current energy remains starting_energy. Initial statistics still report only newly initialized reserves and zero experiment births/deaths.

The existing death deadline is birth_time + max_lifespan, so a founder with age A has max_lifespan − A time remaining. The same event resolver handles exact sub-tick death, energy accounting, competition and extinction. No death code or lifespan value changes. Newborn birth times remain actual tick-end times, and newborn age is zero. Placement, movement, sensing, food, energy costs, reproduction, inheritance and mutation are unchanged.

Random ages do not reconstruct historical food intake, expenditures, reproduction, mutations or survival selection. In particular, old founders do not receive less starting energy or fabricated offspring histories. This intentionally isolates initial age distribution while leaving other initial state fixed.

## Seeded independence

On reset, initialization creates a local age-only generator:

`random.Random("ai-evolution:r1:founder-ages:v1:" + str(seed))`

The versioned domain string is part of the reproducibility convention. Python's deterministic string seeding is used; process-randomized hash() is not. In organism-ID order, uniform mode draws one U in [0,1), sets A = U × max_lifespan, and bounds rounding with min(A, nextafter(max_lifespan, 0)). This keeps the maximum exclusive even at floating-point edge cases. As elsewhere in the model, distributions use finite-precision pseudorandom values.

Legacy mode draws no age values. The age generator does not consume or reseed the existing biological RNG or the module-global random state. With identical seeds and other settings, positions, traits, headings, food, initial spawn scheduling, reserves and biological RNG state are identical between modes at time zero. Common prefixes of founder IDs retain common age fractions, and the same seed across environmental settings retains the same age fractions.

Different remaining lifetimes subsequently change ecological events and may change which biological draws occur. Identical future random-event sequences or outcomes between age modes are neither expected nor imposed. Reset and identical seeded configurations reproduce the same age assignments and trajectories under the supported runtime.

## Exports, imports and old experiments

Software version is 0.8.0. Existing JSON schema version 1 gains the additive `founder_age_mode` configuration field; batch and every per-run configuration record it. Single/headless reports include it as well. Individual living-organism exports already contain current age, which now includes initial founder age. CSV time-series columns are unchanged.

Saved-configuration parsing is distinct from new configuration construction:

- `SimulationConfig()` / `SimulationConfig(**parameters)` use the new uniform default when no age mode is provided.
- `SimulationConfig.from_export(saved_parameters)` supplies zero when the field is absent, preserving original experiment semantics.

The experiment library accepts old complete configurations missing only this new field, validates them as zero-age cohorts, and normalizes batch/per-run metadata to explicit zero. Large measurement arrays are reused, not copied or recalculated. Original run outcomes, measurements, seeds and source versions remain unchanged. Re-exporting a migrated library entry includes the explicit zero field; the source input dictionary is not mutated. Missing older required fields still fail validation. Batch/per-run modes must agree. A 0.8.0 export missing its mode is rejected as incomplete rather than silently guessed.

Known 0.6.0/0.7.0 reports replay in zero mode; 0.8.0 supports either mode. Exact Python version matching and the existing application population limit are still required. Unsupported versions remain analyzable under the existing compatibility policy, but exact replay is disabled with an explanation. An earlier engine version claiming uniform ages is not exact-replay-compatible. Older application versions may reject the added field/new software version; use the updated application to load new exports.

The pre-change zero-mode trajectory is checked against state and RNG hashes captured from approved commit cbd0fd6 before implementation, on the reference Python/macOS environment. Cross-platform/runtime bit identity remains outside the model's existing guarantee.

## Controlled comparisons and limits

Use matching seeds, duration and all configuration fields except founder_age_mode when isolating this effect. The Compare view includes the field automatically and preserves paired-seed analysis. Prefer two new 0.8.0 batches (zero and uniform) to avoid version differences in metadata; an imported old batch can still be analyzed/replayed as its original zero cohort.

Random initial ages stagger the founder lifespan deadlines, but resource-driven deaths, bottlenecks and extinction can still occur. Subsequent population dynamics are expected to differ because the initial demographic state differs. No calibration, guaranteed survival, fitness estimate, formal significance test or claim of causal evolutionary adaptation is included. The full 50-seed founder-age comparison remains user-driven follow-up work.
