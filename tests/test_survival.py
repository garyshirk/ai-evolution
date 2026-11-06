"""Small explicit worlds test causal physics without relying on calibration."""
from dataclasses import asdict
import math
import random
import unittest
from unittest.mock import Mock

from ai_evolution.experiments.r1 import Simulation, SimulationConfig
from ai_evolution.experiments.r1.encounters import entry_delay
from ai_evolution.experiments.r1.energy import expense_rates
from ai_evolution.experiments.r1.models import Food, Organism, Position, Traits
from ai_evolution.experiments.r1.movement import Motion, nearest_visible, plan_motion
from ai_evolution.experiments.r1.resources import next_arrival


def organism(identifier=1, x=1, y=5, speed=2, vision=10, energy=30, heading=0):
    return Organism(identifier, Position(x, y), Traits(speed, vision), energy, heading, identifier)


def world(orgs, foods=(), seed=4, **changes):
    values = dict(initial_population=len(orgs), initial_food=0, food_spawn_rate=0,
                  baseline_cost=0, vision_cost=0, movement_cost=0,
                  consumption_radius=0.25, search_turn_interval=1e30, dt=1,
                  max_lifespan=1000)
    values.update(changes)
    simulation = Simulation(SimulationConfig(**values), seed=seed)
    simulation._state.organisms = {org.id: org for org in orgs}
    simulation._state.food = {food.id: food for food in foods}
    simulation._state.next_food_id = max(simulation._state.food, default=0) + 1
    simulation._state.statistics.initial_energy = sum(org.energy for org in orgs)
    return simulation


class DetectionAndGeometryTests(unittest.TestCase):
    def test_nearest_visible_and_exact_range(self):
        org = organism(vision=2)
        far = Food(1, Position(4, 5), 10)
        edge = Food(2, Position(3, 5), 10)
        near = Food(3, Position(2, 5), 10)
        self.assertIsNone(nearest_visible(org, {1: far}))
        self.assertEqual(nearest_visible(org, {2: edge}), edge)
        self.assertEqual(nearest_visible(org, {2: edge, 3: near}), near)
        tie = Food(4, Position(0, 5), 10)
        self.assertEqual(nearest_visible(org, {4: tie, 3: near}), near)

    def test_search_vs_pursuit_speed(self):
        config = SimulationConfig()
        org = organism(speed=4)
        self.assertEqual(plan_motion(org, {}, config, random.Random(2)).speed, 2)
        food = Food(1, Position(5, 5), 10)
        self.assertEqual(plan_motion(org, {1: food}, config, random.Random(2)).speed, 4)
        self.assertEqual(org.movement_mode, 'pursue')

    def test_tangency_overlap_stationary_and_miss(self):
        motion = Motion(2, 0)
        self.assertEqual(entry_delay(Position(0, 0), motion, Position(2, 1), 1, 2), 1)
        self.assertEqual(entry_delay(Position(0, 0), Motion(0, 0), Position(0, 0), 1, 2), 0)
        self.assertIsNone(entry_delay(Position(0, 0), motion, Position(2, 2), 1, 2))
        self.assertIsNone(entry_delay(Position(0, 0), motion, Position(20, 0), 1, 2))
        self.assertIsNone(entry_delay(Position(0, 0), motion, Position(-2, 0), 1, 2))

    def test_search_path_crosses_food_and_stops(self):
        sim = world([organism(speed=8, vision=0.5)], [Food(1, Position(3, 5), 10)])
        sim.step()
        state = sim.snapshot()
        self.assertEqual(state.food, {})
        self.assertAlmostEqual(state.organisms[1].position.x, 2.75)
        self.assertEqual(state.organisms[1].energy, 40)
        self.assertEqual(state.organisms[1].actual_speed, 0)
        self.assertAlmostEqual(state.statistics.distance_traveled, 1.75)

    def test_reflected_path_food_and_true_distance_cost(self):
        sim = world([organism(x=9, speed=4, vision=0.1)],
                    [Food(1, Position(8, 5), 10)], dt=2, world_width=10,
                    movement_cost=1, speed_reference=2)
        sim.step()
        state = sim.snapshot()
        self.assertAlmostEqual(state.organisms[1].position.x, 8.25)
        self.assertAlmostEqual(state.statistics.distance_traveled, 2.75)
        self.assertAlmostEqual(state.statistics.movement_spent, 2.75)
        self.assertAlmostEqual(state.organisms[1].energy, 37.25)

    def test_multiple_reflections_and_endpoint_food(self):
        sim = world([organism(x=0.5, y=0.5, speed=8, vision=0.01)],
                    [Food(1, Position(0.1, 0.5), 10)], dt=1,
                    world_width=1, world_height=1, consumption_radius=0.01)
        sim.step()
        self.assertEqual(sim.snapshot().statistics.food_consumed, 1)
        self.assertAlmostEqual(sim.snapshot().organisms[1].position.x, 0.11)
        self.assertAlmostEqual(sim.snapshot().statistics.distance_traveled, 1.39)

    def test_meal_at_tick_endpoint_is_not_missed_or_repeated(self):
        sim = world([organism()], [Food(1, Position(3.25, 5), 10)])
        sim.step()
        self.assertEqual(sim.snapshot().statistics.food_consumed, 1)
        self.assertEqual(sim.snapshot().organisms[1].position.x, 3)
        sim.step()
        self.assertEqual(sim.snapshot().statistics.food_consumed, 1)

    def test_diagonal_pursuit_does_not_stick_outside_consumption_circle(self):
        for angle in (0.1, 0.7, 1.2, 2.5, 4.8, 5.9):
            with self.subTest(angle=angle):
                target = Position(50 + 3.14159 * math.cos(angle), 50 + 3.14159 * math.sin(angle))
                sim = world([organism(x=50, y=50, speed=2.26171474249)],
                            [Food(1, target, 10)], dt=0.1)
                sim.advance(20)
                self.assertEqual(sim.snapshot().statistics.food_consumed, 1)
                self.assertEqual(sim.snapshot().food, {})

    def test_one_meal_and_resume_next_tick(self):
        sim = world([organism()], [Food(1, Position(1, 5), 10), Food(2, Position(1, 5), 10)])
        sim.step()
        self.assertEqual(sim.snapshot().statistics.food_consumed, 1)
        self.assertEqual(sim.snapshot().organisms[1].position, Position(1, 5))
        sim.step()
        self.assertEqual(sim.snapshot().statistics.food_consumed, 2)

    def test_loser_follows_old_plan_then_replans(self):
        sim = world([organism(1, x=1, speed=2), organism(2, x=4, speed=1)],
                    [Food(1, Position(5, 5), 10)], dt=3)
        sim.step()
        self.assertAlmostEqual(sim.snapshot().organisms[1].position.x, 4.75)
        self.assertEqual(sim.snapshot().organisms[1].energy, 30)
        sim.step()
        self.assertEqual(sim.snapshot().organisms[1].movement_mode, 'search')


