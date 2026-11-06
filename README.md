# AI Evolution

A laboratory for independent, agent-based evolutionary experiments. The simulation engine is Python; Flask and Canvas provide a local browser interface. Organisms are simple rule-based software entities, with no LLM agents.

## Current release: R1, Milestone C

Implemented: seeded initialization, fixed decision ticks, persistent search, nearest-visible-food pursuit, full-path consumption, chronological competition, continuous metabolic/vision/movement costs, Poisson food replenishment, starvation and age death, and browser controls and inspection.

**Reproduction and mutation are not implemented.** Population can only stay constant or decline. All founders reach their maximum lifespan at simulated time 200 under the defaults, so eventual extinction is expected. This milestone is not a viable evolutionary population or an assessment of the later 1,000-unit calibration target. No charts, fitness calculations, or calibration are included.

## Launch locally

Use the existing Python 3.13 `.venv`, from the repository root:

```sh
.venv/bin/python -m ai_evolution serve --port 5051
```

Open [the browser simulation](http://127.0.0.1:5051). Stop the server with Ctrl+C. The default port without `--port` is 5000; choose an unused port if another service or an older simulation server occupies it. Debug mode is disabled and the server binds only to localhost.

Flask and its dependencies are already installed. To recreate the tested environment when needed:

```sh
.venv/bin/python -m pip install -r requirements.txt
```

## Browser operation

- Start/Resume runs the current experiment; Pause drains the current short batch and preserves state. Single step advances one decision tick, including all continuous events inside it.
- Reset rebuilds the experiment. Seed, food rate, movement coefficient, and vision coefficient edits take effect only on Reset. Start/Resume never silently applies pending model edits.
- Playback (0.25×, 1×, 5×, 20×) changes request scheduling, not physics, costs, dt, or random draws. Local throughput and background-tab throttling may reduce achieved speed. No physics steps are skipped to catch up.
- Click an organism to inspect it. Repeated clicks cycle nearby/overlapping organisms; the dropdown can select every living or dead organism. The selected vision overlay is optional. Dead-organism details freeze at its death time; a selected death location is marked with a cross.
- Statistics show time, steps, live population, food present/consumed, and starvation/age deaths. At extinction, advancement stops automatically, final state and statistics remain visible, and Reset remains available.

Browser seeds are integers within JavaScript's safe range (±9,007,199,254,740,991); Python headless seeds may be arbitrary integers. One in-memory run is shared by tabs; use one control tab at a time. Stale run/step requests are rejected. Reloading explicitly pauses the run. Server restart clears its state. Canvas displays authoritative snapshots without interpolation.

## Run headlessly

```sh
.venv/bin/python -m ai_evolution headless --seed 42 --steps 100
.venv/bin/python -m ai_evolution headless --seed 42 --steps 100 --population 5 --food 0 --food-rate 0
.venv/bin/python -m ai_evolution headless --seed 42 --steps 100 --movement-cost 0.1 --vision-cost 0.2
.venv/bin/python -m ai_evolution --help
```

The command prints JSON containing engine/Python versions, seed, parameters, requested/completed steps, time, terminal status, active state, death records, and cumulative energy/resource statistics. JSON object keys for IDs are strings. This is a full-state report, not the later time-series export system. Headless execution imports no Flask or browser modules.

Options include `--seed` (0), `--steps` (0), `--population` (50), `--food` (200), `--dt` (0.1), `--food-rate` (8), `--movement-cost` (0.05), and `--vision-cost` (0.1). `--food 0` disables only initial food; also specify `--food-rate 0` to disable replenishment. Invalid inputs produce a CLI error. An initially empty population is terminal and advances zero ticks.

## Test

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m pip check
```

Tests cover initialization/configuration, RNG isolation, movement/reflection, swept food encounters, arrival ties, costs and energy conservation, immediate death, spawning/caps, population decline/extinction, replay/batching, Flask controls, and headless equivalence. No third-party test framework is needed. Earlier milestone invariants are retained in isolated fixtures where appropriate; constant-energy/food and immortal-organism expectations have been updated for the authorized survival mechanics.

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

Flask 3.1.2 remains the only direct runtime dependency. `requirements.txt` records tested transitive versions; no dependency changes were needed for Milestone C. Experiments remain under `ai_evolution/experiments/`, independent of the web adapter.

## Model and project documentation

- [Guidelines](AGENTS.md)
- [R1 requirements](docs/R1-requirements.md)
- [Approved architecture](docs/R1-architecture.md)
- [Implemented model, equations, update order, and numerical limitations](docs/R1-model.md)
- [Milestone C verification](docs/Milestone-C-verification.md)

Next is Milestone D: reproduction, inheritance/mutation, and related tests. It has not been started.
