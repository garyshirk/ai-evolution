# AI Evolution

An incremental, agent-based evolutionary simulation laboratory. Python owns the simulation; Flask and Canvas provide a local browser interface. Organisms are rule-based software entities, with no LLM agents.

## Current release: R1, Milestone B

Implemented: validated configuration, organism/trait/food/world data types, seeded initialization, deterministic identifiers, fixed-step searching with reflected boundaries, detached snapshots, reset, headless execution, and an early browser interface.

**Biology is incomplete.** Organisms move but do not detect, pursue, or consume food. No energy expenditure, food replenishment, reproduction, mutation, death, fitness calculations, calibration, or charts are implemented. Age advances with simulation time; energy stays constant and lifespan is not enforced yet. Overlapping organisms do not interact.

## Run locally

Use Python 3.13 and the existing `.venv`. Flask and its dependencies are installed for Milestone B. To reproduce that environment when needed, run `.venv/bin/python -m pip install -r requirements.txt` from the project root.

Launch the browser application:

```sh
.venv/bin/python -m ai_evolution serve --port 5050
```

Open [the local simulation](http://127.0.0.1:5050). Stop the server with Ctrl+C. The default port without `--port` is 5000; use 5050 if another macOS service occupies 5000. This is a localhost development server with debug mode disabled.

The interface starts paused. Start/Resume schedules explicit physics steps; Pause waits for any current short batch, then preserves state. Single step advances exactly one tick while paused. Playback offers 0.25×, 1×, 5×, and 20×; it changes scheduling, never model dt or random draws. Available compute capacity and background-tab throttling can reduce achieved playback speed. The renderer draws authoritative snapshots without interpolating physics.

Edit the seed and press Reset to apply it; Start/Resume does not apply pending edits. Reset with the same seed replays the run. Browser seeds must be integers in JavaScript's safe range (±9,007,199,254,740,991); Python headless seeds may use arbitrary integers. Click circles to select organisms, click repeatedly to cycle nearby/overlapping circles, or use the organism dropdown to select any ID. The selected vision circle can be toggled. Inspection updates during playback and while paused.

One in-memory run is shared by browser tabs. Use one control tab at a time; stale run/step requests are rejected. Reloading explicitly pauses the run. No state survives a server restart.

Headless execution remains available without importing Flask:

```sh
.venv/bin/python -m ai_evolution headless --seed 42 --steps 100
.venv/bin/python -m ai_evolution headless --seed 42 --steps 4 --population 2 --food 0 --dt 0.25
.venv/bin/python -m ai_evolution --help
```

The command prints one JSON document containing the engine/Python version, seed, complete parameters, requested/completed step counts, time, terminal status, and full final state. Object keys representing IDs become strings in JSON. Output may be redirected to a file if desired. This is a foundation state report, not the later time-series export system.

Available options: integer `--seed` (default 0), nonnegative integer `--steps` (default 0), `--population` (50), `--food` (200), and positive `--dt` (0.1). Invalid inputs fail with a command-line error. An initially empty population is terminal and advances zero steps, preserving its food.

## Test

```sh
.venv/bin/python -m unittest discover -s tests -v
```

Tests cover initialization, trait/world bounds, IDs and lineage, configuration validation, seeded replay, clock advancement, snapshot isolation, reset, empty populations, search movement, reflection, batching/playback independence, Flask controls, and subprocess execution of the headless command. No third-party test framework is required. The Milestone A invariant test now allows movement while continuing to verify unchanged food, energy, traits, lineage, and population.

## Engine usage and reproducibility

```python
from ai_evolution.experiments.r1 import Simulation, SimulationConfig

simulation = Simulation(SimulationConfig(initial_population=10), seed=42)
completed = simulation.advance(100)
state = simulation.snapshot()
print(state.step_count, state.time, completed)
print(state.organisms[1].age_at(state.time))
simulation.reset()
```

Configuration and traits are frozen dataclasses. The engine owns mutable state privately; `snapshot()` returns a deep copy, so callers can inspect or change their copy without changing the run. Create a new Simulation to change parameters or seed. `reset()` replays the existing seed/configuration from time zero, including ID counters and RNG state. `step()` returns whether a tick completed; `advance(n)` returns the number completed. Time is computed from integer step count times fixed dt, without cumulative clock addition.

The engine uses one private `random.Random(seed)`. Initialization draws organisms in ID order: x, y, speed, vision, heading; then food in ID order: x, y. Positions are uniform across the rectangle; speed and vision use independent uniform founder ranges, and headings are uniform in radians. Organism and food IDs use separate namespaces starting at 1; founder lineage ID equals founder organism ID. Food IDs do not affect organism IDs.

Each tick processes organisms by sorted ID, drawing once for a turn with probability `1 - exp(-dt / search_turn_interval)`, and once more for a uniform heading only when turning. Search speed is inherited maximum speed times `search_speed_fraction` (default 0.5). Axis-wise folded coordinates reflect the complete traveled distance, including multiple wall hits in one tick; the final heading points along the reflected velocity. Exact wall endpoints point inward. This milestone computes reflected endpoints; swept path segments and encounters are reserved for Milestone C. Snapshot reads, browser rendering, and playback scheduling never draw from the model RNG. Repeatability is supported with the same engine and Python version; future model changes can change trajectories.

`SimulationConfig` includes the approved defaults for later mechanisms but does not activate those mechanisms. Validation rejects booleans, nonnumeric/nonfinite values, invalid counts, nonpositive required quantities, negative rates/costs, probabilities outside [0, 1], reversed trait limits, founder ranges outside inherited-trait limits, and initial food exceeding its cap. Equal founder range endpoints allow fixed founder traits. Zero initial organisms/food/cap and zero optional costs/rates are supported. Future reproduction separately checks transfer affordability at birth; no implicit energy is added by configuration.

Flask 3.1.2 is the sole direct runtime dependency in `pyproject.toml`; `requirements.txt` records the tested transitive versions. The standard-library engine can still run independently of the web adapter. Package metadata includes static assets for optional packaging; running directly from the repository does not invoke the setuptools build backend.

## Design and next stage

- [Project guidelines](AGENTS.md)
- [R1 requirements](docs/R1-requirements.md)
- [Approved architecture](docs/R1-architecture.md)

Experiments live under `ai_evolution/experiments/`; R1 has independent configuration, models, and stepping. Add future mechanisms in their assigned milestones, extracting reusable components when a second experiment needs them.

Next is Milestone C: chronological path encounters, resource interactions, energy costs, and death. It has not been started.
