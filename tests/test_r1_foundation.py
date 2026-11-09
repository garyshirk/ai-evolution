from dataclasses import FrozenInstanceError, fields
import math
import random
import unittest

from ai_evolution.experiments.r1 import Simulation, SimulationConfig
from ai_evolution.experiments.r1.models import Position, Traits, WorldState


class ConfigurationTests(unittest.TestCase):
    def test_approved_defaults(self):
        config = SimulationConfig()
        self.assertEqual((config.world_width, config.world_height), (100, 100))
        self.assertEqual((config.initial_population, config.initial_food), (50, 200))
        self.assertEqual((config.dt, config.food_cap, config.food_spawn_rate), (0.1, 500, 8))
        self.assertEqual((config.reproduction_threshold, config.offspring_energy,
                          config.reproduction_overhead), (60, 25, 5))
        self.assertEqual(config.max_lifespan, 200)
        self.assertEqual(config.speed_mutation_probability, 0.05)
        self.assertEqual(config.vision_mutation_probability, 0.05)

    def test_configuration_is_immutable(self):
        with self.assertRaises(FrozenInstanceError):
            SimulationConfig().dt = 2

    def test_all_fields_reject_wrong_types(self):
        for field in fields(SimulationConfig):
            for value in (True, "1", None):
                with self.subTest(field=field.name, value=value):
                    with self.assertRaises(ValueError):
                        SimulationConfig(**{field.name: value})

    def test_numeric_fields_reject_nonfinite_values(self):
        for field in fields(SimulationConfig):
            for value in (math.nan, math.inf, -math.inf):
                with self.subTest(field=field.name, value=value):
                    with self.assertRaises(ValueError):
                        SimulationConfig(**{field.name: value})

    def test_invalid_ranges_and_values(self):
        cases = [
            {"initial_population": -1}, {"initial_population": 1.5},
            {"initial_food": 2.0}, {"food_cap": -1},
            {"initial_food": 501}, {"dt": 0}, {"world_width": -1},
            {"world_height": 0}, {"food_energy": 0}, {"starting_energy": 0},
            {"speed_reference": 0}, {"vision_reference": 0},
            {"max_lifespan": 0}, {"search_turn_interval": 0},
            {"baseline_cost": -0.1}, {"movement_cost": -1}, {"vision_cost": -1},
            {"food_spawn_rate": -1}, {"search_speed_fraction": 1.01},
            {"speed_mutation_probability": -0.1},
            {"vision_mutation_probability": 1.1},
            {"speed_mutation_magnitude": -1},
            {"vision_mutation_magnitude": -1},
            {"speed_min": 8}, {"vision_max": 1},
            {"founder_speed_min": 0.1}, {"founder_speed_max": 9},
            {"founder_speed_min": 5}, {"founder_vision_min": 0.5},
            {"founder_vision_max": 31}, {"founder_vision_min": 20},
        ]
        for values in cases:
            with self.subTest(values=values), self.assertRaises(ValueError):
                SimulationConfig(**values)

    def test_zero_optional_values_and_fixed_founder_traits(self):
        config = SimulationConfig(
            initial_population=0, initial_food=0, food_cap=0, food_spawn_rate=0,
            baseline_cost=0, movement_cost=0, vision_cost=0,
            search_speed_fraction=0, speed_mutation_probability=0,
            vision_mutation_probability=1, speed_mutation_magnitude=0,
            reproduction_overhead=0, offspring_placement_radius=0,
            founder_speed_min=2, founder_speed_max=2,
            founder_vision_min=5, founder_vision_max=5,
        )
        self.assertEqual(config.food_cap, 0)


class InitializationTests(unittest.TestCase):
    def test_counts_ids_and_founder_state(self):
        simulation = Simulation(seed=42)
        state = simulation.snapshot()
        self.assertEqual(len(state.organisms), 50)
        self.assertEqual(len(state.food), 200)
        self.assertEqual(list(state.organisms), list(range(1, 51)))
        self.assertEqual(list(state.food), list(range(1, 201)))
        self.assertEqual((state.next_organism_id, state.next_food_id), (51, 201))
        self.assertEqual((state.step_count, state.time), (0, 0))
        for identifier, org in state.organisms.items():
            self.assertEqual(org.id, identifier)
            self.assertEqual(org.founder_lineage_id, identifier)
            self.assertIsNone(org.parent_id)
            self.assertEqual((org.generation, org.offspring_count), (0, 0))
            self.assertTrue(0 <= org.age_at(0) < simulation.config.max_lifespan)
            self.assertEqual(org.energy, 30)
            self.assertEqual(org.movement_mode, "idle")
            self.assertEqual(org.actual_speed, 0)
            self.assertTrue(0 <= org.heading < math.tau)
        for identifier, food in state.food.items():
            self.assertEqual(food.id, identifier)
            self.assertEqual(food.energy, 10)

    def test_custom_world_and_trait_ranges(self):
        config = SimulationConfig(
            world_width=7, world_height=13, initial_population=100,
            initial_food=50, starting_energy=12, food_energy=3,
            founder_speed_min=2, founder_speed_max=3,
            founder_vision_min=6, founder_vision_max=7,
        )
        state = Simulation(config, seed=123).snapshot()
        for entity in [*state.organisms.values(), *state.food.values()]:
            self.assertTrue(0 <= entity.position.x < 7)
            self.assertTrue(0 <= entity.position.y < 13)
        for org in state.organisms.values():
            self.assertTrue(2 <= org.traits.speed <= 3)
            self.assertTrue(6 <= org.traits.vision_radius <= 7)
            self.assertEqual(org.energy, 12)
        self.assertGreater(len({org.traits.speed for org in state.organisms.values()}), 90)
        self.assertGreater(len({org.traits.vision_radius for org in state.organisms.values()}), 90)
        self.assertTrue(all(food.energy == 3 for food in state.food.values()))

    def test_fixed_trait_sampling_ranges(self):
        config = SimulationConfig(founder_speed_min=2, founder_speed_max=2,
                                  founder_vision_min=6, founder_vision_max=6)
        self.assertTrue(all(org.traits == Traits(2, 6)
                            for org in Simulation(config).snapshot().organisms.values()))

    def test_seed_validation(self):
        for seed in (True, 1.5, "42", None):
            with self.subTest(seed=seed), self.assertRaises(ValueError):
                Simulation(seed=seed)
        self.assertEqual(Simulation(seed=-42).seed, -42)

    def test_config_type_validation(self):
        with self.assertRaises(TypeError):
            Simulation({})

    def test_immutable_traits(self):
        with self.assertRaises(FrozenInstanceError):
            Traits(2, 6).speed = 5


