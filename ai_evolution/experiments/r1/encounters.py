"""Chronological straight-segment events within a fixed decision tick.

Wall hits split reflected paths into straight segments. Each iteration advances
every living organism on one shared clock, then recomputes candidates. No org
finishes its tick before a competitor's earlier arrival has been considered.
"""

from copy import deepcopy
import math
import random

from .config import SimulationConfig
from .energy import expense_rates
from .models import DeathRecord, Organism, Position, WorldState
from .movement import Motion, plan_motion
from .resources import spawn


def entry_delay(position: Position, motion: Motion, food: Position,
                radius: float, horizon: float) -> float | None:
    """First closed-disk entry along the current segment, including tangencies."""
    dx, dy = food.x - position.x, food.y - position.y
    if math.hypot(dx, dy) <= radius:
        return 0.0
    speed = motion.speed
    if speed == 0:
        return None
    ux, uy = motion.vx / speed, motion.vy / speed
    along = dx * ux + dy * uy
    perpendicular = dx * uy - dy * ux
    discriminant = radius * radius - perpendicular * perpendicular
    # Only repair ulp-scale geometric roundoff; never merge distinct event times.
    tolerance = 8 * math.ulp(max(radius * radius, perpendicular * perpendicular))
    if along < 0 or discriminant < -tolerance:
        return None
    delay = (along - math.sqrt(max(0.0, discriminant))) / speed
    if delay < 0:
        return None
    if delay > horizon:
        if delay - horizon > 8 * math.ulp(max(delay, horizon)):
            return None
        delay = horizon
    return delay


def wall_delay(position: float, velocity: float, extent: float) -> float:
    if velocity > 0:
        return (extent - position) / velocity
    if velocity < 0:
        return -position / velocity
    return math.inf


def record_death(state: WorldState, org: Organism, time: float, cause: str,
                 simultaneous_age: bool = False) -> None:
    state.statistics.energy_removed_at_death += max(0.0, org.energy)
    if cause == "starvation":
        state.statistics.starvation_deaths += 1
        org.energy = 0.0
    else:
        state.statistics.age_deaths += 1
    org.actual_speed = 0.0
    state.deaths[org.id] = DeathRecord(deepcopy(org), time, cause, simultaneous_age)
    del state.organisms[org.id]


