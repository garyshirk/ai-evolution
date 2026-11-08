"""Seeded survival, resource competition, and tick-end asexual evolution."""

from copy import deepcopy
import math
import random

from .config import SimulationConfig
from .models import Food, Organism, Position, Traits, WorldState
from .encounters import resolve_tick
from .resources import next_arrival
from .reproduction import reproduce
from .metrics import DEFAULT_HISTORY_LIMIT, DEFAULT_SAMPLING_INTERVAL, MetricsCollector, measure


class Simulation:
    def __init__(self, config: SimulationConfig | None = None, *, seed: int = 0,
                 collect_metrics: bool = True, sampling_interval: float = DEFAULT_SAMPLING_INTERVAL,
                 history_limit: int = DEFAULT_HISTORY_LIMIT):
        if type(seed) is not int:
            raise ValueError("seed must be an integer")
        if config is not None and not isinstance(config, SimulationConfig):
            raise TypeError("config must be a SimulationConfig")
        self._config = config if config is not None else SimulationConfig()
        self._seed = seed
        self._collect_metrics = collect_metrics
        self._sampling_interval = sampling_interval
        self._history_limit = history_limit
        self.reset()

    @property
    def config(self) -> SimulationConfig:
        return self._config

    @property
    def seed(self) -> int:
        return self._seed

    def snapshot(self) -> WorldState:
        """Return a detached state; inspection cannot mutate the live engine."""
        return deepcopy(self._state)

    def reset(self) -> None:
        """Rebuild the same initialized experiment, including RNG and IDs."""
        self._rng = random.Random(self.seed)
        self._state = WorldState(dt=self.config.dt)
        for _ in range(self.config.initial_population):
            identifier = self._state.next_organism_id
            # Draw order is part of the reproducibility contract for this version.
            position = self._random_position()
            traits = Traits(
                speed=self._rng.uniform(
                    self.config.founder_speed_min, self.config.founder_speed_max
                ),
                vision_radius=self._rng.uniform(
                    self.config.founder_vision_min, self.config.founder_vision_max
                ),
            )
            self._state.organisms[identifier] = Organism(
                id=identifier, position=position, traits=traits,
                energy=self.config.starting_energy,
                heading=self._rng.random() * math.tau,
                founder_lineage_id=identifier,
            )
            self._state.next_organism_id += 1
        for _ in range(self.config.initial_food):
            identifier = self._state.next_food_id
            self._state.food[identifier] = Food(
                id=identifier, position=self._random_position(),
                energy=self.config.food_energy,
            )
            self._state.next_food_id += 1
        self._state.statistics.initial_energy = self.config.initial_population * self.config.starting_energy
        self._state.next_food_spawn_time = next_arrival(0.0, self.config.food_spawn_rate, self._rng)
        if self._state.is_terminal:
            self._state.extinction_time = 0.0
        self._metrics = (MetricsCollector(self.config.dt, interval=self._sampling_interval,
                                         history_limit=self._history_limit) if self._collect_metrics else None)
        if self._metrics is not None:
            self._metrics.observe(self._state, self.config)

    def metric_history(self, after_sequence: int | None = None) -> dict:
        if self._metrics is None:
            return {"enabled": False, "samples": [], "latest_sequence": -1}
        return self._metrics.history(after_sequence)

    def reporting_metadata(self) -> dict:
        return self._metrics.metadata() if self._metrics is not None else {"enabled": False}

    def current_metrics(self):
        return measure(self._state, self.config, previous=self._metrics.latest if self._metrics else None)

    def _random_position(self) -> Position:
        return Position(
            self._rng.random() * self.config.world_width,
            self._rng.random() * self.config.world_height,
        )

    def step(self) -> bool:
        """Resolve one decision tick (possibly terminating early at extinction)."""
        if self._state.is_terminal:
            return False
        resolve_tick(self._state, self.config, self._rng)
        self._state.step_count += 1
        if not self._state.is_terminal:
            reproduce(self._state, self.config, self._rng)
        if self._metrics is not None:
            self._metrics.observe(self._state, self.config)
        return True

    def advance(self, steps: int) -> int:
        """Advance up to N ticks, returning the number actually completed."""
        if type(steps) is not int or steps < 0:
            raise ValueError("steps must be a nonnegative integer")
        completed = 0
        for _ in range(steps):
            if not self.step():
                break
            completed += 1
        return completed