class CompetitionTests(unittest.TestCase):
    def test_earliest_arrival_not_lowest_id_wins(self):
        sim = world([organism(1, x=1, speed=2), organism(2, x=4, speed=1)],
                    [Food(1, Position(5, 5), 10)], dt=3)
        sim.step()
        self.assertEqual(sim.snapshot().organisms[2].energy, 40)
        self.assertEqual(sim.snapshot().organisms[1].energy, 30)

    def tied(self, seed, reverse=False, multiple=False):
        orgs = [organism(1, x=3), organism(2, x=7)]
        foods = [Food(1, Position(5, 5), 10)]
        if multiple:
            orgs = [organism(1, x=5), organism(2, x=5)]
            foods.append(Food(2, Position(5, 5), 20))
        sim = world(list(reversed(orgs)) if reverse else orgs,
                    list(reversed(foods)) if reverse else foods, seed=seed)
        sim.step()
        return sim.snapshot()

    def test_ties_replay_and_ignore_storage_order(self):
        self.assertEqual(self.tied(7), self.tied(7, reverse=True))
        winners = {1: 0, 2: 0}
        for seed in range(100):
            state = self.tied(seed)
            winner = next(org.id for org in state.organisms.values() if org.energy == 40)
            winners[winner] += 1
        self.assertTrue(25 < winners[1] < 75, winners)

    def test_multifood_ties_are_seeded_and_fair(self):
        first_food = set()
        for seed in range(30):
            state = self.tied(seed, multiple=True)
            self.assertEqual(state, self.tied(seed, reverse=True, multiple=True))
            self.assertEqual(state.statistics.food_consumed, 2)
            self.assertEqual(sorted(org.energy for org in state.organisms.values()), [40, 50])
            first_food.add(state.organisms[1].energy)
        self.assertEqual(first_food, {40, 50})


