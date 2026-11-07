# R1 software architecture

Date: November 4, 2026  
Status: Approved architecture, including final meal, competition, and non-collision conventions. Milestones A through E and F.1 are authorized; F.2–F.5 require separate authorization.

## 1. Scope and decision authority

R1 models individual natural selection among rule-based organisms competing indirectly for food. It excludes LLM organisms, learning, social interaction, cooperation, sexual reproduction, and group selection. The Python engine must work without the browser.

Read this document with `R1-requirements.md` and `AGENTS.md`. The user's architecture review approves the Python/Flask/JavaScript/Canvas stack, initial numerical assumptions subject to calibration, reflected world boundaries, reflected trait mutations, the reproduction budget below, and automatic pause at extinction. The review additionally requires:

- Detect food encounters along the entire actual movement path.
- Stop life and movement immediately at zero energy; an organism cannot borrow energy to reach food.
- Award food to the first living organism to arrive. Resolve exact arrival-time ties using the seeded generator, without storage-order advantage.
- Calibrate toward approximately 80–90% population survival across seeds over 1,000 simulated time units, while separately evaluating population stability and observable evolutionary change.
- Consume at most one food per organism per tick; stop movement after eating until the next tick.
- Resolve simultaneous conflicts with seeded randomness, including random ordering of multiple food items, without processing-order advantage.
- Organisms have no physical collisions. They may overlap or cross paths; they do not detect, block, push, or respond to one another. Competition occurs only through shared food consumption.

These decisions replace the earlier proposal's endpoint-only consumption, whole-tick debit before eating, randomized claims regardless of arrival time, and 30–80% calibration target. This document does not change the requirements file.

## 2. Technology and dependencies

- **Engine:** Python 3.13; standard-library `dataclasses`, `math`, `random`, `json`, `csv`, `argparse`, and `unittest`.
- **Local web server:** Flask, the sole direct runtime dependency, with its transitive dependencies recorded when installed. Serve static files and a small same-origin JSON API on localhost.
- **Browser:** HTML, CSS, plain JavaScript modules, Canvas 2D, and `requestAnimationFrame`. No frontend framework or Node build process.
- **Storage:** One active in-memory run; JSON/CSV exports. No database, accounts, or complete historical organism archive.
- **Tests:** Standard-library unittest and Flask's test client. No mandatory scientific or simulation framework.

Record tested dependency versions during implementation. Keep all Flask imports outside the engine. Do not introduce a generic agent framework, plugin registry, or speculative future-experiment abstractions.

## 3. Engine components

Use data classes for state and small functions for model rules:

| Component | Responsibility |
| --- | --- |
| `SimulationConfig` | Immutable, validated parameters and units; separate per-trait mutation settings |
| `Traits` | Inherited maximum speed and vision radius |
| `Organism` | ID, position, heading, energy, birth time, parent ID, founder lineage ID, generation, offspring count, current mode and speed |
| `Food` | Stable ID, position, energy value |
| `WorldState` | Living organisms, available food, integer tick index, current simulation time, deterministic ID counters |
| `Simulation` | Owns configuration, state, seeded random generator, and authoritative advancement |
| `Motion` / implicit segments | Current constant velocity and planned stop; the event resolver splits actual paths at each wall, stop, meal, or death |
| `MetricsCollector` | Time-series samples, cumulative events, energy accounting |

Modules:

- `movement.py`: sensing, search heading changes, motion plans, reflected segments.
- `encounters.py`: swept-path intersection and chronological event resolution.
- `energy.py`: rates, time-to-depletion, exact segment expenses, diagnostics.
- `resources.py`: initial food and scheduled arrivals.
- `reproduction.py`: eligibility, energy transfer, inheritance, mutation, placement.
- `simulation.py`: fixed-tick coordination, death, births, reproducible ordering.
- `metrics.py`, `exports.py`, `calibration.py`: reporting and headless experiments.

Death is an explicit transition with a cause and timestamp, not a separate class hierarchy. Snapshots and inspection are read-only and never consume random numbers. Derive age from current time minus birth time rather than repeated floating-point additions.

## 4. Fixed ticks with chronological events inside each tick

### 4.1 Why both are needed

The decision interval remains fixed at `dt = 0.1`. Physics is independent of browser frames. Within each tick, solve continuous movement, costs, food encounters, and death at their event times. Fixed ticks must not postpone starvation or award food after the organism should have died.

