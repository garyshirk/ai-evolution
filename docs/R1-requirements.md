# AI Evolution — Release 1 Requirements

**Document status:** R1 requirements baseline — approved design decisions; implementation defaults pending architecture review  
**Release:** R1 — Individual natural selection  
**Date:** November 3, 2026  
**Intended repository location:** `docs/R1-requirements.md`

## 1. Purpose and scientific scope

R1 is a small experimental laboratory for investigating **natural selection through competition for limited resources**. A population of simple software organisms (“orgs”) moves through a two-dimensional environment, consumes food, expends energy, reproduces with inheritance and mutation, and dies. Population size and inherited traits change over time as consequences of those rules.

R1 is the first of several **separable experiments**, not a commitment to one ever-expanding simulation. Its well-tested components **may be reused as building blocks** in later experiments when appropriate. Later experiments may introduce direct interaction, cooperation, reciprocity, group competition, and cultural evolution. R1 must not implement these later mechanisms.

**Core questions:**

1. Under what resource conditions can a population persist, grow, or go extinct?
2. How do the distributions of inherited speed and vision change under selection?
3. How do energetic tradeoffs alter those distributions?
4. Which apparent patterns are repeatable across random seeds, and which depend on chance?

**Scientific caution:** A run demonstrates behavior *within the specified model*. It does not, by itself, establish how real organisms evolve. Cost equations and environmental assumptions must be visible, documented, and changeable.

## 2. Boundary of R1

### Included

- Individual orgs with energy, age, position, speed, and vision.
- Random initial variation in speed and vision.
- Food randomly distributed and replenished in a bounded 2D world.
- Searching, detecting food, approaching food, and eating.
- Energy expenditure from baseline metabolism, speed-dependent movement, and vision.
- Asexual reproduction with trait inheritance and probabilistic mutations.
- Death from energy depletion **or maximum lifespan**; an emergent, variable population size.
- Interactive browser visualization, experiment controls, time-series charts, and numerical summaries.
- Deterministic seeded runs and automated simulation tests.
- Simulation engine usable independently of the browser UI.

### Excluded

- LLM-powered organisms, learning, memory, or decision-making models.
- Direct social interactions: sharing, fighting, stealing, cooperation, or reciprocity.
- Sexual reproduction, mating, kin recognition, or group selection.
- Evolving energy efficiency (held constant in R1).
- Claims that one strategy is universally biologically optimal.

## 3. Org model

Each org has a unique identifier, a position in the world, current energy, age, **inherited maximum speed**, and **inherited vision radius**. Track its parent and lineage information for inspection and analysis.

| Property | Meaning | Inherited? | Changes during lifetime? |
|---|---|---|---|
| `speed` | Maximum distance moved per simulation time unit | Yes | No |
| `vision_radius` | Distance within which food can be detected | Yes | No |
| `energy` | Current energy reserve | No | Yes |
| `position` | Coordinates in the world | No | Yes |
| `age` | Elapsed simulation time since birth | No | Yes |
| `id` | Distinguishes an org for recording/debugging | No | No |
| `parent_id` | Parent identifier (none for initial orgs) | No | No |
| `generation` | 0 for founders, parent generation + 1 for offspring | No | No |
| `birth_time` | Simulation time of birth | No | No |
| `offspring_count` | Number of offspring produced | No | Yes |

Orgs do not plan, predict, communicate, or explicitly seek reproductive success. They follow local rules. “Evolution” refers to shifts in **population-level inherited trait frequencies** across reproduction and death, not changes to an individual org's inherited traits during its lifetime.

### Initial population

- Begin each new run with a configurable number of orgs.
- Sample each initial org's speed and vision from documented, bounded random distributions using the run's random seed.
- Give initial orgs configurable starting energy and random positions.
- Use identical initial trait-sampling rules in all experiments unless the user changes them.

## 4. World, resources, and time