class EnergyAndDeathTests(unittest.TestCase):
    def assert_ledger(self, state):
        stats = state.statistics
        expected = (stats.initial_energy + stats.food_energy_gained - stats.baseline_spent
                    - stats.vision_spent - stats.movement_spent - stats.energy_removed_at_death
                    - stats.reproduction_overhead_spent)
        self.assertAlmostEqual(sum(org.energy for org in state.organisms.values()), expected, places=9)

    def test_cost_rates_and_quadratic_cost_per_distance(self):
        org = organism(vision=20)
        config = SimulationConfig()
        baseline, vision, movement = expense_rates(org, 2, config)
        self.assertEqual(baseline, 0.2)
        self.assertEqual(vision, 0.4)
        self.assertEqual(movement, 0.1)
        self.assertAlmostEqual(movement / 2, 4 * expense_rates(org, 1, config)[2])

    def test_stationary_upkeep_and_larger_vision(self):
        sim = world([organism(vision=20)], search_speed_fraction=0, baseline_cost=1, vision_cost=2)
        sim.step()
        self.assertEqual(sim.snapshot().organisms[1].energy, 21)
        self.assert_ledger(sim.snapshot())

    def test_depletion_before_food_stops_at_exact_position(self):
        sim = world([organism(energy=0.5)], [Food(1, Position(3, 5), 10)], baseline_cost=1)
        self.assertEqual(sim.advance(5), 1)
        state = sim.snapshot()
        self.assertTrue(state.is_terminal)
        self.assertEqual(state.time, 0.5)
        self.assertEqual(state.deaths[1].organism.position, Position(2, 5))
        self.assertEqual(state.deaths[1].cause, 'starvation')
        self.assertEqual(len(state.food), 1)
        self.assertEqual(state.statistics.food_consumed, 0)
        self.assert_ledger(state)
        before = sim.snapshot()
        self.assertEqual(sim.advance(10), 0)
        self.assertEqual(sim.snapshot(), before)

    def test_exact_food_depletion_tie_dies_and_cannot_eat(self):
        sim = world([organism(energy=0.875)], [Food(1, Position(3, 5), 10)], baseline_cost=1)
        sim.step()
        state = sim.snapshot()
        self.assertEqual(state.time, 0.875)
        self.assertEqual(state.deaths[1].organism.position, Position(2.75, 5))
        self.assertEqual(state.statistics.food_consumed, 0)
        self.assert_ledger(state)

    def test_reach_food_before_depletion_includes_waiting_upkeep(self):
        sim = world([organism(energy=1)], [Food(1, Position(3, 5), 10)], baseline_cost=1)
        sim.step()
        state = sim.snapshot()
        self.assertEqual(state.organisms[1].energy, 10)
        self.assertAlmostEqual(state.statistics.baseline_spent, 1)
        self.assert_ledger(state)

    def test_all_costs_limit_reach_and_no_borrowing(self):
        sim = world([organism(energy=1, vision=10)], [Food(1, Position(4, 5), 10)],
                    baseline_cost=1, vision_cost=1, movement_cost=1)
        sim.step()
        state = sim.snapshot()
        self.assertAlmostEqual(state.time, 0.25)  # rate 1 + 1 + 2
        self.assertAlmostEqual(state.deaths[1].organism.position.x, 1.5)
        self.assert_ledger(state)

    def test_age_death_truncates_motion_and_removes_reserve(self):
        sim = world([organism()], max_lifespan=0.25, baseline_cost=1)
        sim.step()
        state = sim.snapshot()
        self.assertEqual(state.time, 0.25)
        self.assertEqual(state.deaths[1].cause, 'age')
        self.assertFalse(state.deaths[1].simultaneous_age)
        self.assertEqual(state.statistics.age_deaths, 1)
        self.assertAlmostEqual(state.deaths[1].organism.position.x, 1.25)
        self.assert_ledger(state)

    def test_age_preempts_meal_and_combined_death_cause(self):
        sim = world([organism(energy=0.875)], [Food(1, Position(3, 5), 10)],
                    max_lifespan=0.875, baseline_cost=1)
        sim.step()
        death = sim.snapshot().deaths[1]
        self.assertEqual(death.cause, 'starvation')
        self.assertTrue(death.simultaneous_age)
        self.assertEqual(sim.snapshot().statistics.food_consumed, 0)

    def test_population_can_only_decline(self):
        sim = Simulation(SimulationConfig(initial_population=5, max_lifespan=0.35), seed=5)
        populations = []
        for _ in range(10):
            sim.step()
            populations.append(len(sim.snapshot().organisms))
        self.assertEqual(populations, sorted(populations, reverse=True))
        self.assertEqual(populations[-1], 0)
        self.assert_ledger(sim.snapshot())

    def test_seeded_small_worlds_reconcile_after_many_events(self):
        config = SimulationConfig(initial_population=4, initial_food=10,
                                  world_width=5, world_height=7, max_lifespan=2,
                                  starting_energy=1, food_energy=0.5, food_spawn_rate=3)
        for seed in range(10):
            sim = Simulation(config, seed=seed)
            previous = config.initial_population
            for _ in range(25):
                sim.step()
                state = sim.snapshot()
                self.assertLessEqual(len(state.organisms), previous)
                previous = len(state.organisms)
                for org in state.organisms.values():
                    self.assertGreater(org.energy, 0)
                    self.assertTrue(0 <= org.position.x <= config.world_width)
                    self.assertTrue(0 <= org.position.y <= config.world_height)
                self.assert_ledger(state)
            self.assertTrue(state.is_terminal)


