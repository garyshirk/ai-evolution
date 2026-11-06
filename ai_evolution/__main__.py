"""Minimal headless CLI. Run from the repository root with python -m ai_evolution."""

import argparse
from dataclasses import asdict
import json
import platform

from . import __version__
from .experiments.r1 import Simulation, SimulationConfig


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI Evolution — Milestone C (includes Milestone A foundation)")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="Launch the local browser interface")
    serve.add_argument("--port", type=int, default=5000)
    headless = commands.add_parser("headless", help="Run survival and resource competition; no reproduction yet")
    headless.add_argument("--seed", type=int, default=0)
    headless.add_argument("--steps", type=int, default=0)
    headless.add_argument("--population", type=int, default=50)
    headless.add_argument("--food", type=int, default=200)
    headless.add_argument("--dt", type=float, default=0.1)
    headless.add_argument("--food-rate", type=float, default=8.0)
    headless.add_argument("--movement-cost", type=float, default=0.05)
    headless.add_argument("--vision-cost", type=float, default=0.1)
    args = parser.parse_args(argv)
    if args.command == "serve":
        from .web.app import create_app
        if not 1 <= args.port <= 65535:
            parser.error("port must be between 1 and 65535")
        create_app().run(host="127.0.0.1", port=args.port, debug=False)
        return 0
    try:
        config = SimulationConfig(
            initial_population=args.population, initial_food=args.food, dt=args.dt,
            food_spawn_rate=args.food_rate, movement_cost=args.movement_cost, vision_cost=args.vision_cost,
        )
        simulation = Simulation(config, seed=args.seed)
        completed = simulation.advance(args.steps)
    except ValueError as error:
        parser.error(str(error))
    state = simulation.snapshot()
    print(json.dumps({
        "milestone": "C", "biology_implemented": True, "reproduction_implemented": False,
        "search_movement_implemented": True,
        "engine_version": __version__, "python_version": platform.python_version(),
        "seed": simulation.seed, "parameters": asdict(config),
        "requested_steps": args.steps, "completed_steps": completed,
        "time": state.time, "is_terminal": state.is_terminal,
        "state": asdict(state),
    }, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
