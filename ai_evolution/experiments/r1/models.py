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


@dataclass
class WorldState:
    dt: float
    organisms: dict[int, Organism] = field(default_factory=dict)
    food: dict[int, Food] = field(default_factory=dict)
    step_count: int = 0
    next_organism_id: int = 1
    next_food_id: int = 1

    @property
    def time(self) -> float:
        return self.step_count * self.dt

    @property
    def is_terminal(self) -> bool:
        return not self.organisms
