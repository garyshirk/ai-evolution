"""Validated R1 parameters, including settings reserved for later milestones."""

from dataclasses import dataclass, fields
import math


@dataclass(frozen=True)
class SimulationConfig:
    world_width: float = 100.0
    world_height: float = 100.0
    dt: float = 0.1
    initial_population: int = 50
    initial_food: int = 200
    food_spawn_rate: float = 8.0
    food_cap: int = 500
    food_energy: float = 10.0
    consumption_radius: float = 0.75
    speed_min: float = 0.5
    speed_max: float = 8.0
    founder_speed_min: float = 1.0
    founder_speed_max: float = 4.0
    vision_min: float = 1.0
    vision_max: float = 30.0
    founder_vision_min: float = 3.0
    founder_vision_max: float = 12.0
    starting_energy: float = 30.0
    baseline_cost: float = 0.2
    vision_cost: float = 0.1
    vision_reference: float = 10.0
    movement_cost: float = 0.05
    speed_reference: float = 2.0
    search_speed_fraction: float = 0.5
    search_turn_interval: float = 2.0
    max_lifespan: float = 200.0
    reproduction_threshold: float = 60.0
    offspring_energy: float = 25.0
    reproduction_overhead: float = 5.0
    offspring_placement_radius: float = 1.0
    speed_mutation_probability: float = 0.05
    vision_mutation_probability: float = 0.05
    speed_mutation_magnitude: float = 0.05
    vision_mutation_magnitude: float = 0.05

    def __post_init__(self) -> None:
        counts = {"initial_population", "initial_food", "food_cap"}
        nonnegative = {
            "food_spawn_rate", "baseline_cost", "vision_cost", "movement_cost",
            "reproduction_overhead", "offspring_placement_radius",
            "speed_mutation_magnitude", "vision_mutation_magnitude",
        }
        fractions = {
            "search_speed_fraction", "speed_mutation_probability",
            "vision_mutation_probability",
        }
        for field in fields(self):
            name = field.name
            value = getattr(self, name)
            if name in counts:
                if type(value) is not int or value < 0:
                    raise ValueError(f"{name} must be a nonnegative integer")
                continue
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError(f"{name} must be a finite number")
            if name in fractions:
                if not 0 <= value <= 1:
                    raise ValueError(f"{name} must be between 0 and 1")
            elif name in nonnegative:
                if value < 0:
                    raise ValueError(f"{name} must be nonnegative")
            elif value <= 0:
                raise ValueError(f"{name} must be positive")

        if self.initial_food > self.food_cap:
            raise ValueError("initial_food must not exceed food_cap")
        for trait in ("speed", "vision"):
            lower = getattr(self, f"{trait}_min")
            upper = getattr(self, f"{trait}_max")
            founder_lower = getattr(self, f"founder_{trait}_min")
            founder_upper = getattr(self, f"founder_{trait}_max")
            if not lower < upper:
                raise ValueError(f"{trait}_min must be less than {trait}_max")
            if not lower <= founder_lower <= founder_upper <= upper:
                raise ValueError(f"founder {trait} range must lie within trait bounds")
