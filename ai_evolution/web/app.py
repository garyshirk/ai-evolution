"""Single local run with explicit advancement; no background physics thread."""

from dataclasses import asdict, replace
from threading import Lock
from uuid import uuid4

from flask import Flask, jsonify, request

from .. import __version__
from ..experiments.r1 import Simulation, SimulationConfig


def create_app(config: SimulationConfig | None = None, *, seed: int = 0) -> Flask:
    app = Flask(__name__, static_folder="static")
    simulation = Simulation(config, seed=seed)
    lock = Lock()
    run_id = uuid4().hex
    running = False

    def report():
        state = simulation.snapshot()
        return {
            "run_id": run_id, "running": running, "seed": simulation.seed,
            "engine_version": __version__, "milestone": "D",
            "parameters": asdict(simulation.config), "state": asdict(state),
            "time": state.time, "is_terminal": state.is_terminal,
            "summary": state.summary(),
        }

    @app.after_request
    def no_cache(response):
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/")
    def index():
        return app.send_static_file("index.html")

    @app.get("/api/state")
    def state():
        with lock:
            return jsonify(report())

    @app.post("/api/control")
    def control():
        nonlocal simulation, run_id, running
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error="Expected a JSON object"), 400
        with lock:
            current = simulation.snapshot()
            if (data.get("run_id") != run_id
                    or type(data.get("expected_step")) is not int
                    or data["expected_step"] != current.step_count):
                return jsonify(error="Stale run or step; refresh current state"), 409
            action = data.get("action")
            if action != "reset" and "parameters" in data:
                return jsonify(error="Model parameters can change only on reset"), 400
            if action == "reset":
                seed_value = data.get("seed", simulation.seed)
                if type(seed_value) is not int or abs(seed_value) > 2**53 - 1:
                    return jsonify(error="Seed must be a JavaScript-safe integer"), 400
                updates = data.get("parameters", {})
                allowed = {"initial_food", "food_spawn_rate", "movement_cost", "vision_cost",
                           "speed_mutation_probability", "vision_mutation_probability",
                           "speed_mutation_magnitude", "vision_mutation_magnitude"}
                if not isinstance(updates, dict) or not updates.keys() <= allowed:
                    return jsonify(error="Unsupported reset parameters"), 400
                try:
                    updated_config = replace(simulation.config, **updates)
                except ValueError as error:
                    return jsonify(error=str(error)), 400
                simulation = Simulation(updated_config, seed=seed_value)
                run_id = uuid4().hex
                running = False
            elif action == "start":
                running = not current.is_terminal
            elif action == "pause":
                running = False
            elif action in ("advance", "step"):
                if (action == "advance" and not running) or (action == "step" and running):
                    return jsonify(error="Advance requires running; single step requires paused"), 409
                steps = data.get("steps") if action == "advance" else 1
                if type(steps) is not int or not 1 <= steps <= 20:
                    return jsonify(error="Steps must be an integer from 1 to 20"), 400
                simulation.advance(steps)
                if simulation.snapshot().is_terminal:
                    running = False
            else:
                return jsonify(error="Unknown action"), 400
            return jsonify(report())

    return app
