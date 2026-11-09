"""Birth and mutation rules in small worlds, independent of default calibration."""

from dataclasses import asdict
import json
import math
import random
import unittest
from unittest.mock import Mock

from ai_evolution.experiments.r1 import Simulation, SimulationConfig
from ai_evolution.experiments.r1.models import Food, Position
from ai_evolution.experiments.r1.reproduction import mutate_trait, reflect_value
from ai_evolution.web.app import create_app


def laboratory(**changes):
    values = dict(founder_age_mode="zero", initial_population=1, initial_food=0, food_spawn_rate=0,
                  baseline_cost=0, vision_cost=0, movement_cost=0,
                  search_speed_fraction=0, starting_energy=100,
                  speed_mutation_probability=0, vision_mutation_probability=0)
    values.update(changes)
    return Simulation(SimulationConfig(**values), seed=42)


class ReproductionTests(unittest.TestCase):
    def test_threshold_is_strict(self):
        for energy, births in ((59.9, 0), (60, 0), (math.nextafter(60, math.inf), 1)):
            with self.subTest(energy=energy):
                sim = laboratory(starting_energy=energy)
                sim.step()
                self.assertEqual(sim.snapshot().statistics.births, births)

    def test_allocation_and_overhead_leave_parent_positive(self):
        for energy, births in ((29, 0), (30, 0), (math.nextafter(30, math.inf), 1)):
            with self.subTest(energy=energy):
                sim = laboratory(starting_energy=energy, reproduction_threshold=1)
                sim.step()
                self.assertEqual(sim.snapshot().statistics.births, births)
                self.assertGreater(sim.snapshot().organisms[1].energy, 0)

    def test_parent_child_energy_and_population_ledger(self):
        sim = laboratory(starting_energy=100)
        sim.step()
        state = sim.snapshot()
        self.assertEqual(state.organisms[1].energy, 70)
        self.assertEqual(state.organisms[2].energy, 25)
        self.assertEqual(state.statistics.offspring_energy_transferred, 25)
        self.assertEqual(state.statistics.reproduction_overhead_spent, 5)
        self.assertEqual(state.summary()["living_energy"], 95)
        self.assertEqual(state.summary()["energy_ledger_residual"], 0)

    def test_one_child_per_parent_per_tick_even_with_high_reserves(self):
        sim = laboratory(starting_energy=1000)
        sim.step()
        self.assertEqual(len(sim.snapshot().organisms), 2)
        self.assertEqual(sim.snapshot().organisms[1].offspring_count, 1)
        sim.step()
        self.assertEqual(len(sim.snapshot().organisms), 3)
        self.assertEqual(sim.snapshot().organisms[1].offspring_count, 2)

    def test_newborn_cannot_reproduce_in_birth_tick(self):
        sim = laboratory(starting_energy=500, offspring_energy=100)
        sim.step()
        state = sim.snapshot()
        self.assertEqual(len(state.organisms), 2)
        self.assertEqual(state.organisms[2].offspring_count, 0)
        self.assertEqual(state.organisms[2].energy, 100)
        self.assertEqual(state.organisms[2].age_at(state.time), 0)
        self.assertEqual(state.organisms[2].actual_speed, 0)
        self.assertEqual(state.organisms[2].movement_mode, "idle")
        # Even a large newborn reserve cannot pay its own allocation plus
        # overhead; a meal on the next tick makes this child eligible.
        sim._state.organisms[2].position = Position(10, 10)
        sim._state.food[1] = Food(1, Position(10, 10), 10)
        sim._state.next_food_id = 2
        sim.step()
        self.assertEqual(sim.snapshot().statistics.births, 3)
        self.assertEqual(sim.snapshot().organisms[2].offspring_count, 1)

    def test_newborn_cannot_eat_move_or_pay_costs_until_next_tick(self):
        sim = laboratory(starting_energy=100, baseline_cost=1, search_speed_fraction=0.5,
                         offspring_placement_radius=0, dt=0.1)
        sim.step()
        state = sim.snapshot()
        child = state.organisms[2]
        parent = state.organisms[1]
        self.assertEqual(child.position, parent.position)
        self.assertEqual(child.energy, 25)
        self.assertEqual(child.actual_speed, 0)
        self.assertEqual(state.statistics.baseline_spent, 0.1)
        sim.step()
        next_child = sim.snapshot().organisms[2]
        self.assertNotEqual(next_child.position, child.position)
        self.assertAlmostEqual(next_child.energy, 24.9)
        self.assertAlmostEqual(next_child.age_at(sim.snapshot().time), 0.1)

    def test_inheritance_lineage_generation_birth_time_and_ids(self):
        sim = laboratory(starting_energy=500, offspring_energy=100)
        founder = sim.snapshot().organisms[1]
        sim.step()
        child = sim.snapshot().organisms[2]
        self.assertEqual(child.traits, founder.traits)
        self.assertEqual((child.parent_id, child.generation, child.founder_lineage_id), (1, 1, 1))
        self.assertEqual(child.birth_time, 0.1)
        sim._state.organisms[2].position = Position(10, 10)
        sim._state.food[1] = Food(1, Position(10, 10), 10)
        sim._state.next_food_id = 2
        sim.step()
        state = sim.snapshot()
        grandchild = next(org for org in state.organisms.values() if org.parent_id == 2)
        self.assertEqual(grandchild.generation, 2)
        self.assertEqual(grandchild.founder_lineage_id, 1)
        self.assertEqual(grandchild.traits, child.traits)
        self.assertEqual(grandchild.birth_time, 0.2)
        self.assertEqual(len({org.id for org in state.organisms.values()}), len(state.organisms))
        self.assertEqual(state.next_organism_id, 5)
        self.assertEqual(state.statistics.highest_generation, 2)

    def test_newborn_does_not_consume_leftover_food_in_birth_tick(self):
        sim = laboratory(offspring_placement_radius=0)
        position = sim.snapshot().organisms[1].position
        sim._state.food = {1: Food(1, position, 10), 2: Food(2, position, 10)}
        sim._state.next_food_id = 3
        sim.step()
        state = sim.snapshot()
        self.assertEqual(state.statistics.food_consumed, 1)
        self.assertEqual(len(state.food), 1)
        self.assertEqual(state.organisms[2].energy, 25)
        sim.step()
        self.assertEqual(sim.snapshot().statistics.food_consumed, 2)

    def test_uniform_disk_placement_and_reflected_world_edges(self):
        sim = laboratory(starting_energy=100, offspring_placement_radius=1)
        for seed in range(30):
            sim.reset()
            # Place a parent at an edge; no collisions or placement rejection.
            sim._state.organisms[1].position = Position(0, 0)
            sim._rng = random.Random(seed)
            sim.step()
            child = sim.snapshot().organisms[2]
            self.assertTrue(0 <= child.position.x <= 1)
            self.assertTrue(0 <= child.position.y <= 1)
            self.assertLessEqual(math.hypot(child.position.x, child.position.y), 1)
            self.assertTrue(0 <= child.heading < math.tau)

    def test_parent_at_age_limit_does_not_reproduce_but_child_lives_on(self):
        sim = laboratory(starting_energy=100, max_lifespan=0.15)
        sim.step()
        self.assertEqual(sim.snapshot().statistics.births, 1)
        sim.step()
        state = sim.snapshot()
        self.assertIn(1, state.deaths)
        self.assertIn(2, state.organisms)
        self.assertEqual(state.statistics.births, 1)
        self.assertEqual(state.deaths[1].organism.offspring_count, 1)
        sim.step()
        self.assertTrue(sim.snapshot().is_terminal)
        self.assertEqual(sim.snapshot().statistics.age_deaths, 2)
        self.assertAlmostEqual(sim.snapshot().summary()["energy_ledger_residual"], 0)

    def test_starvation_preempts_reproduction(self):
        sim = laboratory(starting_energy=100, baseline_cost=1000)
        sim.step()
        self.assertEqual(sim.snapshot().statistics.births, 0)
        self.assertTrue(sim.snapshot().is_terminal)

    def test_threshold_test_occurs_after_costs_and_meal(self):
        sim = laboratory(starting_energy=60.05, baseline_cost=1)
        sim.step()
        self.assertEqual(sim.snapshot().statistics.births, 0)
        sim = laboratory(starting_energy=55, baseline_cost=1)
        position = sim.snapshot().organisms[1].position
        sim._state.food[1] = Food(1, position, 10)
        sim._state.next_food_id = 2
        sim.step()
        self.assertEqual(sim.snapshot().statistics.births, 1)
        self.assertAlmostEqual(sim.snapshot().organisms[1].energy, 34.9)

    def test_reset_and_summary_reads_do_not_change_seeded_births(self):
        sim = laboratory(starting_energy=300, speed_mutation_probability=0.5,
                         vision_mutation_probability=0.5)
        sim.advance(10)
        expected = sim.snapshot()
        sim.reset()
        for _ in range(10):
            sim.snapshot().summary()
            sim.step()
        self.assertEqual(sim.snapshot(), expected)

    def test_multiple_founders_keep_lineages_and_storage_order_does_not_matter(self):
        a, b = laboratory(initial_population=3), laboratory(initial_population=3)
        b._state.organisms = dict(reversed(list(b._state.organisms.items())))
        a.advance(3)
        for _ in range(3):
            b.step()
        self.assertEqual(a.snapshot(), b.snapshot())
        for org in a.snapshot().organisms.values():
            if org.parent_id is not None:
                self.assertEqual(org.founder_lineage_id, a.snapshot().organisms[org.parent_id].founder_lineage_id)

    def test_empty_population_summary_is_sensible(self):
        sim = laboratory(initial_population=0)
        self.assertIsNone(sim.snapshot().summary()["mean_speed"])
        self.assertIsNone(sim.snapshot().summary()["mean_vision"])
        self.assertEqual(sim.snapshot().summary()["births"], 0)


