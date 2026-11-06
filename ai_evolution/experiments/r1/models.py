"""Engine data only: no rendering, biological rules, or global randomness."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Position:
    x: float
    y: float


@dataclass(frozen=True)
class Traits:
    speed: float
    vision_radius: float


@dataclass
class Organism:
    id: int
    position: Position
    traits: Traits
    energy: float
    heading: float
    founder_lineage_id: int
    parent_id: int | None = None
    generation: int = 0
    birth_time: float = 0.0
    offspring_count: int = 0
    movement_mode: str = "idle"
    actual_speed: float = 0.0

    def age_at(self, simulation_time: float) -> float:
        """Age is derived from simulation time, not accumulated per step."""
        return simulation_time - self.birth_time


@dataclass(frozen=True)
class Food:
    id: int
    position: Position
    energy: float


@dataclass(frozen=True)
class DeathRecord:
    organism: Organism
    time: float
    cause: str
    simultaneous_age: bool = False


@dataclass
class Statistics:
    food_consumed: int = 0
    starvation_deaths: int = 0
    age_deaths: int = 0
    spawn_attempts: int = 0
    spawned: int = 0
    spawns_discarded: int = 0
    initial_energy: float = 0.0
    food_energy_gained: float = 0.0
    baseline_spent: float = 0.0
    vision_spent: float = 0.0
    movement_spent: float = 0.0
    energy_removed_at_death: float = 0.0
    distance_traveled: float = 0.0


@dataclass
class WorldState:
    dt: float
    organisms: dict[int, Organism] = field(default_factory=dict)
    food: dict[int, Food] = field(default_factory=dict)
    step_count: int = 0
    next_organism_id: int = 1
    next_food_id: int = 1
    next_food_spawn_time: float | None = None
    extinction_time: float | None = None
    deaths: dict[int, DeathRecord] = field(default_factory=dict)
    statistics: Statistics = field(default_factory=Statistics)

    @property
    def time(self) -> float:
        return self.extinction_time if self.extinction_time is not None else self.step_count * self.dt

    @property
    def is_terminal(self) -> bool:
        return not self.organisms
