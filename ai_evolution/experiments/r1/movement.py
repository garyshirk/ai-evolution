"""Persistent random search and rectangular reflection, with no interactions."""

import math
import random

from .config import SimulationConfig
from .models import Organism, Position


def reflect_axis(position: float, velocity: float, duration: float,
                 extent: float) -> tuple[float, float]:
    """Fold an unfolded path into [0, extent], including multiple wall hits.

    At an exact wall endpoint the returned velocity points into the world.
    This computes endpoints only; swept segments belong to Milestone C.
    """
    phase = (position + velocity * duration) % (2 * extent)
    if phase == 0:
        return 0.0, abs(velocity)
    if phase == extent:
        return extent, -abs(velocity)
    if phase < extent:
        return phase, velocity
    return 2 * extent - phase, -velocity


def search(org: Organism, config: SimulationConfig, rng: random.Random) -> None:
    """Advance one search tick, using only the supplied run generator."""
    turn_probability = -math.expm1(-config.dt / config.search_turn_interval)
    if rng.random() < turn_probability:
        org.heading = rng.random() * math.tau
    speed = org.traits.speed * config.search_speed_fraction
    vx, vy = speed * math.cos(org.heading), speed * math.sin(org.heading)
    x, vx = reflect_axis(org.position.x, vx, config.dt, config.world_width)
    y, vy = reflect_axis(org.position.y, vy, config.dt, config.world_height)
    org.position = Position(x, y)
    if speed:
        org.heading = math.atan2(vy, vx) % math.tau
    org.actual_speed = speed
    org.movement_mode = "search"