- The environment is a fixed-size 2D rectangular world.
- Food is represented by discrete consumable items with defined energy values.
- At initialization, food items are placed at random positions. During the run, **new food spawns at random positions** at a constant expected rate per unit of simulated time, independent of org population and current food count (until the cap is reached). Consumed food does **not** regenerate at its previous location.
- A configurable maximum number of simultaneously present food items prevents unlimited accumulation. If the cap is reached, attempted spawning adds nothing; the spawning rule and seeded sampling method must be documented.
- Food supply is finite at any given instant; consumption removes the item.
- Orgs cannot move outside the world; **proposed initial rule:** reflect or redirect movement at boundaries, rather than wrap around. This is an implementation assumption to confirm during architecture review.
- Time advances in fixed simulation steps (`dt`); simulation physics must not depend on browser frame rate.
- All decisions that affect the simulation must use a controlled pseudorandom generator initialized from a user-visible seed.

A **single authoritative update order** must be documented and tested (for example: generate food → sense/move → pay costs → eat → reproduce → remove dead). Avoid behavior that depends accidentally on the order in which orgs happen to be stored; simultaneous food claims must have a documented fair or randomized tie-breaking rule.

## 5. Behavior and energy

### 5.1 Movement

At each time step:

1. If food is within the org's vision radius, target the nearest visible item and **pursue at its inherited maximum speed**, constrained by distance remaining and `dt`.
2. Otherwise, **search at an initial default of 50% of its inherited maximum speed**, following a persistent heading with occasional randomized turns. The search fraction is a documented configuration parameter, initially kept out of the main UI.
3. Eating occurs when an org comes within a small, fixed consumption radius of an available item.

The random-search movement rule should avoid unrealistic frame-by-frame jitter; use a simple persistent heading with occasional random turns. No recognition of other orgs is required.

### 5.2 Energy budget

- Baseline metabolism drains energy every step, including when stationary.
- Movement drains energy whenever an org moves.
- Movement cost depends on **actual distance moved and actual movement speed**. Maximum inherited speed influences energy expenditure through behavior: faster orgs search and pursue faster, not because an unused capability is charged automatically.
- Greater vision radius imposes a continuous metabolic cost (one possible model uses a quadratic vision term).
- Eating adds the consumed food item's energy.
- Reproduction transfers or consumes energy under a specified rule.
- Orgs die and are removed when energy reaches zero or below **or** their age reaches a fixed, configurable maximum lifespan. Lifespan is the same for all orgs in R1 and is **not** an evolving trait. Number of offspring does not itself trigger death.

**Proposed initial cost model (modeling assumption, not a biological law):** For a simulation step of duration `dt`, actual distance moved `d`, actual movement speed `u` (not inherited maximum speed), and inherited vision radius `v`:

\[
E_{\mathrm{cost}} = dt\left[b + k_v\left(\frac{v}{v_{ref}}\right)^2\right]
+ k_m d\left(\frac{u}{u_{ref}}\right)^2
\]

Here `b` is baseline metabolic cost per unit simulated time, `k_v` is the vision upkeep coefficient, and `k_m` is movement energy cost per unit distance at reference speed `u_ref`. Reference values keep sliders interpretable. No distance traveled means no movement cost, while baseline and vision upkeep still apply. The movement-cost relationship is **quadratic in velocity per unit distance** (thus faster travel can be much more expensive); this is a deliberately simple, adjustable assumption rather than a universal biomechanical fact.

**Behavior matters:** in search mode, `u` is initially 0.5 × inherited max speed; in pursuit mode it is up to 1.0 × inherited max speed. Use actual traveled distance (including steps truncated by reaching food or a boundary) to calculate costs; the model must not charge for movement that did not occur. If a motion step uses different speeds, accumulate energy cost for each segment rather than incorrectly applying one speed to the entire step. Do not hard-code preferred speed or vision values: any observed optimum must emerge from the benefits/costs of the environment.

Energy values and expenses must use consistent units. An energy accounting diagnostic should make it possible to reconcile energy gained, energy spent, and energy transferred to offspring, subject to the model's declared rules.

## 6. Reproduction, inheritance, and mutation

- Reproduction is **asexual**: one parent produces one offspring.
- If a living org exceeds the configurable reproduction energy threshold, it may reproduce according to a clearly specified per-step rule.
- Reproduction has a real energetic cost. The offspring starts with an allocated energy reserve; the parent loses at least the energy transferred plus any configured reproduction overhead. Energy must not be created by reproduction.
- Offspring receive inherited speed and vision independently from the parent.
- Each inherited trait has an **independent configurable mutation probability**; most offspring may inherit traits unchanged.
- When a mutation occurs, its change is randomly positive or negative, with configurable magnitude or distribution. Mutations do not “know” what is advantageous.
- Trait values have explicit minimum and maximum bounds for numerical and modeling stability; use a documented policy for mutations that reach a bound.
- Place the offspring near the parent, with any displacement governed by the seeded random generator.