Use integer tick indices to derive tick boundaries as `index * dt`. Maintain a sub-tick event clock only while resolving the interval. Event times are simulated times, never wall-clock times.

### 4.2 Authoritative sequence

1. At tick start, exclude any already-dead organisms. Take the current sensing snapshot. In canonical organism-ID order, choose nearest visible food, or update a persistent search heading with the seeded turn rule.
2. Construct piecewise linear motion plans for this tick, including wall reflections and any planned stop upon reaching the target's consumption circle.
3. Resolve the interval chronologically. Candidate events are food spawning, food entry, starvation, maximum-age death, path-segment transitions, and the tick boundary. Advance all living organisms only to the next event time, integrating movement and energy over that elapsed interval.
4. At an event timestamp, remove deaths first, process food spawns second, and resolve food consumption third. Reflections and segment transitions define the outgoing path at that same time; they take no time and spend no energy themselves.
5. Recompute affected future candidates after energy gains, food removal, path changes, or deaths. Never rely on a stale depletion prediction after eating.
6. At tick end, reproduce eligible survivors once at most, add offspring, then collect scheduled metrics. Newborns first sense, move, and eat on the next tick.

Events exactly at the tick endpoint are resolved before reproduction, once only. The next tick starts from the resulting state. Initial food is present before the first sensing phase; initial overlaps can produce encounters at time zero. Start with zero organisms as a terminal empty experiment.

For simplicity, the first implementation may recompute candidates from current state after each event rather than maintain a complex priority queue with invalidation. Benchmark before optimizing. All organisms must advance on the same event clock; never finish one organism's entire tick before processing another's.

### 4.3 Decision cadence and meal policy — approved conventions

Sensing and random heading decisions happen once per tick. No mid-tick replanning when a competitor removes the chosen target or food newly enters vision. The original motion plan remains until next tick unless death or successful feeding stops it.

Retain the earlier proposal's limit of **one food item per organism per tick**. On the first successful meal, stop movement for the remaining tick, continuing baseline and vision expenses. A losing competitor continues its original plan; upon reaching its planned target-circle entry point it waits until next tick, even if the target is gone. It can still encounter other available food earlier along that path.

These conventions are approved. Organism paths do not interact physically; only shared food availability couples their outcomes.

## 5. Swept-path encounters and first-arrival competition

### 5.1 Geometry

An organism is a point for model geometry; food is consumable within fixed radius `r = 0.75`. Rendered body sizes do not affect physics. For every eligible living organism and available food, inspect every applicable straight segment of its reflected path, including incidental food that was not its target.

For segment position `p(t) = p0 + velocity * t`, solve the first entry into the closed disk:

`|p0 + velocity * t - food_position|^2 <= r^2`

Use the earliest valid entry time in the segment's time interval. An organism already inside the disk has entry time equal to the current time; stationary organisms can eat overlapping food. Tangency counts as contact. Handle zero velocity explicitly. Clip roots only to valid segment limits using a documented numerical roundoff policy. Split at every reflected wall contact, including both velocity components at a corner. Never substitute the straight chord between tick endpoints for the reflected path.

A food item spawned partway through a tick exists only from its arrival time onward. Evaluate encounters from that time, including organisms already within its disk. Never make it available earlier in the tick.

### 5.2 Competition and simultaneous encounters

- Compare arrival times globally, not in organism processing order.
- The earliest eligible arrival consumes the item immediately and receives its energy at that time.
- If all earliest claimants die at that time, exclude them and consider later surviving arrivals.
- Exact arrival ties on one food use a uniform seeded choice from candidates sorted by ID. Consume no tie-breaking draw for a singleton.
- If several food items have simultaneous competing arrivals, process tied food IDs in a seeded random permutation. Re-evaluate eligibility after each award because an organism can eat only once per tick.
- An organism overlapping several foods at the same instant can therefore receive only one. Once a tie is resolved, do not repeatedly redraw it.

Random ordering of genuinely simultaneous food events is explicit model randomness, not an iteration artifact. With distinct arrival times, no random draw determines ownership.

### 5.3 Numerical equality

Use double-precision floating-point event times with strict chronological comparisons. Exact ties mean equal computed event times; do not round all arrivals into broad time bins. Candidate construction must use consistent formulas and canonical ordering. Geometry tolerances are confined to intersection roundoff and segment endpoints, not a general tie window that could favor a later arrival.

