import math
import random
import unittest
from unittest.mock import Mock

from ai_evolution.experiments.r1 import Simulation, SimulationConfig
from ai_evolution.experiments.r1.models import Organism, Position, Traits
from ai_evolution.experiments.r1.movement import reflect_axis, search


class MovementTests(unittest.TestCase):
    def organism(self, heading=0, speed=4, position=Position(50, 50)):
        return Organism(1, position, Traits(speed, 10), 30, heading, 1)

    def test_persistent_heading_and_half_maximum_speed(self):
        for maximum in (0.5, 2, 8):
            org = self.organism(speed=maximum)
            search(org, SimulationConfig(), Mock(random=Mock(return_value=0.99)))
            self.assertAlmostEqual(org.position.x, 50 + maximum * 0.5 * 0.1)
            self.assertEqual(org.position.y, 50)
            self.assertEqual(org.actual_speed, maximum * 0.5)
            self.assertEqual(org.movement_mode, "search")
            self.assertEqual(org.energy, 30)

    def test_turn_uses_seeded_draw_and_probability(self):
        org = self.organism()
        rng = Mock(random=Mock(side_effect=[0, 0.25]))
        search(org, SimulationConfig(), rng)
        self.assertAlmostEqual(org.heading, math.pi / 2)
        self.assertAlmostEqual(org.position.y, 50.2)
        self.assertEqual(rng.random.call_count, 2)

    def test_turn_frequency_matches_model(self):
        config = SimulationConfig()
        rng = random.Random(12)
        org = self.organism()
        changes = 0
        for _ in range(10000):
            org.position = Position(50, 50)
            old = org.heading
            search(org, config, rng)
            # Heading normalization may alter its last bit without a turn.
            changes += abs(math.remainder(org.heading - old, math.tau)) > 1e-10
        expected = 10000 * (1 - math.exp(-config.dt / config.search_turn_interval))
        self.assertLess(abs(changes - expected), 5 * math.sqrt(expected))

    def test_reflection_handles_both_sides_and_multiple_hits(self):
        cases = [(9, 4, 1, 10, 7, -4), (1, -4, 1, 10, 3, 4),
                 (1, 34, 1, 10, 5, -34), (1, -34, 1, 10, 7, -34),
                 (5, 5, 1, 10, 10, -5), (5, -5, 1, 10, 0, 5),
                 (0, -2, 1, 10, 2, 2), (10, 2, 1, 10, 8, -2),
                 (3, 0, 100, 10, 3, 0)]
        for pos, vel, duration, extent, end, outgoing in cases:
            with self.subTest(pos=pos, vel=vel):
                self.assertEqual(reflect_axis(pos, vel, duration, extent), (end, outgoing))

    def test_corner_reflects_both_axes(self):
        org = self.organism(heading=math.pi / 4, position=Position(99.95, 99.95))
        search(org, SimulationConfig(), Mock(random=Mock(return_value=0.99)))
        self.assertLess(org.position.x, 100)
        self.assertLess(org.position.y, 100)
        self.assertAlmostEqual(org.heading, 5 * math.pi / 4)

    def test_zero_search_speed_does_not_move(self):
        org = self.organism()
        search(org, SimulationConfig(search_speed_fraction=0), random.Random(2))
        self.assertEqual(org.position, Position(50, 50))
        self.assertEqual(org.actual_speed, 0)

    def test_fixed_time_controls_distance(self):
        org = self.organism(speed=4)
        search(org, SimulationConfig(dt=0.5), Mock(random=Mock(return_value=0.99)))
        self.assertEqual(org.position, Position(51, 50))

    def test_same_seed_reset_and_batching_match(self):
        first, second = Simulation(seed=42), Simulation(seed=42)
        first.advance(100)
        for _ in range(100):
            second.step()
        self.assertEqual(first.snapshot(), second.snapshot())
        first.reset()
        first.advance(100)
        self.assertEqual(first.snapshot(), second.snapshot())

    def test_storage_order_and_inspection_do_not_affect_rng(self):
        first, second = Simulation(seed=73), Simulation(seed=73)
        second._state.organisms = dict(reversed(list(second._state.organisms.items())))
        for _ in range(30):
            first.snapshot()
            first.step()
        second.advance(30)
        self.assertEqual(first.snapshot(), second.snapshot())

    def test_overlapping_organisms_do_not_interact(self):
        simulation = Simulation(SimulationConfig(initial_population=2), seed=2)
        for org in simulation._state.organisms.values():
            org.position = Position(50, 50)
            org.heading = 0
            org.traits = Traits(4, 10)
        simulation._rng = Mock(random=Mock(return_value=0.99))
        simulation.step()
        organisms = list(simulation.snapshot().organisms.values())
        self.assertEqual(organisms[0].position, organisms[1].position)
        self.assertEqual(organisms[0].position, Position(50.2, 50))

    def test_long_run_stays_in_world_without_changing_food_or_energy(self):
        simulation = Simulation(SimulationConfig(world_width=2, world_height=3), seed=8)
        original = simulation.snapshot()
        simulation.advance(1000)
        state = simulation.snapshot()
        for org in state.organisms.values():
            self.assertTrue(0 <= org.position.x <= 2)
            self.assertTrue(0 <= org.position.y <= 3)
            self.assertEqual(org.energy, 30)
        self.assertEqual(state.food, original.food)


if __name__ == "__main__":
    unittest.main()
