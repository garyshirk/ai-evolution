"""Bounded, process-memory experiment library and strict F.1 export validation."""

from dataclasses import fields
import math
import platform
from threading import Lock
from uuid import uuid4

from ... import __version__
from .config import SimulationConfig
from .metrics import MetricSample
from .statistics import close_time, compare_experiments, experiment_statistics, trajectories

MAX_IMPORT_BYTES = 256 * 1024 * 1024
MAX_EXPERIMENTS = 8
MAX_LIBRARY_SAMPLES = 1000000
REPLAY_VERSIONS = {"0.6.0", "0.7.0"}  # Reporting-only release changes; unchanged R1 model.


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def count(value):
    return type(value) is int and 0 <= value <= 10**9


def validate_batch(data):
    """Validate without copying histories. Ownership transfers to the library."""
    require(isinstance(data, dict) and type(data.get("schema_version")) is int and data["schema_version"] == 1,
            "Expected a compatible schema_version 1 R1 batch export, not a single-simulation report.")
    require(data.get("status") in ("completed", "cancelled", "failed"), "Import requires a finished batch export (completed, cancelled, or failed).")
    for key in ("engine_version", "python_version"):
        require(isinstance(data.get(key), str) and 0 < len(data[key]) <= 80, f"Missing or invalid {key}.")
    config, runs = data.get("configuration"), data.get("results")
    require(isinstance(config, dict) and isinstance(runs, list), "Batch configuration and results array are required.")
    require(type(config.get("runs")) is int and 1 <= config["runs"] <= 1000, "Imported batch must request 1–1000 runs.")
    require(number(config.get("duration")) and 0 < config["duration"] <= 1000000, "Invalid planned duration.")
    require(type(config.get("starting_seed")) is int and -(2**53 - 1) <= config["starting_seed"] <= 2**53 - config["runs"], "Invalid consecutive seed range.")
    parameters = config.get("simulation")
    require(isinstance(parameters, dict) and set(parameters) == set(SimulationConfig.__dataclass_fields__), "Complete R1 simulation configuration is required.")
    try:
        model = SimulationConfig(**parameters)
    except (ValueError, TypeError) as error:
        raise ValueError(f"Invalid R1 configuration: {error}") from error
    require(model.speed_max <= 1e6 and model.vision_max <= 1e6, "Imported trait bounds exceed analysis limits.")
    require(type(data.get("completed_runs")) is int and len(runs) == data["completed_runs"] <= config["runs"], "Completed run count does not match results.")
    require(type(data.get("total_runs")) is int and data["total_runs"] == config["runs"], "Total run count does not match configuration.")
    if data["status"] == "completed":
        require(len(runs) == config["runs"], "Completed batch is missing run results.")
    samples_count = 0
    required_sample = {item.name for item in fields(MetricSample)}
    for index, run in enumerate(runs):
        prefix = f"Run {index + 1}: "
        require(isinstance(run, dict), prefix + "result must be an object.")
        require(run.get("experiment") == "R1" and run.get("schema_version") == 1, prefix + "expected an R1 schema 1 run.")
        require(type(run.get("run_number")) is int and run["run_number"] == index + 1 and type(run.get("seed")) is int and run["seed"] == config["starting_seed"] + index, prefix + "run number or consecutive seed is inconsistent.")
        require(run.get("configuration") == parameters, prefix + "configuration differs from batch.")
        try:
            SimulationConfig(**run["configuration"])
        except (TypeError, ValueError) as error:
            raise ValueError(prefix + f"invalid run configuration: {error}") from error
        require(run.get("engine_version") == data["engine_version"] and run.get("python_version") == data["python_version"], prefix + "version metadata differs from batch.")
        require(type(run.get("survived")) is bool and type(run.get("is_terminal")) is bool and run["survived"] != run["is_terminal"], prefix + "invalid survival/terminal status.")
        require(run.get("stop_reason") == ("duration" if run["survived"] else "extinction"), prefix + "stop reason is inconsistent.")
        end = run.get("final_time")
        require(number(end) and 0 <= end <= config["duration"] + 1e-9, prefix + "invalid final time.")
        require(not run["survived"] or close_time(end, config["duration"], model.dt), prefix + "surviving run did not reach duration.")
        stats = run.get("final_statistics")
        require(isinstance(stats, dict), prefix + "missing final statistics.")
        for key in ("population", "initial_population", "total_births", "total_deaths", "starvation_deaths", "age_deaths", "highest_generation"):
            require(count(stats.get(key)), prefix + f"invalid {key}.")
        require(stats["initial_population"] == model.initial_population and stats["population"] == model.initial_population + stats["total_births"] - stats["total_deaths"], prefix + "population accounting is inconsistent.")
        require(stats["total_deaths"] == stats["starvation_deaths"] + stats["age_deaths"], prefix + "death counts are inconsistent.")
        require(bool(stats["population"]) == run["survived"], prefix + "population does not match terminal state.")
        rows, reporting = run.get("measurements"), run.get("reporting")
        require(isinstance(rows, list) and 1 <= len(rows) <= 10001, prefix + "missing or oversized measurements.")
        samples_count += len(rows)
        require(samples_count <= MAX_LIBRARY_SAMPLES, "Imported measurement count exceeds library capacity.")
        require(isinstance(reporting, dict) and number(reporting.get("effective_interval")) and reporting["effective_interval"] > 0 and count(reporting.get("dropped_samples")), prefix + "invalid reporting metadata.")
        previous_time, previous_sequence, previous_step = -1, -1, -1
        previous_counts = (0, 0)
        for row_index, row in enumerate(rows):
            require(isinstance(row, dict) and required_sample <= row.keys(), prefix + "incomplete measurement fields.")
            time = row["time"]
            require(number(time) and previous_time < time <= end + 1e-9, prefix + "measurement times must be finite, ordered and within final time.")
            require(count(row["step"]) and row["step"] >= previous_step, prefix + "invalid measurement tick.")
            sequence = row["sequence"]
            require((sequence is None and row_index == len(rows) - 1 and row["sample_type"] == "current") or
                    (count(sequence) and sequence > previous_sequence), prefix + "invalid sample sequence.")
            for key in ("population", "initial_population", "total_births", "total_deaths", "starvation_deaths", "age_deaths", "highest_generation", "births_since_previous", "deaths_since_previous", "food_consumed"):
                require(count(row[key]), prefix + f"invalid measurement {key}.")
            require(row["initial_population"] == model.initial_population and row["population"] == model.initial_population + row["total_births"] - row["total_deaths"], prefix + "measurement population accounting is inconsistent.")
            require(row["total_deaths"] == row["starvation_deaths"] + row["age_deaths"] and row["total_births"] >= previous_counts[0] and row["total_deaths"] >= previous_counts[1], prefix + "measurement counters are inconsistent.")
            require(type(row["terminal"]) is bool and row["terminal"] == (row["population"] == 0), prefix + "measurement terminal state is inconsistent.")
            require(not row["terminal"] or row_index == len(rows) - 1, prefix + "terminal measurement must be last.")
            require(row["sample_type"] in ("initial", "regular", "terminal", "current"), prefix + "invalid sample type.")
            for key, lower, upper in (("mean_speed", model.speed_min, model.speed_max), ("mean_vision", model.vision_min, model.vision_max)):
                require(row[key] is None if row["population"] == 0 else number(row[key]) and lower <= row[key] <= upper, prefix + f"invalid {key}.")
            for key in ("speed_stddev", "vision_stddev"):
                require(row[key] is None if row["population"] == 0 else number(row[key]) and 0 <= row[key] <= 1e6, prefix + f"invalid {key}.")
            previous_time, previous_step = time, row["step"]
            previous_counts = row["total_births"], row["total_deaths"]
            if sequence is not None:
                previous_sequence = sequence
        require(rows[0]["time"] == 0 and rows[0]["sequence"] == 0 and rows[0]["population"] == model.initial_population, prefix + "initial measurement is missing.")
        require(close_time(rows[-1]["time"], end, model.dt) and rows[-1]["terminal"] == run["is_terminal"], prefix + "final endpoint is missing.")
        for key in ("population", "mean_speed", "mean_vision", "total_births", "total_deaths", "starvation_deaths", "age_deaths", "highest_generation"):
            require(stats.get(key) == rows[-1][key], prefix + f"final {key} disagrees with last measurement.")
        require(count(run.get("final_step")) and run["final_step"] == rows[-1]["step"], prefix + "final tick is inconsistent.")
    return samples_count


