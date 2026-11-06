"""Continuous energy rates; no UI or randomness."""

from .config import SimulationConfig
from .models import Organism


def expense_rates(org: Organism, speed: float, config: SimulationConfig) -> tuple[float, float, float]:
    return (config.baseline_cost,
            config.vision_cost * (org.traits.vision_radius / config.vision_reference) ** 2,
            config.movement_cost * speed * (speed / config.speed_reference) ** 2)