def resolve_tick(state: WorldState, config: SimulationConfig, rng: random.Random) -> None:
    start, end = state.step_count * config.dt, (state.step_count + 1) * config.dt
    # Remove pre-existing invalid lives before any decision draws (also useful for fixtures).
    for identifier in sorted(list(state.organisms)):
        org = state.organisms[identifier]
        aged = start >= org.birth_time + config.max_lifespan
        if org.energy <= 0 or aged:
            record_death(state, org, start, "starvation" if org.energy <= 0 else "age",
                         org.energy <= 0 and aged)
    if not state.organisms:
        state.extinction_time = start
        return
    motions = {identifier: plan_motion(state.organisms[identifier], state.food, config, rng)
               for identifier in sorted(state.organisms)}
    # Use tick-relative times for geometry and convert only at the external boundary.
    now, duration = 0.0, end - start
    eaten: set[int] = set()
    stagnant = 0
    while True:
        transitions, deaths, rates, contacts = {}, {}, {}, []
        event_time = duration
        spawn_time = (state.next_food_spawn_time - start
                      if state.next_food_spawn_time is not None else math.inf)
        event_time = min(event_time, max(now, spawn_time))
        for identifier in sorted(state.organisms):
            org, motion = state.organisms[identifier], motions[identifier]
            wx = now + wall_delay(org.position.x, motion.vx, config.world_width)
            wy = now + wall_delay(org.position.y, motion.vy, config.world_height)
            transition = min(wx, wy, motion.stop_time)
            transitions[identifier] = (wx, wy, motion.stop_time)
            rates[identifier] = expense_rates(org, motion.speed, config)
            total = sum(rates[identifier])
            depletion = now + org.energy / total if total > 0 else math.inf
            age = max(now, org.birth_time + config.max_lifespan - start)
            deaths[identifier] = (depletion, age)
            event_time = min(event_time, transition, depletion, age)
            if identifier not in eaten:
                horizon = max(0.0, min(duration, transition) - now)
                # Exact broad phase: a disk outside this expanded segment box
                # cannot intersect. This avoids roots for most distant food.
                x, y = org.position.x, org.position.y
                ex, ey = x + motion.vx * horizon, y + motion.vy * horizon
                radius = config.consumption_radius
                left, right = min(x, ex) - radius, max(x, ex) + radius
                bottom, top = min(y, ey) - radius, max(y, ey) + radius
                for food_id in sorted(state.food):
                    food = state.food[food_id]
                    if food_id == motion.target_id:
                        # Pursuit is a direct radial approach. Share its analytic
                        # circle-entry time with the stop event, avoiding two
                        # independently rounded roots that can leave an org stuck
                        # one ulp outside its intended food indefinitely.
                        if now <= motion.stop_time <= duration:
                            contacts.append((motion.stop_time, food_id, identifier))
                            event_time = min(event_time, motion.stop_time)
                        continue
                    if not (left <= food.position.x <= right and bottom <= food.position.y <= top):
                        continue
                    delay = entry_delay(org.position, motion, food.position,
                                        config.consumption_radius, horizon)
                    if delay is not None:
                        arrival = now + delay
                        contacts.append((arrival, food_id, identifier))
                        event_time = min(event_time, arrival)
        if event_time < now:
            raise ArithmeticError("Event clock moved backwards")
        elapsed = event_time - now
        stagnant = stagnant + 1 if elapsed == 0 else 0
        if stagnant > len(state.organisms) + len(state.food) + 10:
            raise ArithmeticError(f"Event clock stalled at {start + now}: {transitions}")
        for identifier in sorted(state.organisms):
            org, motion = state.organisms[identifier], motions[identifier]
            org.position = Position(
                min(config.world_width, max(0.0, org.position.x + motion.vx * elapsed)),
                min(config.world_height, max(0.0, org.position.y + motion.vy * elapsed)),
            )
            baseline, vision, movement = (rate * elapsed for rate in rates[identifier])
            org.energy -= baseline + vision + movement
            stats = state.statistics
            stats.baseline_spent += baseline
            stats.vision_spent += vision
            stats.movement_spent += movement
            stats.distance_traveled += motion.speed * elapsed
        now = event_time
        # Zero energy / maximum age always preempts a meal at the same timestamp.
        for identifier in sorted(list(state.organisms)):
            org = state.organisms[identifier]
            depletion, age = deaths[identifier]
            starving, aged = depletion <= now or org.energy <= 0, age <= now
            if starving or aged:
                record_death(state, org, start + now, "starvation" if starving else "age",
                             starving and aged)
        if not state.organisms:
            state.extinction_time = start + now
            return  # No spawns or expenses after final extinction.
        if spawn_time <= now:
            spawn(state, config, rng)
            # The new item can immediately overlap an eligible organism.
            for identifier in sorted(state.organisms):
                if identifier in eaten:
                    continue
                for food_id in sorted(state.food):
                    if math.hypot(state.food[food_id].position.x - state.organisms[identifier].position.x,
                                  state.food[food_id].position.y - state.organisms[identifier].position.y) <= config.consumption_radius:
                        contacts.append((now, food_id, identifier))
        claims: dict[int, set[int]] = {}
        for arrival, food_id, identifier in contacts:
            if arrival == now and identifier in state.organisms and identifier not in eaten:
                claims.setdefault(food_id, set()).add(identifier)
        food_ids = sorted(claims)
        # Shared contenders make simultaneous foods a genuinely coupled conflict.
        contenders = [identifier for ids in claims.values() for identifier in ids]
        if len(food_ids) > 1 and len(contenders) != len(set(contenders)):
            rng.shuffle(food_ids)
        for food_id in food_ids:
            candidates = sorted(claims[food_id] - eaten)
            if not candidates or food_id not in state.food:
                continue
            winner = candidates[0] if len(candidates) == 1 else rng.choice(candidates)
            food = state.food.pop(food_id)
            org, motion = state.organisms[winner], motions[winner]
            org.energy += food.energy
            state.statistics.food_consumed += 1
            state.statistics.food_energy_gained += food.energy
            eaten.add(winner)
            motion.vx = motion.vy = 0.0
            motion.stop_time = math.inf
            org.actual_speed = 0.0
        # Apply reflected directions / planned arrival stops for survivors.
        for identifier in sorted(state.organisms):
            motion, org = motions[identifier], state.organisms[identifier]
            wx, wy, stop = transitions[identifier]
            if wx == now:
                motion.vx = -motion.vx
            if wy == now:
                motion.vy = -motion.vy
            if stop == now:
                motion.vx = motion.vy = 0.0
                motion.stop_time = math.inf
            org.actual_speed = motion.speed
            if motion.speed:
                org.heading = math.atan2(motion.vy, motion.vx) % math.tau
        if now == duration:
            return
