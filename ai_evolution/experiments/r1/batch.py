"""Sequential R1 experiments, independent of Flask and animation."""

from copy import deepcopy
from dataclasses import asdict, dataclass, field
import math
import platform
from threading import Event, Lock, Thread
from time import sleep
from uuid import uuid4

from ... import __version__
from .config import SimulationConfig
from .exports import experiment_report
from .simulation import Simulation


@dataclass(frozen=True)
class BatchLimits:
    max_runs: int = 200
    max_duration: int = 10000
    max_total_steps: int = 2000000
    max_initial_population: int = 500
    max_food_cap: int = 2000
    max_retained_samples: int = 500000
    max_live_population: int = 10000
    max_death_records: int = 100000

    def __post_init__(self):
        for name, value in asdict(self).items():
            if type(value) is not int or value < 1:
                raise ValueError(f"{name} must be a positive integer")


@dataclass(frozen=True)
class BatchConfig:
    runs: int = 20
    duration: float = 2000
    starting_seed: int = 0
    simulation: SimulationConfig = field(default_factory=SimulationConfig)

    def validate(self, limits: BatchLimits) -> int:
        if type(self.runs) is not int or not 1 <= self.runs <= limits.max_runs:
            raise ValueError(f"runs must be an integer from 1 to {limits.max_runs}")
        if type(self.duration) not in (int, float) or not math.isfinite(self.duration) or not 0 < self.duration <= limits.max_duration:
            raise ValueError(f"duration must be positive and at most {limits.max_duration}")
        if type(self.starting_seed) is not int or not -(2**53 - 1) <= self.starting_seed <= 2**53 - self.runs:
            raise ValueError("All consecutive seeds must be JavaScript-safe integers")
        if not isinstance(self.simulation, SimulationConfig):
            raise ValueError("simulation must be a SimulationConfig")
        ratio = self.duration / self.simulation.dt
        if not math.isfinite(ratio) or ratio > limits.max_total_steps / self.runs:
            raise ValueError(f"Requested workload exceeds {limits.max_total_steps} total ticks")
        steps = round(ratio)
        if steps < 1 or not math.isclose(steps * self.simulation.dt, self.duration, rel_tol=1e-12, abs_tol=0):
            raise ValueError("duration must be a whole number of simulation ticks (dt)")
        if self.simulation.initial_population > limits.max_initial_population or self.simulation.food_cap > limits.max_food_cap:
            raise ValueError("Initial population or food cap exceeds batch resource limits")
        if self.runs * min(10001, steps + 2) > limits.max_retained_samples:
            raise ValueError("Requested retained measurement workload exceeds batch limits")
        return steps

    @classmethod
    def from_dict(cls, data, limits):
        if not isinstance(data, dict) or data.keys() - {"runs", "duration", "starting_seed", "simulation"}:
            raise ValueError("Expected batch runs, duration, starting_seed, and simulation parameters")
        values = dict(data)
        parameters = values.pop("simulation", {})
        if not isinstance(parameters, dict) or parameters.keys() - SimulationConfig.__dataclass_fields__.keys():
            raise ValueError("Unsupported simulation parameters")
        config = cls(**values, simulation=SimulationConfig(**parameters))
        config.validate(limits)
        return config


def aggregate(results):
    """Each completed run has equal weight; empty-population traits stay null."""
    count = len(results)
    survivors = [run for run in results if run["survived"]]
    def mean(values):
        return math.fsum(values) / len(values) if values else None
    return {
        "completed_runs": count, "surviving_populations": len(survivors),
        "extinct_populations": count - len(survivors),
        "survival_percentage": 100 * len(survivors) / count if count else None,
        "average_final_population": mean([run["final_statistics"]["population"] for run in results]),
        "average_final_speed": mean([run["final_statistics"]["mean_speed"] for run in survivors]),
        "average_final_vision": mean([run["final_statistics"]["mean_vision"] for run in survivors]),
        "trait_mean_run_count": len(survivors), "population_mean_run_count": count,
        "definitions": "Completed runs only. Population includes extinct runs as zero. Trait means are equally weighted means of surviving-run means; extinct trait values are unavailable, not zero. Cancelled partial runs are excluded.",
    }


