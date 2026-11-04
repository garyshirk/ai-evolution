# AI Evolution

An incremental, agent-based evolutionary simulation laboratory. The engine is Python; a browser interface is planned for Milestone B. Organisms are rule-based software entities, with no LLM agents.

## Current release: R1, Milestone A

Implemented: validated configuration, organism/trait/food/world data types, seeded random initialization, deterministic identifiers, fixed-step clock, detached snapshots, reset, and a minimal headless command.

**This is a foundation, not a biological simulation yet.** Clock advancement does not move organisms, spend energy, spawn additional food, consume food, reproduce, mutate, or kill organisms. Age is derived from simulation time, but lifespan is not enforced yet. No browser, Flask server, calibration results, or evolutionary conclusions are available.

## Run locally

Use Python 3.13 and the existing `.venv`. From the project root, no package installation is needed for Milestone A:

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

Tests cover initialization, trait/world bounds, IDs and lineage, configuration validation, seeded replay, clock advancement, snapshot isolation, reset, empty populations, batching, and subprocess execution of the headless command. No third-party test packages are required.

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

The engine uses one private `random.Random(seed)`. Initialization draws organisms in ID order: x, y, speed, vision, heading; then food in ID order: x, y. Positions are uniform across the rectangle; speed and vision use independent uniform founder ranges, and headings are uniform in radians. Organism and food IDs use separate namespaces starting at 1; founder lineage ID equals founder organism ID. Food IDs do not affect organism IDs. No clock step currently consumes randomness. Repeatability is supported with the same engine and Python version; future model changes can change trajectories.

`SimulationConfig` includes the approved defaults for later mechanisms but does not activate those mechanisms. Validation rejects booleans, nonnumeric/nonfinite values, invalid counts, nonpositive required quantities, negative rates/costs, probabilities outside [0, 1], reversed trait limits, founder ranges outside inherited-trait limits, and initial food exceeding its cap. Equal founder range endpoints allow fixed founder traits. Zero initial organisms/food/cap and zero optional costs/rates are supported. Future reproduction separately checks transfer affordability at birth; no implicit energy is added by configuration.

The project has no runtime dependencies at this stage. `pyproject.toml` records package metadata and an optional setuptools build backend; running and testing directly from the repository do not invoke it. Flask will be introduced with the authorized UI milestone.

## Design and next stage

- [Project guidelines](AGENTS.md)
- [R1 requirements](docs/R1-requirements.md)
- [Approved architecture](docs/R1-architecture.md)

Experiments live under `ai_evolution/experiments/`; R1 has independent configuration, models, and stepping. Add future mechanisms in their assigned milestones, extracting reusable components when a second experiment needs them.

Next is Milestone B: an early Canvas interface, controls, selection, and reflected search movement, clearly labeled as incomplete biology. It has not been started.