def replay_issue(run):
    if run["engine_version"] not in REPLAY_VERSIONS:
        return f"Replay unsupported for engine {run['engine_version']}; supported unchanged-model releases: {', '.join(sorted(REPLAY_VERSIONS))}. Analysis remains available."
    if run["python_version"] != platform.python_version():
        return f"Exact replay requires Python {run['python_version']}; this server uses {platform.python_version()}. Analysis remains available."
    return None


class ExperimentLibrary:
    def __init__(self):
        self._entries = {}
        self._lock = Lock()
        self._samples = 0

    def add(self, data, name):
        name = self._name(name)
        with self._lock:
            require(len(self._entries) < MAX_EXPERIMENTS, "Experiment library is full. Export and remove an experiment first.")
        sample_count = validate_batch(data)
        analysis, history = experiment_statistics(data), trajectories(data)
        entry = {"id": uuid4().hex, "name": name, "data": data,
                 "statistics": analysis, "trajectories": history, "samples": sample_count}
        with self._lock:
            require(len(self._entries) < MAX_EXPERIMENTS and self._samples + sample_count <= MAX_LIBRARY_SAMPLES,
                    "Experiment library is full (8 experiments / 1,000,000 samples). Export and remove an experiment first.")
            self._entries[entry["id"]] = entry
            self._samples += sample_count
        return self.metadata(entry)

    @staticmethod
    def _name(name):
        require(isinstance(name, str) and 0 < len(name.strip()) <= 120 and not any(ord(char) < 32 for char in name), "Experiment name must be 1–120 printable characters.")
        return name.strip()

    @staticmethod
    def metadata(entry):
        data = entry["data"]
        return {"id": entry["id"], "name": entry["name"], "configuration": data["configuration"],
                "status": data["status"], "completed_runs": len(data["results"]),
                "engine_version": data["engine_version"], "samples": entry["samples"]}

    def list(self):
        with self._lock:
            return [self.metadata(entry) for entry in self._entries.values()]

    def get(self, identity):
        require(isinstance(identity, str), "Invalid experiment identifier.")
        with self._lock:
            require(identity in self._entries, "Experiment not found or removed.")
            return self._entries[identity]  # Read-only ownership; no history copies per request.

    def rename(self, identity, name):
        name = self._name(name)
        with self._lock:
            require(identity in self._entries, "Experiment not found or removed.")
            self._entries[identity]["name"] = name

    def remove(self, identity):
        with self._lock:
            require(identity in self._entries, "Experiment not found or removed.")
            self._samples -= self._entries.pop(identity)["samples"]

    def compare(self, first, second):
        require(first != second, "Select two different experiments.")
        a, b = self.get(first), self.get(second)
        return compare_experiments(a["data"], b["data"], a["statistics"], b["statistics"], a["trajectories"], b["trajectories"])
