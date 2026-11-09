"""Final D checks: headings, fractional resources, mutations, and full replay."""
from dataclasses import asdict
import json
import math
import random
import unittest
from unittest.mock import Mock

from ai_evolution.experiments.r1 import Simulation, SimulationConfig
from ai_evolution.experiments.r1.reproduction import mutate_trait, reproduce
from ai_evolution.web.app import create_app


class NewbornHeadingTests(unittest.TestCase):
    def test_heading_uses_an_independent_seeded_draw_not_parent_heading(self):
        config = SimulationConfig(initial_population=1, initial_food=0,
                                  starting_energy=100, speed_mutation_probability=0,
                                  vision_mutation_probability=0)
        state = Simulation(config, seed=1).snapshot()
        other = Simulation(config, seed=1).snapshot()
        state.organisms[1].heading = 0.1
        other.organisms[1].heading = 5.9
        expected_rng = random.Random(1239)
        # Two mutation tests, then radius and placement angle, then heading.
        for _ in range(4):
            expected_rng.random()
        expected_heading = math.tau * expected_rng.random()
        reproduce(state, config, random.Random(1239))
        reproduce(other, config, random.Random(1239))
        self.assertEqual(state.organisms[2].heading, expected_heading)
        self.assertEqual(other.organisms[2].heading, expected_heading)
        self.assertEqual(state.organisms[2].traits, state.organisms[1].traits)

    def test_equal_headings_are_allowed_when_independent_draws_coincide(self):
        config = SimulationConfig(initial_population=1, initial_food=0, starting_energy=100,
                                  speed_mutation_probability=0, vision_mutation_probability=0)
        state = Simulation(config).snapshot()
        state.organisms[1].heading = math.tau * 0.25
        rng = Mock(random=Mock(side_effect=[0.9, 0.9, 0.36, 0.2, 0.25]))
        reproduce(state, config, rng)
        self.assertEqual(state.organisms[2].heading, state.organisms[1].heading)
        self.assertEqual(rng.random.call_count, 5)


class FractionalFoodTests(unittest.TestCase):
    def test_engine_poisson_counts_over_long_simulated_periods(self):
        for rate in (0.05, 0.1, 0.5, 1.0):
            with self.subTest(rate=rate):
                count = 0
                for seed in range(10):
                    config = SimulationConfig(
                        initial_population=1, initial_food=0, food_spawn_rate=rate,
                        food_cap=2000, dt=10, max_lifespan=2000, founder_age_mode="zero",
                        baseline_cost=0, vision_cost=0, movement_cost=0,
                        search_speed_fraction=0, reproduction_threshold=1e9,
                    )
                    sim = Simulation(config, seed=seed)
                    sim.advance(100)  # 1,000 simulated time units per seed.
                    state = sim.snapshot()
                    self.assertEqual(state.time, 1000)
                    self.assertEqual(state.statistics.spawns_discarded, 0)
                    count += state.statistics.spawned
                expected = rate * 1000 * 10
                self.assertLess(abs(count - expected), 5 * math.sqrt(expected))

    def test_fractional_spawning_replays_and_zero_disables(self):
        for rate in (0, 0.05, 0.1, 0.5, 1.0):
            with self.subTest(rate=rate):
                config = SimulationConfig(initial_population=2, initial_food=10,
                                          food_spawn_rate=rate, dt=1)
                a, b = Simulation(config, seed=38), Simulation(config, seed=38)
                a.advance(20)
                for _ in range(20):
                    b.step()
                self.assertEqual(a.snapshot(), b.snapshot())
                if rate == 0:
                    self.assertEqual(a.snapshot().statistics.spawn_attempts, 0)
                    self.assertIsNone(a.snapshot().next_food_spawn_time)


class ResetResourceTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()
        self.report = self.client.get('/api/state').get_json()

    def action(self, action, **values):
        response = self.client.post('/api/control', json={
            'action': action, 'run_id': self.report['run_id'],
            'expected_step': self.report['state']['step_count'], **values,
        })
        if response.status_code == 200:
            self.report = response.get_json()
        return response

    def test_defaults_remain_200_and_8(self):
        self.assertEqual(self.report['parameters']['initial_food'], 200)
        self.assertEqual(self.report['parameters']['food_spawn_rate'], 8)

    def test_initial_food_and_fractional_rates_apply_independently_on_reset(self):
        for initial in (0, 5, 10, 20, 50, 200):
            for rate in (0, 0.05, 0.1, 0.5, 1.0):
                with self.subTest(initial=initial, rate=rate):
                    response = self.action('reset', seed=42, parameters={
                        'initial_food': initial, 'food_spawn_rate': rate,
                    })
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(len(self.report['state']['food']), initial)
                    self.assertEqual(self.report['parameters']['food_spawn_rate'], rate)
                    self.assertEqual(self.report['state']['step_count'], 0)
        self.action('reset', parameters={'initial_food': 10, 'food_spawn_rate': 0.1})
        first = self.report['state']
        self.action('step')
        self.action('reset')
        self.assertEqual(self.report['state'], first)

    def test_invalid_initial_food_is_rejected_atomically(self):
        for initial in (-1, 1.5, 5.0, True, '10', None, 501):
            with self.subTest(initial=initial):
                before = self.report
                self.assertEqual(self.action('reset', parameters={'initial_food': initial}).status_code, 400)
                self.assertEqual(self.client.get('/api/state').get_json(), before)
        self.assertEqual(self.action('reset', parameters={'initial_food': 500}).status_code, 200)

    def test_initial_food_limit_uses_configured_cap(self):
        client = create_app(SimulationConfig(initial_food=0, food_cap=12)).test_client()
        report = client.get('/api/state').get_json()
        response = client.post('/api/control', json={'action': 'reset', 'run_id': report['run_id'],
                              'expected_step': 0, 'parameters': {'initial_food': 13}})
        self.assertEqual(response.status_code, 400)

    def test_resource_parameters_cannot_change_mid_run(self):
        before = self.report
        self.assertEqual(self.action('step', parameters={'initial_food': 10, 'food_spawn_rate': 0.1}).status_code, 400)
        self.assertEqual(self.client.get('/api/state').get_json(), before)

    def test_initial_food_uses_seeded_random_positions(self):
        self.action('reset', seed=42, parameters={'initial_food': 20, 'food_spawn_rate': 0.1})
        original = self.report['state']
        expected = Simulation(SimulationConfig(initial_food=20, food_spawn_rate=0.1), seed=42).snapshot()
        self.assertEqual(original['food'], json.loads(json.dumps(asdict(expected)))['food'])
        self.assertGreater(len({(food['position']['x'], food['position']['y'])
                               for food in original['food'].values()}), 1)
        self.action('reset', seed=43)
        self.assertNotEqual(self.report['state']['food'], original['food'])


class MutationMatrixTests(unittest.TestCase):
    def test_requested_probabilities_and_full_range_magnitudes(self):
        samples = 5000
        for probability in (0, 0.05, 1.0):
            for magnitude in (0.05, 0.1):
                with self.subTest(probability=probability, magnitude=magnitude):
                    rng = random.Random(819)
                    s_count = v_count = joint = positive = negative = 0
                    for _ in range(samples):
                        speed, s = mutate_trait(4, 0.5, 8, probability, magnitude, rng)
                        vision, v = mutate_trait(15, 1, 30, probability, magnitude, rng)
                        s_count += s
                        v_count += v
                        joint += s and v
                        positive += speed > 4
                        negative += speed < 4
                        self.assertLessEqual(abs(speed - 4), magnitude * 7.5 + 1e-12)
                        self.assertLessEqual(abs(vision - 15), magnitude * 29 + 1e-12)
                        self.assertTrue(0.5 <= speed <= 8 and 1 <= vision <= 30)
                    expected = samples * probability
                    allowance = 5 * math.sqrt(samples * probability * (1 - probability))
                    self.assertLessEqual(abs(s_count - expected), allowance)
                    self.assertLessEqual(abs(v_count - expected), allowance)
                    joint_p = probability * probability
                    self.assertLessEqual(abs(joint - samples * joint_p),
                                         5 * math.sqrt(samples * joint_p * (1 - joint_p)))
                    if probability:
                        self.assertGreater(positive, 0)
                        self.assertGreater(negative, 0)
                    else:
                        self.assertEqual((positive, negative), (0, 0))

    def test_reflection_with_both_requested_magnitudes(self):
        for magnitude in (0.05, 0.1):
            speed_delta, vision_delta = magnitude * 7.5, magnitude * 29
            for parent, lower, upper, delta in ((8, 0.5, 8, speed_delta), (0.5, 0.5, 8, -speed_delta),
                                                 (30, 1, 30, vision_delta), (1, 1, 30, -vision_delta)):
                with self.subTest(parent=parent, magnitude=magnitude):
                    rng = Mock(random=Mock(return_value=0), uniform=Mock(return_value=delta))
                    child, event = mutate_trait(parent, lower, upper, 1, magnitude, rng)
                    self.assertTrue(event)
                    self.assertAlmostEqual(child, parent - delta)