def execute_batch(config, limits, cancel, completed, progress):
    """Callbacks publish immutable completed reports; partial cancelled runs discarded.

    Cancellation is checked between ticks. Yielding the GIL lets local request
    threads service progress/control without holding the manager lock in physics.
    """
    steps = config.validate(limits)
    for index in range(config.runs):
        if cancel.is_set():
            return
        seed = config.starting_seed + index
        progress(index + 1, seed, 0.0)
        simulation = Simulation(config.simulation, seed=seed)
        for step in range(steps):
            if cancel.is_set():
                return
            active = simulation.step()
            if step % 20 == 0 or not active:
                state = simulation.snapshot()
                if len(state.organisms) > limits.max_live_population or len(state.deaths) > limits.max_death_records:
                    raise RuntimeError("Run exceeded population/death-record resource limit; no biological culling was applied")
                progress(index + 1, seed, state.time)
            sleep(0)
            if not active:
                break
        state = simulation.snapshot()
        if len(state.organisms) > limits.max_live_population or len(state.deaths) > limits.max_death_records:
            raise RuntimeError("Run exceeded population/death-record resource limit; no biological culling was applied")
        report = experiment_report(simulation)
        report.pop("living_organisms")
        report.pop("histograms")
        report.update(run_number=index + 1, survived=not report["is_terminal"],
                      stop_reason="extinction" if report["is_terminal"] else "duration")
        completed(report)
        del simulation


class BatchRunner:
    """One in-memory batch per application, with short-held publication locks."""
    def __init__(self, limits=None, on_complete=None):
        self.limits = limits or BatchLimits()
        self._on_complete = on_complete
        self._library_error = None
        self._library_id = None
        self._lock = Lock()
        self._cancel = Event()
        self._thread = None
        self._id = None
        self._status = "idle"
        self._config = None
        self._results = []
        self._current = None
        self._error = None

    def start(self, config):
        config.validate(self.limits)
        with self._lock:
            if self._status in ("running", "cancelling"):
                raise RuntimeError("A batch is already running")
            self._id = uuid4().hex
            self._config = config
            self._status = "running"
            self._results = []
            self._current = None
            self._error = None
            self._library_error = None
            self._library_id = None
            self._cancel = Event()
            self._thread = Thread(target=self._work, daemon=True, name="r1-batch")
            self._thread.start()
            return self._id

    def _work(self):
        def completed(report):
            with self._lock:
                self._results.append(report)
        def progress(number, seed, time):
            with self._lock:
                self._current = {"run_number": number, "seed": seed, "time": time}
        try:
            execute_batch(self._config, self.limits, self._cancel, completed, progress)
            with self._lock:
                outcome = "completed" if len(self._results) == self._config.runs else "cancelled"
                self._current = None
                completed_data = {**self._status_report(), "status": outcome, "schema_version": 1,
                                  "engine_version": __version__, "python_version": platform.python_version(),
                                  "limits": asdict(self.limits), "results": list(self._results)}
            completed_data.pop("library_id")
            completed_data.pop("library_error")
            if outcome == "completed" and self._on_complete is not None:
                try:
                    saved = self._on_complete(completed_data)
                    with self._lock:
                        self._library_id = saved["id"]
                except ValueError as error:
                    with self._lock:
                        self._library_error = str(error)
            with self._lock:
                self._status = outcome
        except Exception as error:
            with self._lock:
                self._status = "failed"
                self._error = str(error)
                self._current = None

    def cancel(self, batch_id):
        with self._lock:
            self._check_id(batch_id)
            if self._status == "running":
                self._status = "cancelling"
                self._cancel.set()

    def _check_id(self, batch_id):
        if batch_id != self._id or self._id is None:
            raise ValueError("Stale or missing batch ID")

    def status(self):
        with self._lock:
            return self._status_report()

    def _status_report(self):
        return {"batch_id": self._id, "status": self._status, "current": dict(self._current) if self._current else None,
                "configuration": asdict(self._config) if self._config else None,
                "completed_runs": len(self._results), "total_runs": self._config.runs if self._config else 0,
                "summary": aggregate(self._results), "error": self._error,
                "library_id": self._library_id, "library_error": self._library_error,
                "runs": [{"run_number": row["run_number"], "seed": row["seed"],
                          "stop_reason": row["stop_reason"], "final_time": row["final_time"],
                          "final_population": row["final_statistics"]["population"]} for row in self._results]}

    def result(self, batch_id, number):
        with self._lock:
            self._check_id(batch_id)
            if type(number) is not int or not 1 <= number <= len(self._results):
                raise ValueError("Completed run not found")
            return deepcopy(self._results[number - 1])

    def export(self, batch_id):
        with self._lock:
            self._check_id(batch_id)
            metadata = self._status_report()
            metadata.pop("library_id")
            metadata.pop("library_error")
            return {**deepcopy(metadata), "schema_version": 1,
                    "engine_version": __version__, "python_version": platform.python_version(),
                    "limits": asdict(self.limits), "results": deepcopy(self._results)}

    def wait(self, timeout=None):
        """Used by headless callers/tests; never by Flask request handling."""
        if self._thread:
            self._thread.join(timeout)