class StateAndClockTests(unittest.TestCase):
    def test_clock_uses_tick_index_not_accumulated_time(self):
        simulation = Simulation(SimulationConfig(
            dt=0.03, founder_age_mode="zero", initial_population=1, initial_food=0, food_spawn_rate=0,
            baseline_cost=0, vision_cost=0, movement_cost=0,
            search_speed_fraction=0, max_lifespan=1e9,
        ))
        self.assertTrue(simulation.step())
        self.assertEqual(simulation.advance(9999), 9999)
        state = simulation.snapshot()
        self.assertEqual(state.step_count, 10000)
        self.assertEqual(state.time, 10000 * 0.03)
        self.assertEqual(state.organisms[1].age_at(state.time), state.time)

    def test_founders_without_resources_do_not_reproduce_or_mutate(self):
        simulation = Simulation(SimulationConfig(
            initial_population=5, initial_food=0, food_spawn_rate=0, max_lifespan=0.3,
        ))
        before = simulation.snapshot()
        simulation.advance(10)
        after = simulation.snapshot()
        # These founders cannot reach the reproduction threshold without food.
        final_organisms = {**after.organisms,
                           **{identifier: death.organism for identifier, death in after.deaths.items()}}
        for identifier, org in final_organisms.items():
            original = before.organisms[identifier]
            self.assertEqual(org.traits, original.traits)
            self.assertEqual(org.parent_id, original.parent_id)
            self.assertEqual(org.generation, original.generation)
            self.assertEqual(org.offspring_count, original.offspring_count)
        self.assertEqual(set(final_organisms), set(before.organisms))
        self.assertEqual(after.food, before.food)
        self.assertEqual(after.next_organism_id, before.next_organism_id)
        self.assertEqual(after.next_food_id, before.next_food_id)

    def test_snapshots_are_detached_and_reads_have_no_effect(self):
        simulation = Simulation(seed=91)
        expected = simulation.snapshot()
        changed = simulation.snapshot()
        changed.organisms[1].energy = -100
        changed.organisms[1].position = Position(0, 0)
        changed.organisms.clear()
        changed.food.clear()
        changed.step_count = 99
        changed.next_organism_id = 900
        self.assertEqual(simulation.snapshot(), expected)

    def test_reset_replays_initialization_and_clock(self):
        simulation = Simulation(seed=19)
        initial = simulation.snapshot()
        simulation.advance(17)
        simulation.reset()
        self.assertEqual(simulation.snapshot(), initial)
        simulation.advance(17)
        other = Simulation(seed=19)
        other.advance(17)
        self.assertEqual(simulation.snapshot(), other.snapshot())

    def test_batching_and_same_seed_trajectories_match(self):
        first, second = Simulation(seed=8), Simulation(seed=8)
        self.assertEqual(first.snapshot(), second.snapshot())
        for batch in (0, 1, 5, 100):
            first.advance(batch)
            for _ in range(batch):
                second.step()
            self.assertEqual(first.snapshot(), second.snapshot())

    def test_different_seeds_differ(self):
        self.assertNotEqual(Simulation(seed=1).snapshot(), Simulation(seed=2).snapshot())

    def test_rng_is_independent_of_global_random_and_other_runs(self):
        global_state = random.getstate()
        try:
            first = Simulation(seed=3).snapshot()
            self.assertEqual(random.getstate(), global_state)
            random.seed(900)
            random.random()
            Simulation(seed=7).advance(50)
            self.assertEqual(Simulation(seed=3).snapshot(), first)
        finally:
            random.setstate(global_state)

    def test_zero_steps_is_noop_and_invalid_steps_are_atomic(self):
        simulation = Simulation()
        initial = simulation.snapshot()
        self.assertEqual(simulation.advance(0), 0)
        for value in (-1, True, 1.5, "2", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                simulation.advance(value)
            self.assertEqual(simulation.snapshot(), initial)

    def test_empty_population_is_terminal_without_discarding_food(self):
        simulation = Simulation(SimulationConfig(initial_population=0))
        initial = simulation.snapshot()
        self.assertTrue(initial.is_terminal)
        self.assertFalse(simulation.step())
        self.assertEqual(simulation.advance(10), 0)
        self.assertEqual(simulation.snapshot(), initial)
        self.assertEqual(len(initial.food), 200)

    def test_foodless_world_can_advance_clock(self):
        simulation = Simulation(SimulationConfig(initial_food=0, food_cap=0))
        self.assertEqual(simulation.advance(10), 10)
        self.assertEqual(simulation.snapshot().food, {})

    def test_world_containers_are_not_shared(self):
        first, second = WorldState(0.1), WorldState(0.1)
        first.organisms[1] = Simulation().snapshot().organisms[1]
        self.assertEqual(second.organisms, {})


if __name__ == "__main__":
    unittest.main()