class CompleteReplayTests(unittest.TestCase):
    def test_full_trajectories_match_seeds_batching_storage_and_browser_schedules(self):
        config = SimulationConfig(initial_population=3, initial_food=20, world_width=8,
                                  world_height=6, starting_energy=100, food_spawn_rate=0.5,
                                  max_lifespan=2.3, speed_mutation_probability=1,
                                  vision_mutation_probability=1, speed_mutation_magnitude=0.1,
                                  vision_mutation_magnitude=0.1)
        first, second = Simulation(config, seed=93), Simulation(config, seed=93)
        self.assertEqual(first.snapshot(), second.snapshot())
        second._state.organisms = dict(reversed(list(second._state.organisms.items())))
        second._state.food = dict(reversed(list(second._state.food.items())))
        client = create_app(config, seed=93).test_client()
        report = client.get('/api/state').get_json()
        slow_client = create_app(config, seed=93).test_client()
        slow_report = slow_client.get('/api/state').get_json()
        def advance_api(client, report, count):
            response = client.post('/api/control', json={
                'action': 'start', 'run_id': report['run_id'], 'expected_step': report['state']['step_count']})
            report = response.get_json()
            for _ in range(count):
                if report['is_terminal']:
                    break
                response = client.post('/api/control', json={
                    'action': 'advance', 'steps': 1, 'run_id': report['run_id'],
                    'expected_step': report['state']['step_count']})
                self.assertEqual(response.status_code, 200)
                report = response.get_json()
            return report
        trajectory = []
        for count in (1, 3, 7, 9, 10):
            for _ in range(count):
                first.step()
            second.advance(count)
            state = first.snapshot()
            self.assertEqual(state, second.snapshot())
            # One client sends single steps, the other bounded fast-forward batches.
            slow_report = advance_api(slow_client, slow_report, count)
            response = client.post('/api/control', json={
                'action': 'start', 'run_id': report['run_id'], 'expected_step': report['state']['step_count']})
            report = response.get_json()
            response = client.post('/api/control', json={
                'action': 'advance', 'steps': count, 'run_id': report['run_id'],
                'expected_step': report['state']['step_count']})
            self.assertEqual(response.status_code, 200)
            report = response.get_json()
            expected = json.loads(json.dumps(asdict(state)))
            self.assertEqual(report['state'], expected)
            self.assertEqual(slow_report['state'], expected)
            trajectory.append(state.summary()['population'])
        stats = first.snapshot().statistics
        self.assertGreater(stats.births, 0)
        self.assertGreater(stats.age_deaths, 0)
        self.assertGreater(stats.food_consumed, 0)
        self.assertGreater(stats.spawned, 0)
        self.assertGreater(stats.speed_mutations, 0)
        self.assertGreater(stats.vision_mutations, 0)
        self.assertGreater(len(set(trajectory)), 1)
        # Reset replay includes the complete final state, archives, and counters.
        first.reset()
        first.advance(30)
        self.assertEqual(first.snapshot(), second.snapshot())


if __name__ == '__main__':
    unittest.main()