class MutationTests(unittest.TestCase):
    def test_probability_zero_inherits_exactly(self):
        value = math.nextafter(2.0, math.inf)
        inherited, mutated = mutate_trait(value, 0.5, 8, 0, 0.05, random.Random(1))
        self.assertEqual(inherited, value)
        self.assertFalse(mutated)

    def test_uniform_perturbations_can_be_positive_or_negative(self):
        for random_delta, expected in ((0.2, 2.2), (-0.2, 1.8)):
            rng = Mock(random=Mock(return_value=0), uniform=Mock(return_value=random_delta))
            value, mutated = mutate_trait(2, 0.5, 8, 1, 0.05, rng)
            self.assertEqual(value, expected)
            self.assertTrue(mutated)
            rng.uniform.assert_called_once_with(-0.375, 0.375)

    def test_trait_reflection_handles_both_bounds_and_large_overshoots(self):
        for value, expected in ((8.2, 7.8), (0.3, 0.7), (23.2, 7.8), (-14.7, 0.7), (8, 8), (0.5, 0.5)):
            with self.subTest(value=value):
                self.assertAlmostEqual(reflect_value(value, 0.5, 8), expected)
        rng = Mock(random=Mock(return_value=0), uniform=Mock(return_value=0.3))
        self.assertAlmostEqual(mutate_trait(8, 0.5, 8, 1, 0.05, rng)[0], 7.7)

    def test_speed_and_vision_mutation_are_independently_configurable(self):
        for speed_probability, vision_probability in ((1, 0), (0, 1)):
            sim = laboratory(speed_mutation_probability=speed_probability,
                             vision_mutation_probability=vision_probability)
            parent = sim.snapshot().organisms[1]
            sim.step()
            child = sim.snapshot().organisms[2]
            self.assertEqual(child.traits.speed == parent.traits.speed, not speed_probability)
            self.assertEqual(child.traits.vision_radius == parent.traits.vision_radius, not vision_probability)

    def test_frequencies_joint_independence_signs_and_bounds(self):
        rng = random.Random(123)
        samples = 20000
        speed_events = vision_events = both = positive = negative = 0
        for _ in range(samples):
            speed, s = mutate_trait(4, 0.5, 8, 0.05, 0.05, rng)
            vision, v = mutate_trait(15, 1, 30, 0.05, 0.05, rng)
            speed_events += s
            vision_events += v
            both += s and v
            positive += speed > 4
            negative += speed < 4
            self.assertTrue(0.5 <= speed <= 8)
            self.assertTrue(1 <= vision <= 30)
            self.assertLessEqual(abs(speed - 4), 0.375)
            self.assertLessEqual(abs(vision - 15), 1.45)
        self.assertLess(abs(speed_events - 1000), 5 * math.sqrt(950))
        self.assertLess(abs(vision_events - 1000), 5 * math.sqrt(950))
        self.assertLess(abs(both - 50), 5 * math.sqrt(50))
        self.assertLess(abs(positive - negative), 5 * math.sqrt(speed_events))

    def test_zero_magnitude_preserves_trait_even_if_event_fires(self):
        self.assertEqual(mutate_trait(2, 0.5, 8, 1, 0, random.Random(3)), (2, True))

    def test_overflowing_mutation_ranges_are_rejected(self):
        for name in ('speed_mutation_magnitude', 'vision_mutation_magnitude'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                SimulationConfig(**{name: 1e308})


class BrowserEvolutionTests(unittest.TestCase):
    def test_batched_browser_and_headless_births_agree(self):
        config = laboratory(initial_population=2, starting_energy=150,
                            speed_mutation_probability=1, vision_mutation_probability=1).config
        expected = Simulation(config, seed=42)
        expected.advance(10)
        client = create_app(config, seed=42).test_client()
        report = client.get('/api/state').get_json()
        for action, extra in (("start", {}), ("advance", {"steps": 4}), ("advance", {"steps": 6}), ("pause", {})):
            response = client.post('/api/control', json={"action": action, "run_id": report['run_id'],
                                  "expected_step": report['state']['step_count'], **extra})
            self.assertEqual(response.status_code, 200)
            report = response.get_json()
        self.assertEqual(report['state'], json.loads(json.dumps(asdict(expected.snapshot()))))
        self.assertEqual(report['summary'], expected.snapshot().summary())
        self.assertGreater(report['summary']['births'], 0)

    def test_advanced_mutation_settings_validate_and_require_reset(self):
        client = create_app().test_client()
        report = client.get('/api/state').get_json()
        def request(action, parameters):
            return client.post('/api/control', json={"action": action, "run_id": report['run_id'],
                               "expected_step": 0, "parameters": parameters})
        self.assertEqual(request('step', {'speed_mutation_probability': 0}).status_code, 400)
        self.assertEqual(request('reset', {'vision_mutation_probability': 1.1}).status_code, 400)
        self.assertEqual(request('reset', {'speed_mutation_magnitude': -1}).status_code, 400)
        response = request('reset', {'speed_mutation_probability': 0,
                                    'vision_mutation_probability': 1,
                                    'speed_mutation_magnitude': 0.1,
                                    'vision_mutation_magnitude': 0.2})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['parameters']['vision_mutation_probability'], 1)


if __name__ == '__main__':
    unittest.main()