Mathematically symmetric paths can differ by floating-point roundoff. Add symmetric geometry tests and document this platform limitation. Do not promise arbitrary-precision event ordering. If tests reveal materially unfair outcomes, revise the numerical policy explicitly before release rather than silently adding a large epsilon.

## 6. Continuous energy and immediate death

For inherited vision `v` and constant segment travel speed `u`:

`upkeep_rate = b + kv * (v / vref)^2`

`movement_rate = km * u * (u / uref)^2`

`total_rate = upkeep_rate + movement_rate`

For elapsed segment duration `h`, actual distance is `u * h`; movement expense is equivalently `km * distance * (u / uref)^2`. A truncated approach uses its actual travel speed while moving, not distance divided by the full tick duration. Stationary time has zero movement expense and positive upkeep under the starting defaults.

If the rate is positive, time to energy depletion is `energy / total_rate`. Compare this against the next geometric event, food spawn, age limit, and tick end. At depletion:

- Move only as far as available energy permits.
- Debit only expenses up to that instant and set energy to zero.
- Remove the organism immediately; it cannot eat or reproduce.
- Record timestamp, position, and starvation cause.

With zero expense rate, depletion time is infinite for positive energy. Nonpositive starting energy means immediate death; configuration should normally require positive founder and offspring reserves.

Food can rescue an organism only when arrival precedes depletion and it still has strictly positive energy. An arrival exactly at depletion does not rescue it. Maximum-age death also wins over a simultaneous meal or reproduction. If starvation and age occur at exactly the same time, record starvation as the primary cause and a simultaneous-age flag so primary death totals remain exclusive.

Age death occurs exactly at `birth_time + lifespan`, even within a tick. It removes any remaining reserve. Eating increases energy immediately and changes all later depletion predictions. No costs accrue after death. No temporary negative energy, energy borrowing, or whole-tick debit followed by retrospective rescue is allowed.

Energy ledger:

`living energy = initial energy + consumed food energy`
`                - baseline costs - vision costs - movement costs`
`                - reproduction overhead - reserves removed at death`

Offspring transfers cancel in population totals but are recorded for each parent and child. Reconcile within declared floating-point tolerances. There is no energy capacity, forced population size, or silent energy deletion. Exhausted organisms should not create a numerical overspend beyond roundoff.

## 7. Resources, inheritance, and starting parameters

### Food

Uniform random initial positions. Subsequent spawns follow exponential interarrival times (a Poisson process), at the configured rate independent of population. Place accepted arrivals uniformly. At the cap, discard the arrival, do not queue it, and continue scheduling arrivals. Rate zero disables replenishment. Generate interarrival times from a documented open-interval uniform transformation so waits are positive. Record attempted, accepted, and discarded arrivals.

Resolve spawns at their actual sub-tick times. At a simultaneous spawn and consumption when already capped, the spawn is discarded first; this convention is explicit. No consumed item regenerates at its old location.

### Reproduction and mutation

At tick end, a living parent's energy must strictly exceed 60 and support transfer plus overhead while leaving it positive. Deduct 25 for offspring and 5 overhead; produce at most one child per parent per tick. Process eligible parents in ID order for reproducible random draws and ID assignment; reproduction involves no shared-resource competition.

Copy each trait independently. Mutate each with probability 0.05; when selected, add a uniform perturbation in `[-0.05 * range, +0.05 * range]`. Reflect any overshoot repeatedly into its valid range, including configurable larger perturbations. Keep independent settings for speed and vision. Mutation is not directed toward improvement.

Place offspring uniformly within a radius-1 disk around the parent's current position, reflecting coordinates at world edges. Inherit parent ID, founder lineage ID, and parent generation plus one. Birth time is the tick endpoint. No lifespan evolution or reproduction-count death.

### Initial defaults, subject to calibration

| Parameter | Starting value |
| --- | --- |
| World dimensions | 100 × 100 distance units |
| Fixed decision interval | 0.1 simulated time units |
| Initial organisms / food | 50 / 200 |
| Food arrival rate / cap / energy | 8 per time unit / 500 / 10 |
| Consumption radius | 0.75 |
| Speed bounds / founder sampling | 0.5–8 / uniform 1–4 |
| Vision bounds / founder sampling | 1–30 / uniform 3–12 |
| Founder energy | 30 |
| Baseline cost `b` | 0.2 energy/time |
| Vision coefficient `kv` / reference `vref` | 0.1 energy/time / 10 distance |
| Movement coefficient `km` / reference `uref` | 0.05 energy/distance / 2 distance/time |
| Search speed fraction | 0.5 |
| Search turn mean interval | 2 simulated time units |
| Lifespan | 200 simulated time units |
| Reproduction threshold / transfer / overhead | 60 / 25 / 5 energy |
| Mutation probability / perturbation scale | 0.05 per trait / 0.05 of allowed range |

