"""Descriptive measurements only: no model writes and no random draws."""

from bisect import bisect_right
from collections import deque
from dataclasses import asdict, dataclass
import math

from .config import SimulationConfig
from .models import WorldState


@dataclass(frozen=True, slots=True)
class MetricSample:
    sequence: int | None
    sample_type: str
    time: float
    step: int
    terminal: bool
    population: int
    initial_population: int
    total_births: int
    total_deaths: int
    starvation_deaths: int
    age_deaths: int
    highest_generation: int
    mean_speed: float | None
    mean_vision: float | None
    speed_stddev: float | None
    vision_stddev: float | None
    births_since_previous: int
    deaths_since_previous: int
    food_consumed: int


def measure(state: WorldState, config: SimulationConfig, *, sequence: int | None = None,
            sample_type: str = "current", previous: MetricSample | None = None) -> MetricSample:
    summary = state.summary()
    organisms = [state.organisms[key] for key in sorted(state.organisms)]
    count = len(organisms)
    mean_speed, mean_vision = summary["mean_speed"], summary["mean_vision"]
    speed_sd = math.sqrt(math.fsum((org.traits.speed - mean_speed) ** 2 for org in organisms) / count) if count else None
    vision_sd = math.sqrt(math.fsum((org.traits.vision_radius - mean_vision) ** 2 for org in organisms) / count) if count else None
    stats = state.statistics
    deaths = stats.starvation_deaths + stats.age_deaths
    return MetricSample(
        sequence, sample_type, state.time, state.step_count, state.is_terminal,
        count, config.initial_population, stats.births, deaths,
        stats.starvation_deaths, stats.age_deaths, stats.highest_generation,
        mean_speed, mean_vision, speed_sd, vision_sd,
        stats.births - (previous.total_births if previous else 0),
        deaths - (previous.total_deaths if previous else 0), stats.food_consumed,
    )


def histogram(values, lower: float, upper: float, bins: int = 10) -> dict:
    """Left-closed/right-open bins; the final bin includes the upper limit."""
    if type(bins) is not int or bins < 1 or not lower < upper:
        raise ValueError("Histogram requires positive bin count and increasing bounds")
    edges = [lower + (upper - lower) * index / bins for index in range(bins + 1)]
    edges[-1] = upper
    counts = [0] * bins
    for value in values:
        if not math.isfinite(value) or not lower <= value <= upper:
            raise ValueError("Histogram value is outside the allowed trait range")
        counts[min(bins - 1, bisect_right(edges, value) - 1)] += 1
    return {"edges": edges, "counts": counts}


def distributions(state: WorldState, config: SimulationConfig) -> dict:
    organisms = state.organisms.values()
    return {
        "speed": histogram((org.traits.speed for org in organisms), config.speed_min, config.speed_max),
        "vision": histogram((org.traits.vision_radius for org in organisms), config.vision_min, config.vision_max),
    }


class MetricsCollector:
    """Retain initial state plus a bounded rolling window of immutable samples.

    Sampling uses completed ticks, after reproduction. A non-dividing custom dt
    rounds the requested interval up to whole ticks; it never splits physics or
    invents interpolated biological states. Default dt=0.1 samples exactly at 1.
    """
    def __init__(self, dt: float, *, interval: float = 1.0, history_limit: int = 10000):
        if type(dt) not in (float, int) or not math.isfinite(dt) or dt <= 0:
            raise ValueError("Metrics dt must be finite and positive")
        if type(interval) not in (float, int) or not math.isfinite(interval) or interval <= 0:
            raise ValueError("Metrics interval must be finite and positive")
        if type(history_limit) is not int or history_limit < 2:
            raise ValueError("Metrics history limit must be an integer at least 2")
        self.requested_interval = interval
        self.every_steps = max(1, math.ceil(interval / dt))
        self.effective_interval = self.every_steps * dt
        self.history_limit = history_limit
        self._initial: MetricSample | None = None
        self._recent: deque[MetricSample] = deque(maxlen=history_limit - 1)
        self.total_samples = 0

    @property
    def latest(self) -> MetricSample | None:
        return self._recent[-1] if self._recent else self._initial

    def observe(self, state: WorldState, config: SimulationConfig) -> None:
        if self.latest is not None and self.latest.step == state.step_count:
            return
        if self._initial is not None and not state.is_terminal and state.step_count % self.every_steps:
            return
        kind = "initial" if self._initial is None else "terminal" if state.is_terminal else "regular"
        sample = measure(state, config, sequence=self.total_samples, sample_type=kind, previous=self.latest)
        if self._initial is None:
            self._initial = sample
        else:
            self._recent.append(sample)
        self.total_samples += 1

    def metadata(self) -> dict:
        retained = int(self._initial is not None) + len(self._recent)
        return {
            "enabled": True, "requested_interval": self.requested_interval,
            "effective_interval": self.effective_interval, "sample_every_steps": self.every_steps,
            "history_limit": self.history_limit, "total_samples": self.total_samples,
            "retained_samples": retained, "dropped_samples": self.total_samples - retained,
            "latest_sequence": self.total_samples - 1,
        }

    def history(self, after_sequence: int | None = None) -> dict:
        if after_sequence is not None and (type(after_sequence) is not int or after_sequence < -1):
            raise ValueError("History cursor must be an integer at least -1")
        replace = (after_sequence is None or after_sequence < 0 or after_sequence >= self.total_samples
                   or bool(self._recent and after_sequence < self._recent[0].sequence - 1))
        samples = ([self._initial] if self._initial is not None and replace else [])
        samples += [sample for sample in self._recent if replace or sample.sequence > after_sequence]
        return {**self.metadata(), "replace": replace, "samples": [asdict(sample) for sample in samples]}
