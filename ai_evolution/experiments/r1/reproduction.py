"""Asexual births with energetic transfers and independent, undirected mutation."""

import math
import random

from .config import SimulationConfig
from .models import Organism, Position, Traits, WorldState


def reflect_value(value: float, lower: float, upper: float) -> float:
    """Reflect any number of overshoots without piling values onto the bounds."""
    if lower <= value <= upper:
        return value
    width = upper - lower
    phase = (value - lower) % (2 * width)
    return lower + (phase if phase <= width else 2 * width - phase)


def mutate_trait(value: float, lower: float, upper: float, probability: float,
                 magnitude: float, rng: random.Random) -> tuple[float, bool]:
    """Return the inherited value and whether the independent mutation test fired.

    A zero-magnitude event is still an event, but leaves the trait exactly intact.
    Mutation probability and magnitude are validated by SimulationConfig.
    """
    if rng.random() >= probability:
        return value, False
    delta = rng.uniform(-magnitude * (upper - lower), magnitude * (upper - lower))
    return reflect_value(value + delta, lower, upper), True


def eligible(parent: Organism, config: SimulationConfig) -> bool:
    allocation = config.offspring_energy + config.reproduction_overhead
    return parent.energy > config.reproduction_threshold and parent.energy - allocation > 0


def reproduce(state: WorldState, config: SimulationConfig, rng: random.Random) -> None:
    """Tick-end births: only the existing parents are considered, once each.

    Draw order per eligible parent: speed test/delta, vision test/delta,
    radial uniform, placement angle, newborn heading. IDs follow parent-ID order.
    Newborns are inserted only after every parent has been considered.
    """
    newborns = []
    for identifier in sorted(state.organisms):
        parent = state.organisms[identifier]
        if not eligible(parent, config):
            continue
        speed, speed_mutated = mutate_trait(
            parent.traits.speed, config.speed_min, config.speed_max,
            config.speed_mutation_probability, config.speed_mutation_magnitude, rng,
        )
        vision, vision_mutated = mutate_trait(
            parent.traits.vision_radius, config.vision_min, config.vision_max,
            config.vision_mutation_probability, config.vision_mutation_magnitude, rng,
        )
        radius = config.offspring_placement_radius * math.sqrt(rng.random())
        angle = math.tau * rng.random()
        position = Position(
            reflect_value(parent.position.x + radius * math.cos(angle), 0, config.world_width),
            reflect_value(parent.position.y + radius * math.sin(angle), 0, config.world_height),
        )
        child = Organism(
            id=state.next_organism_id, position=position, traits=Traits(speed, vision),
            energy=config.offspring_energy, heading=math.tau * rng.random(),
            founder_lineage_id=parent.founder_lineage_id, parent_id=parent.id,
            generation=parent.generation + 1, birth_time=state.time,
        )
        state.next_organism_id += 1
        parent.energy -= config.offspring_energy + config.reproduction_overhead
        parent.offspring_count += 1
        stats = state.statistics
        stats.births += 1
        stats.highest_generation = max(stats.highest_generation, child.generation)
        stats.offspring_energy_transferred += config.offspring_energy
        stats.reproduction_overhead_spent += config.reproduction_overhead
        stats.speed_mutations += int(speed_mutated)
        stats.vision_mutations += int(vision_mutated)
        newborns.append(child)
    state.organisms.update((child.id, child) for child in newborns)