Founder traits are independent; positions and headings are uniform. Search turn probability per tick is `1 - exp(-dt / 2)`, with a new uniform heading on a turn. Pursuit uses inherited maximum speed. Preserve last travel heading for subsequent searching. All randomness uses the run generator.

The movement equation is quadratic in speed per distance and cubic in speed per time during uninterrupted travel. It is an adjustable modeling assumption, not a biological law.

## 8. Reproducibility, browser, and reporting

### Reproducibility

One private `random.Random(seed)` belongs to each Simulation. Canonically order initialization, organisms, foods, geometric candidates, reproduction, and random tie inputs. Do not use set iteration or request timing as model input. Do not draw randomness for rendering, inspection, exports, or metric reads.

Compare equal physics-step counts, not elapsed real time. Headless and browser advancement call the same engine. Record engine version, Python version, seed, and all parameters in exports. Guarantee reproducibility for the same supported engine/runtime environment; floating-point geometry and random-library changes limit broader cross-platform/version guarantees.

### Browser API and controls

Flask exposes create/reset, advance-by-N-steps, snapshot/inspection, and export operations. Keep one advance request in flight; serialize state mutations and use run identity plus expected tick index to reject stale or duplicate advancement. A single local run is the supported scope, not concurrent independent browser users.

The browser schedules small bounded batches based on playback speed, never modifying `dt`, traits, or costs. At 1×, target one simulated time unit per real second. Pause drains the current short batch before confirming paused state. Single step advances one complete tick including all internal events. If throughput is insufficient, display achieved speed rather than skip physics. Reset reproduces the same configuration and seed; pending parameter edits require an explicit new run/reset.

An empty population terminates advancement at the tick containing extinction; retain the precise last-death timestamp separately. Do not process later events in that interval once extinction is final. Record terminal metrics, preserve state and charts, and pause automatically. Headless batching returns the actual completed step count and terminal status; no hidden extra ticks occur after extinction.

### Presentation

- Canvas world; distinct food and organism markers, brief birth/death effects.
- Independent animation via requestAnimationFrame. Any visual interpolation follows reflected segments where provided and never feeds back into physics.
- Click selection during pause and, if practical, playback. Highlight one organism and optionally its vision circle.
- Inspection: ID, parent, founder lineage, generation, age, energy, maximum speed, current mode/speed, vision, offspring count. Retain last selected details and cause when it dies.
- Main controls: playback, seed/new seed, initial population, food rate, movement and vision coefficients, plus run buttons.
- Advanced panel: all remaining model parameters, including food energy/cap, mutation, reproduction, lifespan, search, trait ranges, world dimensions, and dt.
- Numerical summaries: population, births, deaths by primary cause, time/tick, seed, trait means and standard deviations.
- Charts: population, mean inherited speed, mean inherited vision; simple current-trait histograms if practical.
- Sample summaries each simulated time unit, initially, and at termination. Empty-population trait means are null, not zero.
- JSON exports include complete parameters, seed, versions, summaries, and accounting totals. CSV exports contain time-series summaries. No full event-history requirement; keep aggregate counts and bounded recent visualization events.

## 9. Verification and calibration

### Deterministic physics tests

- A path crosses a food disk with both tick endpoints outside it.
- Tangency, initial overlap, stationary contact, reflection, multiple wall contacts, corner reflection, and zero-length segments.
- Organisms may overlap or cross paths without collision or responses to one another.
- Earlier arrival wins even when the later organism has lower ID or is stored first.
- Seeded exact ties replay identically; repeated trials show approximately uniform ownership.
- Multiple simultaneous food/organism contacts obey one-meal eligibility without storage-order advantage.
- Insufficient energy stops movement before food; food just before depletion rescues; food exactly at or after depletion cannot rescue.
- Eating revises subsequent depletion; waiting after eating still spends upkeep.
- Maximum age truncates movement and preempts simultaneous feeding or birth.
- Spawn timing cannot expose food before creation; caps and zero rates work.
- Segment-integrated costs and population energy reconciliation, including reproduction and age-death reserves.
- Inheritance, reflected mutation bounds, frequencies/signs, lineage, successive births, and empty/extreme configurations.