**Suggested initial mutation settings (tunable placeholders):** 5% probability **per trait, per birth**; small centered perturbations scaled to each trait's allowable range. The exact distribution and numeric ranges must be approved in the architecture proposal.

R1 **requires a maximum lifespan**, measured in simulated time rather than number of reproductions. Age-based death and energy-based death must be distinguishable in diagnostics. The initial lifespan value is to be proposed during architecture review and should be adjustable in advanced configuration.

## 7. Experimental controls

The browser UI must provide:

- **Start / Pause / Resume / Reset** (reset to the same seed and same parameters for exact replay).
- **Simulation playback speed** control (e.g., 0.25×, 1×, 5×, 20×, as practical), which changes how rapidly simulated steps are processed, **not** org max speed, energy equations, `dt`, or model outcomes. Include a **single-step** control while paused; fast-forward may skip rendering frames but must not skip physics steps.
- Editable random seed; option to generate a new seed.
- Initial population size.
- Food replenishment rate and food energy value (or an equally clear resource-availability control).
- Speed-cost and vision-cost multipliers.
- Mutation probability and mutation magnitude (can share initial controls for speed and vision if individual settings remain possible in the engine).

Keep the **initially visible adjustable controls deliberately small**: simulation playback speed, seed, initial population, food spawning rate, and speed/vision cost coefficients are priorities. Other model settings (food energy, food cap, mutation rate/magnitude, lifespan, search speed fraction, starting energy, reproduction threshold, etc.) must exist in a documented configuration or compact Advanced panel rather than crowding the main interface. Codex should propose a coherent minimal control set at architecture review; exact UI exposure is subject to review.

**Parameter-change policy:** To make experiments interpretable, changing foundational parameters should require a reset/new run in R1, rather than silently altering the rules mid-run. The interface should distinguish a paused run from a newly initialized experiment.

## 8. Visualization and reporting

### Live 2D view

- Display individual orgs and food items on a visible map of the world.
- Animate movement and make births and deaths observable at normal speeds.
- Distinguish orgs from food; optional color or size encoding for one trait if it remains easy to interpret. Avoid permanent overlapping trait overlays that obscure the world.
- **Org inspection:** support clicking an org (at minimum when paused) to view its live state and inherited traits: ID, parent ID, generation, age, energy, max speed, actual movement mode/speed, vision radius, and offspring count. Prefer selection during playback as well if straightforward. Highlight the selected org and optionally show its vision radius as a circle; do not draw every org's radius by default.
- Allow practical performance at the default population size, without making animation frame rate determine simulation outcomes.

### Numerical displays and charts

- Current live population, number of births, number of deaths (ideally by cause: starvation/age), simulation time/step, and seed.
- Population size over time.
- Mean inherited speed over time.
- Mean inherited vision radius over time.
- Ideally include trait spread/distribution (e.g., histogram or range) in R1; if this materially increases scope, treat it as the first visualization enhancement.
- When the population is extinct, graphs and metrics must continue to display the completed run sensibly.

### Exports

Export at least experiment parameters, seed, and time-series summary data to a simple reusable format (e.g., CSV and/or JSON), enabling subsequent comparison and analysis. No backend database is required for R1.

## 9. Reproducibility and software architecture

- Implement the simulation as a self-contained engine, independent of rendering or browser state. Organize components for **selective reuse by future, independent experiments** without speculative infrastructure for unbuilt features.
- Separate model/data types, simulation stepping, parameter configuration, and metrics collection.
- Provide a headless execution path that can advance a run by N steps without opening the browser.
- Given the same engine version, parameters, seed, and step count, headless runs must produce the same outcomes (within any explicitly documented platform/numeric constraints).
- Prefer a lightweight browser UI architecture and minimize dependencies. **Python is the selected initial simulation-engine language**, but the precise UI stack is deferred to the architecture proposal.
- Organize the code so future cooperation experiments could reuse basic engine components without making R1 depend on those future experiments.

## 10. Verification and acceptance criteria

R1 is acceptable when all of the following are demonstrably true:

1. **Run control:** A user can start, pause, resume, single-step, and reset a simulation in the browser; changing playback speed does not change results at the same number of physics steps.
2. **Resource behavior:** Orgs move, detect reachable food, consume it, and gain the specified energy.
3. **Energy and death:** Orgs lose energy under documented time-, distance-, velocity-, and vision-dependent rules and die at zero energy **or** maximum age. Tests check search versus pursuit speeds, actual-distance costing, age-based death, energy calculations, and reproduction transfers.
4. **Birth:** Eligible orgs reproduce; new orgs start with the specified energy and location rules.
5. **Inheritance:** Without mutation, offspring speed and vision exactly match the parent.
6. **Mutation:** With mutation enabled, positive and negative changes occur within bounds, at approximately the configured frequencies over sufficiently many samples.
7. **Natural population dynamics:** Population can grow or decline, and extinction is possible; no forced constant population size.
8. **Cost sensitivity:** Automated comparisons show that changing cost coefficients changes the simulated energy budget as specified; don't require a particular evolutionary outcome from one stochastic run.
9. **Metrics and inspection:** The app displays population and trait trends corresponding to engine data; a user can pause and click a living org to inspect its energy, age, inherited traits, and lineage.
10. **Reproducibility:** The same initial seed and settings produce the same headless trajectory across repeated runs.
11. **Isolation:** The headless engine works and is testable without a UI.
12. **Documentation:** Model equations, update order, defaults, modeling assumptions, and known limitations are recorded.
13. **Food supply:** Fixed-rate random-location spawning and a food cap behave as specified; consumed items do not automatically regenerate in place.
14. **Calibration:** Automated headless multi-seed runs produce survival, extinction, births/deaths, population, and trait summaries. A documented baseline set of defaults sustains populations in a useful fraction of runs while **not guaranteeing survival**. Report actual calibration outcomes, including unsuccessful settings; do not bias physics to force stability.

Tests should cover edge cases such as no food, zero orgs, near-zero energy, extreme trait limits, multiple orgs reaching one food item, and successive births. Include a short manual smoke test of the browser UI.

## 11. Suggested initial experiments (not hard-coded outcomes)

These are experiments to run *after* implementation, not results to guarantee:

- **Calibration / baseline:** Search for useful starting conditions with repeated seeded headless runs. Distinguish viability, population stability, and detectable selection; observe population and trait trajectories under proposed defaults.
- **Scarcity:** Reduce food replenishment while holding other parameters and seed constant.
- **Expensive vision:** Increase vision cost and compare trait trajectories against baseline.
- **Expensive movement:** Increase speed cost and compare trajectories.
- **Mutation off/on:** Compare the ability to change inherited trait distributions without and with new mutations.
- **Repeatability:** Run several different seeds for a given parameter set and compare the range of outcomes.

Interpretation must distinguish short-term population change, selection on inherited traits, mutation, chance, and artifacts of model design.

## 12. Open implementation choices for Codex architecture review

Codex should **propose**, not silently decide, the following before application code is written:

1. Browser UI stack and how it communicates with the Python simulation engine.
2. Concrete default parameter values, trait bounds, world dimensions, time-step size, and org/food counts.
3. Implementation details for the agreed **distance × (actual speed / reference speed)²** movement cost and quadratic vision upkeep; propose and justify coefficient defaults and units.
4. Food spawn timing for constant expected rate, initial food, maximum food count, food claim resolution, and update ordering.
5. Random-search heading changes, search fraction default (50%), pursuit at max speed, and boundary behavior.
6. Reproduction eligibility and division of parent/offspring energy.
7. Mutation distributions and trait-bound handling.
8. Data collection cadence, charts, org-inspection UI, playback speed implementation, and export format.
9. How to run tests and the headless simulation locally.
10. Proposed default **maximum lifespan**, and an efficient calibration procedure using repeated seeds and reported survival/trait metrics.
11. A deliberately limited initial set of visible UI sliders; where other configurable parameters will reside.

Review these choices for clarity, internal consistency, and whether the experiment's outcomes are actually interpretable. Do not start coding until the architecture and requirements are approved.

---

## R1 completion definition

A user can watch a simple living population compete indirectly for food, inspect individual orgs, adjust tradeoffs and playback speed, reproduce experiments from seeds, and measure whether inherited speed and vision change over time—without any direct social interactions or LLM agents.
