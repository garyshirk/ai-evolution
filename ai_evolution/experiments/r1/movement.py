"""Tick-start sensing, persistent search, and reflected movement primitives."""

import math
import random
from dataclasses import dataclass

from .config import SimulationConfig
from .models import Food, Organism, Position


@dataclass
class Motion:
    vx: float
    vy: float
    stop_time: float = math.inf
    target_id: int | None = None

    @property
    def speed(self) -> float:
        return math.hypot(self.vx, self.vy)


def nearest_visible(org: Organism, food: dict[int, Food]) -> Food | None:
    candidates = ((math.hypot(item.position.x - org.position.x,
                              item.position.y - org.position.y), item.id, item)
                  for item in food.values())
    visible = [candidate for candidate in candidates if candidate[0] <= org.traits.vision_radius]
    return min(visible, key=lambda candidate: candidate[:2])[2] if visible else None


def plan_motion(org: Organism, food: dict[int, Food], config: SimulationConfig,
                rng: random.Random) -> Motion:
    """One decision per tick. Losing a target does not cause mid-tick replanning."""
    target = nearest_visible(org, food)
    if target is not None:
        org.movement_mode = "pursue"
        dx, dy = target.position.x - org.position.x, target.position.y - org.position.y
        distance = math.hypot(dx, dy)
        if distance <= config.consumption_radius:
            org.actual_speed = 0.0
            return Motion(0.0, 0.0)
        org.heading = math.atan2(dy, dx) % math.tau
        org.actual_speed = org.traits.speed
        return Motion(org.actual_speed * dx / distance, org.actual_speed * dy / distance,
                      (distance - config.consumption_radius) / org.actual_speed, target.id)
    org.movement_mode = "search"
    turn_probability = -math.expm1(-config.dt / config.search_turn_interval)
    if rng.random() < turn_probability:
        org.heading = rng.random() * math.tau
    org.actual_speed = org.traits.speed * config.search_speed_fraction
    return Motion(org.actual_speed * math.cos(org.heading), org.actual_speed * math.sin(org.heading))


def reflect_axis(position: float, velocity: float, duration: float,
                 extent: float) -> tuple[float, float]:
    """Fold an unfolded path into [0, extent], including multiple wall hits.

    At an exact wall endpoint the returned velocity points into the world.
    This helper computes endpoints; the event resolver splits paths at walls.
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
    motion = plan_motion(org, {}, config, rng)
    speed = org.actual_speed
    vx, vy = motion.vx, motion.vy
    x, vx = reflect_axis(org.position.x, vx, config.dt, config.world_width)
    y, vy = reflect_axis(org.position.y, vy, config.dt, config.world_height)
    org.position = Position(x, y)
    if speed:
        org.heading = math.atan2(vy, vx) % math.tau
    org.actual_speed = speed
    org.movement_mode = "search"