Compare complete trajectories across repeats, one-step versus batched runs, reversed storage insertion order, headless versus API runs, and different UI playback schedules. Verify inspection and metric reads have no effect. Use fixed seeds and statistically justified tolerances for distribution tests. Check event resolver progress: no zero-time infinite loops or duplicate meals/deaths at segment boundaries.

### Calibration

Use 20 training seeds to screen a small documented set of food-rate and cost settings, then validate the selected baseline on at least 100 separate, predefined seeds for 1,000 simulated time units (10,000 ticks). Target approximately 80–90% survival without rescue rules, forced births, or hidden culling. Report counts and a binomial confidence interval; a measured fraction is not a guarantee of the underlying probability.

Report all tested settings, including failures. Record survival, extinction times, births/deaths, final and time-varying population, trait means/spreads, generations, energy budgets, and runtime. Examine late-run population trends/variability to distinguish survival from stability. Compare trait shifts across seeds and mutation-off controls; do not require a particular optimum or force directional evolution. Initial food must not merely delay collapse; extend selected surviving runs beyond the main horizon to check this.

If survival, stability, and detectable selection cannot all be obtained under the approved rules, report the conflict for review rather than change physics to obtain the target. Treat default calibration changes as documented parameter choices, not silent acceptance-test manipulation.

## 10. Project layout and local entry points

```text
ai-evolution/
  AGENTS.md
  README.md
  pyproject.toml
  docs/
    R1-requirements.md
    R1-architecture.md
    R1-model.md
    R1-calibration.md
    decisions/
  ai_evolution/
    __init__.py
    __main__.py
    experiments/
      __init__.py
      r1/
        config.py
        models.py
        movement.py
        encounters.py
        energy.py
        resources.py
        reproduction.py
        simulation.py
        metrics.py
        exports.py
        calibration.py
    web/
      app.py
      static/
        index.html
        styles.css
        api.js
        controls.js
        world.js
        charts.js
  tests/
    test_r1_*.py
    test_web_api.py
```

Future independent experiments get their own packages. Extract shared components when an actual second experiment justifies reuse, not in anticipation of unbuilt mechanisms.

Planned commands after implementation:

```text
.venv/bin/python -m unittest discover -s tests
.venv/bin/python -m ai_evolution headless --seed 42 --steps 10000
.venv/bin/python -m ai_evolution calibrate
.venv/bin/python -m ai_evolution serve
```

## 11. Small implementation milestones

1. **Engine foundation:** approved model documentation, validated config, seeded initialization, state, tick boundaries, headless execution, basic tests.
2. **Early visual interface:** world rendering, reflected search movement, seed, start/pause/reset/single-step, playback, basic selection. Clearly mark incomplete biology.
3. **Chronological physics:** swept encounters, first-arrival competition, continuous energy, immediate starvation/age death, resource spawning, rigorous geometry/accounting tests. Add basic live metrics.
4. **Evolution:** reproduction, mutation, lineage, offspring inspection, birth/death effects, conservation tests.
5. **Experiment reporting:** advanced controls, charts, exports, trait spreads/histograms, API replay tests and manual browser smoke test.
6. **Calibration and acceptance:** multi-seed reports, performance measurements, late-run checks, documented baseline and limitations.

Keep every stage runnable and testable. Milestones A through E and F.1 are authorized. Do not begin F.2–F.5 without authorization.

Milestone B implementation note: random search uses an analytic axis-folding calculation for reflected endpoints and outgoing headings, supporting multiple wall hits per tick. No swept encounters or interactions are implemented yet. Browser playback requests explicit bounded batches through the Flask adapter; it does not introduce a second physics loop. Canvas displays authoritative snapshots without interpolation. The server has no autonomous stepping thread, so only accepted advance/single-step requests move simulated time.

Milestone C implementation note: the engine splits motion at chronological events and solves swept disk encounters on every actual segment. Continuous expenses and immediate starvation/age death preempt food at the same computed time. Food spawns at its Poisson arrival time; shared simultaneous claims use seeded ordering and choices. Event segments are represented by the current `Motion` and elapsed interval rather than stored as a separate path-history object. Cumulative statistics and final death records support diagnostics and inspection. Reproduction and mutation were deferred at that milestone.