class SpawningAndReplayTests(unittest.TestCase):
    def test_positive_waits_and_zero_rate(self):
        self.assertIsNone(next_arrival(0, 0, random.Random(1)))
        self.assertGreater(next_arrival(1, 10, Mock(random=Mock(side_effect=[0, 0.5]))), 1)
        rng = random.Random(72)
        waits = [next_arrival(0, 2, rng) for _ in range(10000)]
        self.assertAlmostEqual(sum(waits) / len(waits), 0.5, delta=0.025)

    def test_spawn_at_actual_time_can_rescue_stationary_org(self):
        sim = world([organism(x=50, y=50, energy=0.075)], dt=0.1,
                    food_spawn_rate=1, baseline_cost=1, search_speed_fraction=0)
        sim._state.next_food_spawn_time = 0.05
        sim._rng = Mock(random=Mock(return_value=0.5))
        sim.step()
        state = sim.snapshot()
        self.assertAlmostEqual(state.organisms[1].energy, 9.975)
        self.assertEqual(state.statistics.spawned, 1)
        self.assertEqual(state.statistics.food_consumed, 1)

    def test_no_spawn_after_extinction_or_before_creation(self):
        sim = world([organism(energy=0.025)], dt=0.1, food_spawn_rate=1, baseline_cost=1)
        sim._state.next_food_spawn_time = 0.05
        sim.step()
        self.assertEqual(sim.snapshot().statistics.spawned, 0)
        self.assertEqual(sim.snapshot().time, 0.025)

    def test_cap_discards_but_does_not_accumulate_spawn_backlog(self):
        sim = world([organism(x=1, vision=0.1)], [Food(1, Position(90, 90), 10)],
                    dt=1, food_cap=1, food_spawn_rate=20)
        sim.advance(3)
        state = sim.snapshot()
        self.assertEqual(len(state.food), 1)
        self.assertGreater(state.statistics.spawn_attempts, 10)
        self.assertEqual(state.statistics.spawned, 0)
        self.assertEqual(state.statistics.spawns_discarded, state.statistics.spawn_attempts)
        self.assertGreater(state.next_food_spawn_time, state.time)

    def test_cap_is_applied_before_simultaneous_consumption(self):
        sim = world([organism(x=50, y=50)], [Food(1, Position(50, 50), 10)],
                    food_spawn_rate=1, food_cap=1)
        sim._state.next_food_spawn_time = 0.0
        sim._rng = Mock(random=Mock(return_value=0.5))
        sim.step()
        state = sim.snapshot()
        self.assertEqual(state.statistics.spawns_discarded, 1)
        self.assertEqual(state.statistics.food_consumed, 1)

    def test_consumed_food_does_not_regenerate_at_old_location(self):
        sim = world([organism(x=1, y=5)], [Food(1, Position(1, 5), 10)],
                    food_spawn_rate=1, dt=0.1)
        sim._state.next_food_spawn_time = 0.05
        sim._rng = Mock(random=Mock(return_value=0.5))
        sim.step()
        state = sim.snapshot()
        self.assertNotIn(1, state.food)
        self.assertEqual(state.food[2].position, Position(50, 50))

    def test_same_seed_batches_and_order_independent_complete_states(self):
        config = SimulationConfig(initial_population=8, initial_food=30)
        a, b = Simulation(config, seed=84), Simulation(config, seed=84)
        b._state.organisms = dict(reversed(list(b._state.organisms.items())))
        b._state.food = dict(reversed(list(b._state.food.items())))
        a.advance(100)
        for _ in range(100):
            b.step()
            b.snapshot()
        self.assertEqual(asdict(a.snapshot()), asdict(b.snapshot()))
        a.reset()
        a.advance(100)
        self.assertEqual(a.snapshot(), b.snapshot())


if __name__ == '__main__':
    unittest.main()
