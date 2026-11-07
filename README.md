# AI Evolution

A laboratory for independent, agent-based evolutionary experiments. The simulation engine is Python; Flask and Canvas provide a local browser interface. Organisms are simple rule-based software entities, with no LLM agents.

## Current release: R1, Milestone F.1

Implemented: seeded initialization, fixed decision ticks, search and pursuit, full-path food competition, continuous energy costs, Poisson replenishment, starvation/age death, asexual reproduction, trait inheritance and mutation, and browser controls and inspection.

Population can grow through births and decline through deaths. Evolutionary differences arise from inherited speed/vision, resource access, survival, and reproduction; no fitness score or guaranteed survival is imposed. Milestone E adds descriptive evolutionary charts and exports. Milestone F.1 adds sequential batch experiments; calibration and F.2–F.5 remain unimplemented. Starting defaults have only undergone smoke testing.

## Launch locally

Use the existing Python 3.13 `.venv`, from the repository root:

```sh
.venv/bin/python -m ai_evolution serve --port 5052
```

Open [the browser simulation](http://127.0.0.1:5052). Stop the server with Ctrl+C. The default port without `--port` is 5000; choose an unused port if another service or an older simulation server occupies it. Debug mode is disabled and the server binds only to localhost.

Flask and its dependencies are already installed. To recreate the tested environment when needed:

```sh
.venv/bin/python -m pip install -r requirements.txt
```

## Browser operation

- Start/Resume runs the current experiment; Pause drains the current short batch and preserves state. Single step advances one decision tick, including all continuous events inside it.
- Reset rebuilds the experiment. Seed, food rate, movement coefficient, and vision coefficient edits take effect only on Reset. Start/Resume never silently applies pending model edits.
- **Initial Population** defaults to 50, accepts nonnegative integers, and applies on Reset. It uses the same configurable initial-population limit as batch execution (500 by default). Opening a batch replay fills this field from that run; exports record the applied population. Zero starts an extinct world.
- Advanced also provides **Initial Food**, a nonnegative integer no greater than the configured food cap (default 500). It defaults to 200 and is independent of the replenishment rate, which still defaults to 8. For scarcity, set Initial Food to 10 and Food / time to 0.1, then Reset. Zero initial food and zero replenishment are supported independently.
- Food / time accepts fractional rates such as 0.05, 0.1, 0.5, and 1.0. Its spinner increment is 0.5, but manually typed rates are validated as finite nonnegative numbers rather than restricted to spinner multiples.
- Advanced mutation settings provide independent per-trait probabilities and magnitudes, also applied only on Reset. Values are fractions: 0.05 means a 5% chance per birth or a perturbation up to 5% of the allowed trait range. Set both probabilities to zero for exact inheritance without mutation.
- Playback (0.25×, 1×, 5×, 20×) changes request scheduling, not physics, costs, dt, or random draws. Local throughput and background-tab throttling may reduce achieved speed. No physics steps are skipped to catch up.
- Click an organism to inspect it. Repeated clicks cycle nearby/overlapping organisms; the dropdown can select every living or dead organism. The selected vision overlay is optional. Dead-organism details freeze at its death time; a selected death location is marked with a cross.
- Statistics show time, steps, live population, births, deaths, highest generation reached, mean inherited speed/vision, and food present/consumed. Highest generation is cumulative, while means describe living organisms only; empty-population means display a dash.
- Inspect parent ID, generation, founder lineage, birth time, age, traits, energy, and offspring count. Newborns have a green ring for their first 0.5 simulated time units. Fast-forward may skip seeing that brief visual effect, but never skips the birth or physics.
- At extinction, advancement stops automatically, final state and statistics remain visible, and Reset remains available.

Browser seeds are integers within JavaScript's safe range (±9,007,199,254,740,991); Python headless seeds may be arbitrary integers. One in-memory run is shared by tabs; use one control tab at a time. Stale run/step requests are rejected. Reloading explicitly pauses the run. Server restart clears its state. Canvas displays authoritative snapshots without interpolation.

The environment occupies a pane fitted to the available viewport, preserving the world's aspect ratio. Window resizing changes only rendering size, never world dimensions or physics. Controls, Advanced settings, statistics, and inspection scroll independently; the full environment stays visible. Narrow windows stack the world above a scrolling control pane. Canvas picking and vision overlays use the current fitted dimensions.

## Evolutionary reports and exports

The collapsible Reports section contains population, mean inherited maximum speed, and mean inherited vision history graphs, plus current speed/vision histograms and a paired speed-versus-vision scatter plot. Hover over scatter points for exact traits and click repeatedly to inspect overlapping organisms. Statistics include population standard deviations, initial population, cumulative births/deaths and death causes, and highest generation reached. Empty-population trait values are unavailable, not zero. Measurements describe changes without assigning evolutionary causes.

Samples include initialization, every one simulated time unit at the default dt, and exact extinction. Custom dt rounds the requested interval upward to whole ticks (dt 0.3 gives 1.2 units); metadata records the effective interval. Pause preserves history; Reset starts a new history. Retention is 10,000 points: the initial point and latest 9,999. Lost middle history is explicitly marked; exports contain retained points only. Charts redraw at most four times per second with a bounded display envelope, independently of physics.

Export CSV and Export JSON pause playback and download the applied run, including its current endpoint. Pending settings are excluded. JSON also records seed, full configuration, engine/Python versions, final statistics, reporting metadata, and a living-organism snapshot (traits, lineage, generation, age, energy, and offspring count). Downloads do not save resumable simulation state. See the reporting document for column definitions and retention details.

## Batch Experiments

Switch to **Batch Experiments** to configure independent, sequential engine runs without animation. Defaults are 20 runs, 2,000 simulated units each, starting seed 0; all biological defaults come from the existing SimulationConfig. Seeds increase by one. The main controls expose population, food, costs and mutation; Additional R1 parameters exposes all remaining configuration fields.

Run Experiment starts a background worker. Progress shows completed/total runs and current run/time; Cancel stops between physics ticks and preserves completed runs. Changing tabs preserves results. Opening Batch Experiments pauses the animated single run. It can be resumed independently while the batch continues, sharing CPU resources.

Select a completed run to see its configuration, statistics, and population/trait histories. **Open in Single Simulation** replaces the single run with a fresh, paused time-zero replay using the selected seed and complete applied configuration. Export Batch JSON downloads the batch configuration, software/Python versions, every completed run's result/history, summary definitions, and completion/cancellation/error status. Export before starting a replacement batch; one batch is held in memory, and server restart loses it.

Average final population includes extinct completed runs as zero. Trait averages are equally weighted means of surviving-run means; extinct trait values remain unavailable, and the displayed denominator is explicit. Cancelled partial runs are excluded from all summary statistics. Results are descriptive, not a calibration or fitness analysis.

Default safeguards: 200 runs, duration 10,000, 2,000,000 total requested ticks, 500 initial organisms, food cap 2,000, and a conservative 500,000-measurement budget. Duration must align with full dt ticks. Resource guards stop and report an oversized run without culling; a single tick is not preemptible. See [batch architecture, API and limitations](docs/R1-batch.md) and [verification procedure](docs/Milestone-F1-verification.md).

## Run headlessly

```sh
.venv/bin/python -m ai_evolution headless --seed 42 --steps 100
.venv/bin/python -m ai_evolution headless --seed 42 --steps 100 --population 5 --food 0 --food-rate 0
.venv/bin/python -m ai_evolution headless --seed 42 --steps 100 --movement-cost 0.1 --vision-cost 0.2
.venv/bin/python -m ai_evolution headless --seed 42 --steps 100 --mutation-probability 0
.venv/bin/python -m ai_evolution headless --seed 42 --steps 100 --export-csv /tmp/r1.csv --export-json /tmp/r1.json
.venv/bin/python -m ai_evolution --help
```

The command prints JSON containing engine/Python versions, seed, parameters, requested/completed steps, time, terminal status, active state, death records, cumulative statistics, and a live summary including population energy and the energy-ledger residual. JSON object keys for IDs are strings. It also includes collected reporting history. Use --export-csv PATH and --export-json PATH for portable time-series and experiment reports. Headless execution imports no Flask or browser modules.

Options include `--seed` (0), `--steps` (0), `--population` (50), `--food` (200), `--dt` (0.1), `--food-rate` (8), `--movement-cost` (0.05), and `--vision-cost` (0.1). `--food 0` disables only initial food; also specify `--food-rate 0` to disable replenishment. Invalid inputs produce a CLI error. An initially empty population is terminal and advances zero ticks.

The CLI also accepts shared `--mutation-probability` and `--mutation-magnitude` (both default 0.05). Python configuration and the browser Advanced panel retain independent speed/vision settings.

## Test

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m pip check
```

Tests cover initialization/configuration, RNG isolation, movement/reflection, swept encounters and arrival ties, energy conservation, death, spawning/caps, reproduction thresholds and transfers, newborn timing, inheritance, independent mutation and reflection, lineage, population changes, replay/batching, Flask controls, and headless equivalence. Reporting tests also verify moments, histograms, sampling/retention, exports, reset/extinction, and unchanged seeded outcomes with collection enabled or disabled. No third-party test framework is needed. Earlier milestone invariants remain covered; resource-free founders still cannot reach the reproduction threshold.

## Reproduction and mutation

At tick end, a surviving parent's energy must be strictly greater than 60 and sufficient to leave it positive after transferring 25 to its child and spending 5 overhead. Each eligible parent has at most one offspring per tick. Newborns begin at age zero and first act on the next tick. Parent and child both remain alive unless later model events kill them.

Speed and vision inherit exactly unless their independent mutation test fires. Defaults are 5% per trait per birth, with a uniform positive/negative perturbation up to 5% of the trait's full allowed range. Reflect overshoots into speed 0.5–8 and vision 1–30. Place offspring uniformly in a radius-1 disk near the parent with reflected world coordinates. Each initial heading is a separate seeded uniform draw, not an inherited trait; do not force it to differ from the parent. Once active, parent and offspring can pursue the same food and therefore move together. No energy-efficiency trait is introduced.

Population energy is reduced only by the reproduction overhead: the child's reserve is a transfer, not newly created energy. Diagnostics separately record transferred energy, overhead, and mutation events. A zero-magnitude mutation event changes no value. See the model document for exact draw order and ledger equations.

## Engine API

```python
from ai_evolution.experiments.r1 import Simulation, SimulationConfig

simulation = Simulation(SimulationConfig(initial_population=10), seed=42)
completed = simulation.advance(100)
state = simulation.snapshot()
print(state.step_count, state.time, completed, state.statistics.food_consumed)
simulation.reset()
```

Configuration and traits are frozen dataclasses. Engine state is private; snapshots are detached deep copies. Create a new Simulation for new parameters/seed; `reset()` restores the existing seed/configuration, counters, statistics, and RNG. `step()` returns whether a tick was attempted/completed; `advance(n)` returns the number advanced, stopping at extinction. The final tick may terminate partway through: its index is counted, while `state.time` and `extinction_time` retain the exact terminal simulated time. Age is derived from simulated time or the archived death time, never browser time.

One private `random.Random(seed)` drives initialization, searching, spawning, and exact conflict resolution in canonical order. Snapshot reads and browser rendering do not draw from it. Repeatability is supported for the same engine/runtime environment, seed, configuration, and step count; cross-version/platform bit identity is not promised. Food/organism IDs use separate monotonic namespaces starting at 1.

Flask 3.1.2 remains the only direct runtime dependency. `requirements.txt` records tested transitive versions; no dependency changes were needed for Milestone F.1. Experiments remain under `ai_evolution/experiments/`, independent of the web adapter.

## Model and project documentation

- [Guidelines](AGENTS.md)
- [R1 requirements](docs/R1-requirements.md)
- [Approved architecture](docs/R1-architecture.md)
- [Implemented model, equations, update order, and numerical limitations](docs/R1-model.md)
- [Reporting definitions, sampling, retention, and export formats](docs/R1-reporting.md)
- [Milestone E verification and smoke observations](docs/Milestone-E-verification.md)

Long runs can accumulate many organisms and archived death records; the death archive has no retention limit, and no artificial population cap has been introduced. Reporting history is bounded separately. Runtime and memory use should be measured before extensive runs. Persistence is not established by the smoke tests.

Milestone F.1 is implemented. F.2–F.5 require separate authorization; no calibration or new biological mechanisms are included.