Milestone D implementation note: `reproduction.py` applies tick-end eligibility, transfers and overhead, exact inheritance, independent reflected mutations, and disk placement. Eligible parents are processed in canonical ID order and newborns inserted after all existing parents have been considered. The ledger treats offspring reserves as internal transfers and overhead as an expense. The UI adds live summaries, lineage/birth inspection, a brief newborn ring, and reset-only Advanced mutation settings. Full time-series reporting and calibration were deferred at that milestone. See `R1-model.md` for the implemented rules and limitations.

Milestone D final refinements: the full environment is fitted to a viewport-sized pane with aspect ratio preserved, while surrounding controls/statistics/inspection scroll independently. This affects rendering and hit testing only. Advanced settings now expose Initial Food independently of the fractional replenishment rate, using the existing configuration validation and seeded initialization. Heading independence, requested mutation settings, fractional Poisson rates, and complete seeded trajectories are additionally verified; no biological rule or default was changed.

## 12. Approved conventions and implementation concerns

### Final behavioral conventions

1. **Meal limit:** one food per organism per tick, followed by no movement until the next tick; sensing/replanning remains at tick boundaries.
2. **Competition:** chronological first arrival wins. Exact simultaneous conflicts use seeded randomness, including random ordering across simultaneous food items. Storage/processing order gives no advantage. Death precedes a same-time meal; spawning precedes same-time consumption.
3. **No physical collisions:** overlapping positions and crossing paths are allowed without detection, blocking, pushing, or any other response to organisms. Only shared food creates competition.

No behavioral approval points remain for Milestone A. Implement these rules only in their assigned subsequent milestones.

### Concerns to measure, without changing approved rules

- Continuous event resolution is more complex than endpoint stepping but necessary for the approved causal behavior. Start with transparent candidate recomputation and tests; introduce a priority queue or spatial grid only after profiling.
- A one-meal-per-tick cap and once-per-tick reproduction remain dt-dependent biological assumptions even though movement encounters are continuous. Compare dt 0.1 and 0.05 during calibration and report sensitivity; identical outcomes across different dt values are not promised.
- Floating-point exact ties require carefully constructed geometry and documented limitations. No broad epsilon-based race resolution is approved by this document.
- Food cap does not bound population or chart history. Runtime safeguards may visibly pause an oversized run, never silently cull organisms or alter energy. Benchmark practical default throughput before promising 20× playback.
- Survival at 1,000 units, stable populations, and observable inherited-trait change are separate outcomes; an 80–90% survival target may require tuning and does not itself establish selection.
- Fixed lifespan, unbounded energy storage, trait bounds, and mutation reflection all affect results. Preserve their visibility in configuration, exports, and scientific interpretation.

No additional technology or architectural framework is required to accommodate the approved revisions.


Milestone E implementation note: a separate read-only MetricsCollector observes initial, periodic tick-end, and terminal states without RNG access. History retains the initial point plus the latest 9,999 measurements. The requested one-unit interval is exact at the default dt; non-dividing custom dt rounds upward to whole ticks, exposing the effective interval rather than splitting biological steps. Flask serves cursor-based history and stable-run CSV/JSON exports. Plain Canvas renders bounded envelopes and fixed-range current histograms at at most four redraws per second in the existing scrolling pane. See `R1-reporting.md` for definitions, retention gaps, endpoint exports, and limitations. Biological rules and defaults are unchanged; calibration remains Milestone F.

Milestone E final reporting refinements: the Canvas scatter plot reuses paired traits from the existing authoritative living-organism payload, with fixed configured axes and deterministic overlap picking into the inspector. JSON adds an ID-sorted living-organism snapshot at final_time; aggregate histories and CSV schema are unchanged. No individual history, biological changes, random draws, or dependencies were added.


Milestone F.1 adds a sequential batch runner in `experiments/r1/batch.py`, independent of Flask and animation. One daemon thread per application executes at most one batch at a time; each seed owns a separate engine and RNG. Locks protect progress/result publication, not physics execution, and cancellation is checked between ticks. Completed aggregate results/histories remain in memory and can be exported or replayed through the existing single-run controller. The two-tab UI reuses Canvas history rendering and SimulationConfig validation/defaults. See `R1-batch.md` for limits, denominators, replay, API and lifecycle details. No calibration, biological changes, multiprocessing, database, or F.2–F.5 features are included.
