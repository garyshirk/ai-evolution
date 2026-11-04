"""Minimal headless CLI. Run from the repository root with python -m ai_evolution."""

import argparse
from dataclasses import asdict
import json
import platform

from . import __version__
from .experiments.r1 import Simulation, SimulationConfig


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI Evolution — Milestone A foundation")
    commands = parser.add_subparsers(dest="command", required=True)
    headless = commands.add_parser("headless", help="Initialize and advance the clock; no biology yet")
    headless.add_argument("--seed", type=int, default=0)
    headless.add_argument("--steps", type=int, default=0)
    headless.add_argument("--population", type=int, default=50)
    headless.add_argument("--food", type=int, default=200)
    headless.add_argument("--dt", type=float, default=0.1)
    args = parser.parse_args(argv)
    try:
        config = SimulationConfig(
            initial_population=args.population, initial_food=args.food, dt=args.dt
        )
        simulation = Simulation(config, seed=args.seed)
        completed = simulation.advance(args.steps)
    except ValueError as error:
        parser.error(str(error))
    state = simulation.snapshot()
    print(json.dumps({
        "milestone": "A", "biology_implemented": False,
        "engine_version": __version__, "python_version": platform.python_version(),
        "seed": simulation.seed, "parameters": asdict(config),
        "requested_steps": args.steps, "completed_steps": completed,
        "time": state.time, "is_terminal": state.is_terminal,
        "state": asdict(state),
    }, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
