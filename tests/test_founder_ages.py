"""Independent demographic initialization, legacy trajectories and saved-run replay."""
from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import json
import math
import platform
import random
import subprocess
import sys
import unittest

from ai_evolution.experiments.r1 import Simulation, SimulationConfig
from ai_evolution.experiments.r1.batch import BatchConfig, BatchRunner
from ai_evolution.experiments.r1.exports import experiment_report
from ai_evolution.experiments.r1.library import ExperimentLibrary, replay_issue
from ai_evolution.web.app import create_app


def quiet(**changes):
    options = dict(initial_population=1, initial_food=0, food_spawn_rate=0, baseline_cost=0,
                   movement_cost=0, vision_cost=0, search_speed_fraction=0)
    options.update(changes)
    return SimulationConfig(**options)


def digest(state):
    return hashlib.sha256(json.dumps(asdict(state), sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def finished_batch(mode='zero'):
    runner = BatchRunner()
    runner.start(BatchConfig(runs=2, duration=.3, starting_seed=42, simulation=quiet(founder_age_mode=mode)))
    runner.wait(3)
    assert runner.status()['status'] == 'completed'
    return runner.export(runner.status()['batch_id'])


def old_batch(version='0.7.0'):
    data = finished_batch('zero')
    data['engine_version'] = version
    data['configuration']['simulation'].pop('founder_age_mode')
    for run in data['results']:
        run['engine_version'] = version
        run['configuration'].pop('founder_age_mode')
    return data


class FounderInitializationTests(unittest.TestCase):
    def test_random_ages_default_bounds_and_uniform_spread(self):
        config = quiet(initial_population=2000)
        self.assertEqual(config.founder_age_mode, 'uniform')
        state = Simulation(config, seed=42).snapshot()
        ages = [org.age_at(0) for org in state.organisms.values()]
        self.assertTrue(all(0 <= age < config.max_lifespan for age in ages))
        self.assertGreater(len(set(ages)), 1900)
        self.assertAlmostEqual(sum(ages) / len(ages) / config.max_lifespan, .5, delta=.03)
        bins = [sum(i/10 <= age/config.max_lifespan < (i+1)/10 for age in ages) for i in range(10)]
        self.assertTrue(all(140 <= count <= 260 for count in bins), bins)
        self.assertEqual(state.time, 0)
        for org in state.organisms.values():
            self.assertIsNone(org.parent_id)
            self.assertEqual(org.generation, 0)
            self.assertEqual(org.energy, config.starting_energy)
        self.assertEqual(state.statistics.births, 0)

    def test_independent_deterministic_age_stream_preserves_other_initial_conditions(self):
        config = SimulationConfig()
        global_rng = random.getstate()
        uniform = Simulation(config, seed=42)
        zero = Simulation(replace(config, founder_age_mode='zero'), seed=42)
        a, b = uniform.snapshot(), zero.snapshot()
        self.assertEqual(uniform._rng.getstate(), zero._rng.getstate())
        self.assertEqual(random.getstate(), global_rng)
        for identifier in a.organisms:
            org = a.organisms[identifier]
            self.assertEqual(replace(org, birth_time=0), b.organisms[identifier])
        self.assertEqual(a.food, b.food)
        self.assertEqual(a.next_food_spawn_time, b.next_food_spawn_time)
        self.assertEqual(a.statistics, b.statistics)
        expected = random.Random('ai-evolution:r1:founder-ages:v1:42')
        self.assertEqual(a.organisms[1].age_at(0), expected.random() * config.max_lifespan)

    def test_age_seed_replay_reset_batching_and_different_seeds(self):
        a, b = Simulation(seed=3), Simulation(seed=3)
        initial = a.snapshot()
        self.assertEqual(initial, b.snapshot())
        self.assertNotEqual(initial.organisms[1].birth_time, Simulation(seed=4).snapshot().organisms[1].birth_time)
        a.advance(30)
        for _ in range(30): b.step()
        self.assertEqual(a.snapshot(), b.snapshot())
        self.assertEqual(a._rng.getstate(), b._rng.getstate())
        a.reset()
        self.assertEqual(a.snapshot(), initial)

    @unittest.skipUnless(platform.python_version() == '3.13.5' and sys.platform == 'darwin',
                         'Legacy reference hashes were captured on macOS / Python 3.13.5')
    def test_legacy_mode_matches_prechange_state_and_rng_goldens(self):
        # Captured from approved cbd0fd6 before implementation, Python 3.13.5.
        simulation = Simulation(SimulationConfig(founder_age_mode='zero'), seed=42)
        self.assertEqual(digest(simulation.snapshot()), '5179d347a6bce114975a3219ddc057b1c38f84146cd22c8d97fab0b0b328ee1b')
        self.assertTrue(all(org.birth_time == 0 for org in simulation.snapshot().organisms.values()))
        simulation.advance(300)
        self.assertEqual(digest(simulation.snapshot()), 'd2101e53170c9aef091b47a11e6a08a6235bafe7e1eaba267796794172b0efa9')
        self.assertEqual(hashlib.sha256(repr(simulation._rng.getstate()).encode()).hexdigest(),
                         '0491d43f9cdb4226b59b5395e1246399e708ceb1c5baf83c9b5ccacd03aa4230')

    def test_existing_lifespan_mechanism_uses_each_founders_remaining_life(self):
        config = quiet(initial_population=30, max_lifespan=2)
        uniform = Simulation(config, seed=8)
        initial = uniform.snapshot()
        uniform.advance(20)
        final = uniform.snapshot()
        self.assertEqual(len(final.deaths), 30)
        self.assertEqual(final.statistics.age_deaths, 30)
        self.assertEqual(final.statistics.births, 0)
        death_times = [record.time for record in final.deaths.values()]
        self.assertGreater(len(set(death_times)), 25)
        for identifier, record in final.deaths.items():
            self.assertEqual(record.time, initial.organisms[identifier].birth_time + config.max_lifespan)
            self.assertAlmostEqual(record.organism.age_at(record.time), 2)
        zero = Simulation(replace(config, founder_age_mode='zero'), seed=8)
        zero.advance(20)
        self.assertEqual({record.time for record in zero.snapshot().deaths.values()}, {2})
        self.assertEqual(final.statistics.energy_removed_at_death, zero.snapshot().statistics.energy_removed_at_death)

    def test_newborns_start_at_zero_without_inheriting_founder_age(self):
        simulation = Simulation(quiet(starting_energy=100))
        simulation.step()
        state = simulation.snapshot()
        self.assertGreater(state.organisms[1].age_at(state.time), .1)
        child = state.organisms[2]
        self.assertEqual(child.parent_id, 1)
        self.assertEqual(child.birth_time, state.time)
        self.assertEqual(child.age_at(state.time), 0)
        self.assertEqual(child.energy, 25)

    def test_config_modes_and_exclusive_upper_bound_at_extreme_lifespans(self):
        for value in ('', 'random', True, None, 0, []):
            with self.subTest(value=value), self.assertRaises(ValueError): SimulationConfig(founder_age_mode=value)
        for lifespan in (.15, 200, 1e-300, 1e300, math.nextafter(0, 1)):
            with self.subTest(lifespan=lifespan):
                state = Simulation(quiet(initial_population=30, max_lifespan=lifespan)).snapshot()
                self.assertTrue(all(0 <= org.age_at(0) < lifespan for org in state.organisms.values()))
        self.assertEqual(SimulationConfig.from_export({}).founder_age_mode, 'zero')


class FounderExportAndReplayTests(unittest.TestCase):
    def test_batch_single_engine_and_individual_export_preserve_mode_and_ages(self):
        for mode in ('uniform', 'zero'):
            data = finished_batch(mode)
            self.assertEqual(data['configuration']['simulation']['founder_age_mode'], mode)
            for run in data['results']:
                self.assertEqual(run['configuration']['founder_age_mode'], mode)
                simulation = Simulation(SimulationConfig(**run['configuration']), seed=run['seed'])
                simulation.advance(3)
                report = experiment_report(simulation)
                self.assertEqual(run['final_statistics'], report['final_statistics'])
                self.assertEqual(run['measurements'], report['measurements'])
                self.assertEqual(report['configuration']['founder_age_mode'], mode)
                for row in report['living_organisms']:
                    self.assertEqual(row['age'], simulation.snapshot().organisms[row['id']].age_at(report['final_time']))

    def test_older_missing_field_import_normalizes_zero_without_copying_histories(self):
        data = old_batch()
        before = deepcopy(data)
        library = ExperimentLibrary()
        identity = library.add(data, 'older-F2.json')['id']
        saved = library.get(identity)['data']
        self.assertEqual(saved['configuration']['simulation']['founder_age_mode'], 'zero')
        self.assertEqual(saved['results'][0]['configuration']['founder_age_mode'], 'zero')
        self.assertIs(saved['results'][0]['measurements'], data['results'][0]['measurements'])
        self.assertEqual(data, before)
        self.assertIsNone(replay_issue(saved['results'][0]))
        again = ExperimentLibrary()
        self.assertEqual(again.get(again.add(saved, 'roundtrip')['id'])['data'], saved)

    def test_legacy_and_new_import_replay_use_correct_modes_at_time_zero(self):
        for data, mode in ((old_batch('0.6.0'), 'zero'), (old_batch(), 'zero'), (finished_batch('uniform'), 'uniform')):
            app = create_app(); client = app.test_client()
            response = client.post('/api/experiments/import?name=test.json', json=data)
            self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
            identity = response.get_json()['id']
            initial = client.get('/api/state').get_json()
            self.assertEqual(initial['parameters']['founder_age_mode'], 'uniform')
            response = client.post('/api/control', json=dict(action='replay_experiment', experiment_id=identity,
                run_number=1, run_id=initial['run_id'], expected_step=0))
            self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
            replay = response.get_json()
            self.assertEqual(replay['parameters']['founder_age_mode'], mode)
            self.assertEqual(replay['time'], 0)
            self.assertEqual(replay['seed'], 42)
            config = SimulationConfig.from_export(data['configuration']['simulation'])
            expected = Simulation(config, seed=42)
            self.assertEqual(replay['state'], json.loads(json.dumps(asdict(expected.snapshot()))))

    def test_reset_is_validated_and_export_mode_is_applied_not_pending(self):
        client = create_app().test_client()
        initial = client.get('/api/state').get_json()
        payload = dict(action='reset',run_id=initial['run_id'],expected_step=0)
        self.assertEqual(client.post('/api/control',json={**payload,'parameters':{'founder_age_mode':'invalid'}}).status_code,400)
        self.assertEqual(client.get('/api/state').get_json(),initial)
        result = client.post('/api/control',json={**payload,'parameters':{'founder_age_mode':'zero'}}).get_json()
        self.assertTrue(all(org['birth_time']==0 for org in result['state']['organisms'].values()))
        self.assertEqual(client.get('/api/export.json').get_json()['configuration']['founder_age_mode'],'zero')
        self.assertEqual(client.get('/api/batch/settings').get_json()['defaults']['simulation']['founder_age_mode'],'uniform')

    def test_library_comparison_highlights_age_mode_as_only_model_change(self):
        library = ExperimentLibrary()
        a = library.add(finished_batch('zero'), 'zero')['id']
        b = library.add(finished_batch('uniform'), 'uniform')['id']
        comparison = library.compare(a, b)
        self.assertEqual([row['parameter'] for row in comparison['configuration'] if row['different']], ['founder_age_mode'])
        self.assertTrue(comparison['paired']['available'])

    def test_missing_other_config_fields_and_new_version_missing_mode_are_rejected(self):
        data = old_batch(); data['configuration']['simulation'].pop('dt')
        with self.assertRaises(ValueError): ExperimentLibrary().add(data, 'missing')
        data = finished_batch(); data['configuration']['simulation'].pop('founder_age_mode')
        with self.assertRaisesRegex(ValueError,'founder_age_mode'): ExperimentLibrary().add(data, 'missing-new-mode')
        data = old_batch(); data['results'][0]['configuration']['founder_age_mode'] = 'uniform'
        with self.assertRaisesRegex(ValueError,'differs'): ExperimentLibrary().add(data, 'conflict')

    def test_cli_defaults_and_explicit_legacy_choice(self):
        for args, mode in (([], 'uniform'), (['--founder-age-mode','zero'], 'zero')):
            result = subprocess.run([sys.executable,'-m','ai_evolution','headless','--population','2','--steps','0',*args], capture_output=True,text=True,check=True)
            report = json.loads(result.stdout)
            self.assertEqual(report['parameters']['founder_age_mode'],mode)
            births = [org['birth_time'] for org in report['state']['organisms'].values()]
            self.assertTrue(all(value == 0 for value in births) if mode=='zero' else any(value < 0 for value in births))
