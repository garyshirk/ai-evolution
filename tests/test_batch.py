"""Batch orchestration must preserve the single engine's seeded outcomes."""
from dataclasses import asdict, replace
import json
from threading import Event
import unittest
from unittest.mock import patch

from ai_evolution.experiments.r1 import Simulation, SimulationConfig
from ai_evolution.experiments.r1.batch import BatchConfig, BatchLimits, BatchRunner, aggregate, execute_batch
from ai_evolution.experiments.r1.exports import experiment_report
from ai_evolution.web.app import create_app


def config(**changes):
    values = dict(initial_population=2, initial_food=0, food_spawn_rate=0)
    values.update(changes)
    return SimulationConfig(**values)


def execute(options, cancel=None, completed=None, progress=None, limits=None):
    rows = []
    def collect(row):
        rows.append(row)
        if completed:
            completed(row)
    execute_batch(options, limits or BatchLimits(), cancel or Event(), collect,
                  progress or (lambda *args: None))
    return rows


class BatchEngineTests(unittest.TestCase):
    def test_defaults_and_validation(self):
        defaults = BatchConfig()
        self.assertEqual((defaults.runs, defaults.duration, defaults.starting_seed), (20, 2000, 0))
        self.assertEqual(defaults.simulation, SimulationConfig())
        self.assertEqual(defaults.validate(BatchLimits()), 20000)
        invalid = [dict(runs=0), dict(runs=True), dict(runs=201), dict(runs=1.5),
                   dict(duration=0), dict(duration=float('nan')), dict(duration=float('inf')),
                   dict(duration=10001), dict(duration=0.15), dict(starting_seed=True),
                   dict(starting_seed=2**53-1), dict(simulation=config(dt=1e-300)),
                   dict(simulation=config(initial_population=501)), dict(simulation=config(food_cap=2001))]
        for updates in invalid:
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                replace(defaults, **updates).validate(BatchLimits())
        for data in (None, [], {'unknown': 1}, {'simulation': []},
                     {'simulation': {'bad': 1}}, {'simulation': {'movement_cost': -1}}):
            with self.subTest(data=data), self.assertRaises(ValueError):
                BatchConfig.from_dict(data, BatchLimits())
        with self.assertRaises(ValueError):
            BatchLimits(max_runs=0)
        with self.assertRaises(ValueError):
            defaults.validate(BatchLimits(max_retained_samples=5))

    def test_correct_count_seed_sequence_and_independent_reproducibility(self):
        options = BatchConfig(3, 0.3, -1, config())
        with patch('ai_evolution.experiments.r1.batch.Simulation', wraps=Simulation) as factory:
            rows = execute(options)
            self.assertEqual(factory.call_count, 3)
        self.assertEqual([row['seed'] for row in rows], [-1, 0, 1])
        self.assertEqual([row['run_number'] for row in rows], [1, 2, 3])
        self.assertEqual(rows, execute(options))
        for row in rows:
            self.assertEqual(row['stop_reason'], 'duration')
            self.assertAlmostEqual(row['final_time'], 0.3)

    def test_fixed_seed_batch_matches_independent_single_engine_including_rng(self):
        options = BatchConfig(1, 4.0, 42, SimulationConfig())
        rows = execute(options)
        single = Simulation(seed=42)
        single.advance(40)
        expected = experiment_report(single)
        for field in ('final_statistics', 'measurements', 'reporting', 'configuration', 'final_time'):
            self.assertEqual(rows[0][field], expected[field])
        # Capture the actual batch instance without adding a model API for testing.
        with patch('ai_evolution.experiments.r1.batch.Simulation', return_value=Simulation(seed=42)) as factory:
            execute(options)
            self.assertEqual(factory.return_value.snapshot(), single.snapshot())
            self.assertEqual(factory.return_value._rng.getstate(), single._rng.getstate())

    def test_extinction_and_initial_empty_stop_without_extra_steps(self):
        for population, time in ((2, 0.15), (0, 0)):
            rows = execute(BatchConfig(2, 1, 0, config(initial_population=population, max_lifespan=0.15)))
            self.assertEqual(len(rows), 2)
            for row in rows:
                self.assertEqual(row['stop_reason'], 'extinction')
                self.assertFalse(row['survived'])
                self.assertEqual(row['final_time'], time)
                self.assertEqual(row['final_statistics']['population'], 0)
                self.assertTrue(row['measurements'][-1]['terminal'])

    def test_aggregate_denominators_and_empty_values(self):
        extinct = execute(BatchConfig(1, 1, 0, config(initial_population=0)))[0]
        living = execute(BatchConfig(1, 0.1, 1, config()))[0]
        result = aggregate([living, extinct])
        self.assertEqual((result['completed_runs'], result['surviving_populations'], result['extinct_populations']), (2, 1, 1))
        self.assertEqual(result['survival_percentage'], 50)
        self.assertEqual(result['average_final_population'], 1)
        self.assertEqual(result['average_final_speed'], living['final_statistics']['mean_speed'])
        self.assertEqual((result['trait_mean_run_count'], result['population_mean_run_count']), (1, 2))
        self.assertIsNone(aggregate([extinct])['average_final_speed'])
        self.assertIsNone(aggregate([])['survival_percentage'])
        self.assertIsNone(aggregate([])['average_final_population'])

    def test_cancel_before_start_and_between_runs_preserves_completed(self):
        cancel = Event()
        cancel.set()
        self.assertEqual(execute(BatchConfig(3, 0.2, 0, config()), cancel), [])
        cancel.clear()
        rows = execute(BatchConfig(3, 0.2, 0, config()), cancel, lambda row: cancel.set())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['seed'], 0)

    def test_cancel_during_run_discards_only_partial_run(self):
        cancel = Event()
        original = Simulation.step
        def step(sim):
            outcome = original(sim)
            cancel.set()
            return outcome
        with patch.object(Simulation, 'step', step):
            self.assertEqual(execute(BatchConfig(2, 1, 0, config()), cancel), [])

    def test_workload_failure_does_not_silently_cull(self):
        with self.assertRaisesRegex(RuntimeError, 'resource limit'):
            execute(BatchConfig(1, 0.1, 0, config()), limits=BatchLimits(max_live_population=1))


class BatchWebTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        self.runner = self.app.extensions['batch_runner']
        self.addCleanup(self.cleanup)

    def cleanup(self):
        status = self.runner.status()
        if status['batch_id']:
            self.runner.cancel(status['batch_id'])
        self.runner.wait(3)

    def start(self, **changes):
        values = dict(runs=2, duration=0.3, starting_seed=5, simulation=asdict(config()))
        values.update(changes)
        response = self.client.post('/api/batch', json=values)
        self.assertEqual(response.status_code, 202, response.get_data(as_text=True))
        return response.get_json()['batch_id']

    def test_settings_validation_and_independent_single_run(self):
        settings = self.client.get('/api/batch/settings').get_json()
        self.assertEqual(settings['defaults']['simulation'], asdict(SimulationConfig()))
        for data in ([], {'runs': 0}, {'simulation': {'bad': 1}}):
            self.assertEqual(self.client.post('/api/batch', json=data).status_code, 400)
        before = self.client.get('/api/state').get_json()
        self.start()
        self.runner.wait(3)
        self.assertEqual(self.client.get('/api/state').get_json(), before)
        self.assertEqual(self.runner.status()['status'], 'completed')

    def test_results_and_complete_json_export(self):
        identity = self.start()
        self.runner.wait(3)
        status = self.client.get('/api/batch').get_json()
        self.assertEqual((status['completed_runs'], status['total_runs']), (2, 2))
        run = self.client.get(f'/api/batch/{identity}/runs/2').get_json()
        self.assertEqual(run['seed'], 6)
        exported = self.client.get(f'/api/batch/export.json?batch_id={identity}')
        self.assertEqual(exported.status_code, 200)
        data = json.loads(exported.data)
        self.assertEqual(data['status'], 'completed')
        self.assertEqual(data['results'][1], run)
        self.assertEqual(data['configuration']['starting_seed'], 5)
        self.assertIn('engine_version', data)
        self.assertIn('python_version', data)
        self.assertIn('measurements', run)
        self.assertNotIn('living_organisms', run)
        self.assertEqual(self.client.get(f'/api/batch/{identity}/runs/3').status_code, 404)
        run['configuration']['dt'] = 99
        self.assertEqual(self.runner.result(identity, 2)['configuration']['dt'], 0.1)

    def test_replay_full_configuration_seed_and_time_zero(self):
        parameters = config(initial_population=3, founder_speed_min=2, founder_speed_max=2,
                            max_lifespan=4, speed_mutation_probability=0.2)
        identity = self.start(simulation=asdict(parameters))
        self.runner.wait(3)
        original = self.client.get('/api/state').get_json()
        response = self.client.post('/api/control', json=dict(action='replay_batch',
            batch_id=identity, run_number=2, run_id=original['run_id'], expected_step=0))
        self.assertEqual(response.status_code, 200)
        replay = response.get_json()
        self.assertEqual(replay['parameters'], asdict(parameters))
        self.assertEqual(replay['seed'], 6)
        self.assertEqual(replay['parameters']['initial_population'], 3)
        self.assertEqual(self.client.get('/api/export.json').get_json()['configuration']['initial_population'], 3)
        self.assertEqual(replay['time'], 0)
        self.assertFalse(replay['running'])
        expected = Simulation(parameters, seed=6)
        self.assertEqual(replay['state'], json.loads(json.dumps(asdict(expected.snapshot()))))
        self.assertEqual(self.runner.status()['completed_runs'], 2)

    def test_concurrent_start_cancel_and_normal_requests_nonblocking(self):
        entered, release = Event(), Event()
        def work(*args):
            entered.set()
            release.wait(3)
        with patch('ai_evolution.experiments.r1.batch.execute_batch', side_effect=work):
            identity = self.start()
            self.assertTrue(entered.wait(1))
            try:
                self.assertEqual(self.client.get('/api/state').status_code, 200)
                self.assertEqual(self.client.get('/api/batch').get_json()['status'], 'running')
                self.assertEqual(self.client.post('/api/batch', json=dict(runs=1, duration=1)).status_code, 409)
                self.assertEqual(self.client.post('/api/batch/cancel', json={'batch_id': 'stale'}).status_code, 409)
                self.assertEqual(self.client.post('/api/batch/cancel', json={'batch_id': identity}).status_code, 200)
                self.assertEqual(self.runner.status()['status'], 'cancelling')
            finally:
                release.set()
                self.runner.wait(3)
        self.assertEqual(self.runner.status()['status'], 'cancelled')
        exported = self.client.get(f'/api/batch/export.json?batch_id={identity}').get_json()
        self.assertEqual(exported['results'], [])
        self.assertEqual(exported['status'], 'cancelled')

    def test_manager_cancellation_keeps_completed_run_and_exports(self):
        entered = Event()
        report = execute(BatchConfig(1, 0.1, 0, config()))[0]
        def work(options, limits, cancel, completed, progress):
            completed(report)
            progress(2, 1, 0.1)
            entered.set()
            cancel.wait(3)
        with patch('ai_evolution.experiments.r1.batch.execute_batch', side_effect=work):
            identity = self.start()
            self.assertTrue(entered.wait(1))
            self.runner.cancel(identity)
            self.runner.wait(3)
        data = self.runner.export(identity)
        self.assertEqual(data['status'], 'cancelled')
        self.assertEqual(data['completed_runs'], 1)
        self.assertEqual(data['results'], [report])
        self.assertEqual(data['summary']['population_mean_run_count'], 1)

    def test_failed_worker_reports_error_and_preserves_results(self):
        with patch('ai_evolution.experiments.r1.batch.execute_batch', side_effect=RuntimeError('test failure')):
            identity = self.start()
            self.runner.wait(3)
        self.assertEqual(self.runner.status()['status'], 'failed')
        self.assertEqual(self.runner.export(identity)['error'], 'test failure')

    def test_new_batch_invalidates_old_selection_and_exports(self):
        old = self.start()
        self.runner.wait(3)
        current = self.start(runs=1)
        self.runner.wait(3)
        self.assertNotEqual(old, current)
        self.assertEqual(self.client.get(f'/api/batch/export.json?batch_id={old}').status_code, 409)
        self.assertEqual(self.client.get(f'/api/batch/{old}/runs/1').status_code, 404)

    def test_tabs_assets_and_limits_customization(self):
        with self.client.get('/') as response:
            self.assertIn(b'Batch Experiments', response.data)
            self.assertIn(b'Single Simulation', response.data)
        with self.client.get('/static/batch.js') as response:
            self.assertEqual(response.status_code, 200)
        custom = create_app(batch_limits=BatchLimits(max_runs=1)).test_client()
        self.assertEqual(custom.get('/api/batch/settings').get_json()['limits']['max_runs'], 1)
        self.assertEqual(custom.post('/api/batch', json=dict(runs=2)).status_code, 400)
