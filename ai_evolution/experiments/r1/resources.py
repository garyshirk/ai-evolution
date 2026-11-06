"""Poisson arrivals in simulated time, independent of population and food count."""

import math
import random

from .config import SimulationConfig
from .models import Food, Position, WorldState


def next_arrival(now: float, rate: float, rng: random.Random) -> float | None:
    if rate == 0:
        return None
    uniform = rng.random()
    while uniform == 0:  # Open interval (0, 1), so the waiting time is positive.
        uniform = rng.random()
    candidate = now - math.log(uniform) / rate
    # Strict progress even if a positive wait rounds back to the same timestamp.
    return max(candidate, math.nextafter(now, math.inf))


def spawn(state: WorldState, config: SimulationConfig, rng: random.Random) -> None:
    """Resolve one scheduled arrival, then schedule another even at the cap."""
    state.statistics.spawn_attempts += 1
    if len(state.food) < config.food_cap:
        identifier = state.next_food_id
        state.food[identifier] = Food(identifier, Position(
            rng.random() * config.world_width, rng.random() * config.world_height,
        ), config.food_energy)
        state.next_food_id += 1
        state.statistics.spawned += 1
    else:
        state.statistics.spawns_discarded += 1
    state.next_food_spawn_time = next_arrival(state.next_food_spawn_time, config.food_spawn_rate, rng)
