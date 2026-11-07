"""Explicit single-run advancement and one independent background batch worker."""

from dataclasses import asdict, replace
import json
from threading import Lock
from uuid import uuid4

from flask import Flask, Response, jsonify, request

from .. import __version__
from ..experiments.r1 import Simulation, SimulationConfig
from ..experiments.r1.metrics import distributions
from ..experiments.r1.exports import export_csv, export_json
from ..experiments.r1.batch import BatchConfig, BatchRunner


def create_app(config: SimulationConfig | None = None, *, seed: int = 0, batch_limits=None) -> Flask:
    app = Flask(__name__, static_folder="static")
    simulation = Simulation(config, seed=seed)
    lock = Lock()
    run_id = uuid4().hex
    running = False
    batch = BatchRunner(batch_limits)
    app.extensions["batch_runner"] = batch

    def report():
        state = simulation.snapshot()
        return {
            "run_id": run_id, "running": running, "seed": simulation.seed,
            "engine_version": __version__, "milestone": "E",
            "parameters": asdict(simulation.config), "state": asdict(state),
            "population_limit": batch.limits.max_initial_population,
            "time": state.time, "is_terminal": state.is_terminal,
            "summary": state.summary(),
            "measurement": asdict(simulation.current_metrics()),
            "histograms": distributions(state, simulation.config),
            "reporting": simulation.reporting_metadata(),
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

    @app.get("/api/history")
    def history():
        with lock:
            if request.args.get("run_id", run_id) != run_id:
                return jsonify(error="History belongs to a different run"), 409
            try:
                cursor = request.args.get("after")
                cursor = int(cursor) if cursor is not None else None
                data = simulation.metric_history(cursor)
            except ValueError as error:
                return jsonify(error=str(error)), 400
            return jsonify(run_id=run_id, **data)

    @app.get("/api/export.<format>")
    def download(format):
        if format not in ("csv", "json"):
            return jsonify(error="Export format must be csv or json"), 400
        with lock:
            if request.args.get("run_id", run_id) != run_id:
                return jsonify(error="Export belongs to a different run"), 409
            body = export_csv(simulation) if format == "csv" else export_json(simulation)
            response = Response(body, content_type="text/csv; charset=utf-8" if format == "csv" else "application/json")
            response.headers["Content-Disposition"] = f'attachment; filename="ai-evolution-seed-{simulation.seed}.{format}"'
            return response

    @app.get("/api/batch/settings")
    def batch_settings():
        return jsonify(defaults=asdict(BatchConfig()), limits=asdict(batch.limits),
                       integer_parameters=["initial_population", "initial_food", "food_cap"])

    @app.route("/api/batch", methods=["GET", "POST"])
    def batch_experiment():
        if request.method == "GET":
            return jsonify(batch.status())
        try:
            config = BatchConfig.from_dict(request.get_json(silent=True), batch.limits)
            identity = batch.start(config)
        except ValueError as error:
            return jsonify(error=str(error)), 400
        except RuntimeError as error:
            return jsonify(error=str(error)), 409
        return jsonify(batch_id=identity), 202

    @app.post("/api/batch/cancel")
    def cancel_batch():
        data = request.get_json(silent=True)
        try:
            batch.cancel(data.get("batch_id") if isinstance(data, dict) else None)
        except ValueError as error:
            return jsonify(error=str(error)), 409
        return jsonify(batch.status())

    @app.get("/api/batch/<identity>/runs/<int:number>")
    def batch_run(identity, number):
        try:
            return jsonify(batch.result(identity, number))
        except ValueError as error:
            return jsonify(error=str(error)), 404

    @app.get("/api/batch/export.json")
    def batch_export():
        try:
            data = batch.export(request.args.get("batch_id"))
        except ValueError as error:
            return jsonify(error=str(error)), 409
        response = Response(json.dumps(data, indent=2, sort_keys=True, allow_nan=False),
                            content_type="application/json")
        response.headers["Content-Disposition"] = 'attachment; filename="ai-evolution-batch.json"'
        return response

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
            if action == "replay_batch":
                try:
                    result = batch.result(data.get("batch_id"), data.get("run_number"))
                except ValueError as error:
                    return jsonify(error=str(error)), 409
                simulation = Simulation(SimulationConfig(**result["configuration"]), seed=result["seed"])
                run_id = uuid4().hex
                running = False
            elif action == "reset":
                seed_value = data.get("seed", simulation.seed)
                if type(seed_value) is not int or abs(seed_value) > 2**53 - 1:
                    return jsonify(error="Seed must be a JavaScript-safe integer"), 400
                updates = data.get("parameters", {})
                allowed = {"initial_population", "initial_food", "food_spawn_rate", "movement_cost", "vision_cost",
                           "speed_mutation_probability", "vision_mutation_probability",
                           "speed_mutation_magnitude", "vision_mutation_magnitude"}
                if not isinstance(updates, dict) or not updates.keys() <= allowed:
                    return jsonify(error="Unsupported reset parameters"), 400
                try:
                    updated_config = replace(simulation.config, **updates)
                    if "initial_population" in updates and updated_config.initial_population > batch.limits.max_initial_population:
                        raise ValueError(f"Initial Population must be at most {batch.limits.max_initial_population}")
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
