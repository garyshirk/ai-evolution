"""Reporting measures authoritative state without changing ecological outcomes."""
import csv
from dataclasses import FrozenInstanceError, asdict
import io
import json
import math
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import unittest

from ai_evolution import __version__
from ai_evolution.experiments.r1 import Simulation, SimulationConfig
from ai_evolution.experiments.r1.exports import CSV_COLUMNS, experiment_report, export_csv, export_json
from ai_evolution.experiments.r1.metrics import MetricsCollector, distributions, histogram, measure
from ai_evolution.experiments.r1.models import Organism, Position, Traits, WorldState
from ai_evolution.web.app import create_app


def quiet_config(**values):
    settings = dict(founder_age_mode="zero", initial_population=1, initial_food=0, food_spawn_rate=0, baseline_cost=0,
                    vision_cost=0, movement_cost=0, search_speed_fraction=0, max_lifespan=1e9)
    settings.update(values)
    return SimulationConfig(**settings)


class MeasurementTests(unittest.TestCase):
    def test_known_population_moments_counts_and_generations(self):
        config = SimulationConfig(initial_population=2)
        state = WorldState(dt=0.1, step_count=10)
        state.organisms = {
            2: Organism(2, Position(2, 2), Traits(4, 8), 30, 0, 1, parent_id=1, generation=2),
            1: Organism(1, Position(1, 1), Traits(2, 4), 30, 0, 1),
        }
        state.statistics.births = 4
        state.statistics.age_deaths = 1
        state.statistics.starvation_deaths = 3
        state.statistics.highest_generation = 3
        initial = measure(state, config)
        self.assertEqual((initial.population, initial.initial_population), (2, 2))
        self.assertEqual((initial.mean_speed, initial.mean_vision), (3, 6))
        self.assertEqual((initial.speed_stddev, initial.vision_stddev), (1, 2))
        self.assertEqual((initial.total_births, initial.total_deaths, initial.highest_generation), (4, 4, 3))
        self.assertEqual((initial.starvation_deaths, initial.age_deaths), (3, 1))
        state.statistics.births += 2
        state.statistics.age_deaths += 1
        later = measure(state, config, previous=initial)
        self.assertEqual((later.births_since_previous, later.deaths_since_previous), (2, 1))

    def test_singleton_and_empty_population(self):
        simulation = Simulation(quiet_config())
        sample = simulation.current_metrics()
        self.assertEqual((sample.speed_stddev, sample.vision_stddev), (0, 0))
        empty = Simulation(quiet_config(initial_population=0))
        sample = empty.current_metrics()
        self.assertEqual(sample.population, 0)
        self.assertIsNone(sample.mean_speed)
        self.assertIsNone(sample.mean_vision)
        self.assertIsNone(sample.speed_stddev)
        self.assertIsNone(sample.vision_stddev)

    def test_bins_are_fixed_half_open_and_include_final_upper_boundary(self):
        self.assertEqual(histogram([0, 1, 2, 3, 4], 0, 4, bins=4),
                         {'edges': [0, 1, 2, 3, 4], 'counts': [1, 1, 1, 2]})
        self.assertEqual(histogram([], 0.5, 8)['counts'], [0] * 10)
        self.assertEqual(histogram([8], 0.5, 8)['counts'], [0] * 9 + [1])
        self.assertEqual(histogram([0.5], 0.5, 8)['counts'], [1] + [0] * 9)
        for invalid in (-1, 5, math.nan):
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                histogram([invalid], 0, 4)

    def test_histogram_boundaries_match_generated_trait_bins(self):
        for lower, upper in ((0.5, 8), (1, 30)):
            edges = histogram([], lower, upper)['edges']
            result = histogram(edges, lower, upper)
            self.assertEqual(result['counts'], [1] * 9 + [2])

    def test_distributions_count_only_living_orgs(self):
        simulation = Simulation(quiet_config(initial_population=3))
        state = simulation.snapshot()
        data = distributions(state, simulation.config)
        self.assertEqual(sum(data['speed']['counts']), 3)
        self.assertEqual(sum(data['vision']['counts']), 3)
        state.organisms.clear()
        self.assertEqual(distributions(state, simulation.config)['speed']['counts'], [0] * 10)


class CollectorTests(unittest.TestCase):
    def test_initial_and_default_one_unit_sampling_after_births(self):
        simulation = Simulation(quiet_config(starting_energy=100))
        self.assertEqual([row['time'] for row in simulation.metric_history()['samples']], [0])
        simulation.advance(5)
        self.assertEqual(len(simulation.metric_history()['samples']), 1)
        simulation.advance(25)
        rows = simulation.metric_history()['samples']
        self.assertEqual([row['time'] for row in rows], [0, 1, 2, 3])
        self.assertEqual([row['step'] for row in rows], [0, 10, 20, 30])
        self.assertEqual(rows[1]['total_births'], 2)
        self.assertEqual(rows[1]['births_since_previous'], 2)
        self.assertEqual(rows[1]['population'], 3)
        self.assertEqual(rows[-1]['mean_speed'], simulation.current_metrics().mean_speed)

    def test_nondividing_custom_dt_has_uniform_documented_tick_cadence(self):
        simulation = Simulation(quiet_config(dt=0.3))
        simulation.advance(12)
        data = simulation.metric_history()
        self.assertEqual(data['sample_every_steps'], 4)
        self.assertEqual(data['requested_interval'], 1)
        self.assertEqual(data['effective_interval'], 1.2)
        self.assertEqual([row['step'] for row in data['samples']], [0, 4, 8, 12])

    def test_terminal_point_includes_zero_population_and_unavailable_means(self):
        simulation = Simulation(quiet_config(initial_population=2, max_lifespan=0.15))
        simulation.advance(20)
        rows = simulation.metric_history()['samples']
        self.assertEqual([row['time'] for row in rows], [0, 0.15])
        self.assertEqual(rows[-1]['sample_type'], 'terminal')
        self.assertTrue(rows[-1]['terminal'])
        self.assertEqual(rows[-1]['population'], 0)
        self.assertEqual(rows[-1]['age_deaths'], 2)
        self.assertIsNone(rows[-1]['mean_speed'])
        self.assertIsNone(rows[-1]['speed_stddev'])
        expected = simulation.metric_history()
        simulation.advance(10)
        self.assertEqual(simulation.metric_history(), expected)

    def test_terminal_at_sample_boundary_is_not_duplicated(self):
        simulation = Simulation(quiet_config(max_lifespan=1))
        simulation.advance(20)
        self.assertEqual([row['time'] for row in simulation.metric_history()['samples']], [0, 1])

    def test_initially_empty_run_has_one_initial_terminal_point(self):
        simulation = Simulation(quiet_config(initial_population=0))
        rows = simulation.metric_history()['samples']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['sample_type'], 'initial')
        self.assertTrue(rows[0]['terminal'])

    def test_bounded_history_retains_initial_and_recent_points_and_repairs_cursors(self):
        simulation = Simulation(quiet_config(dt=1), history_limit=5)
        simulation.advance(120)
        data = simulation.metric_history()
        self.assertEqual([row['sequence'] for row in data['samples']], [0, 117, 118, 119, 120])
        self.assertEqual((data['retained_samples'], data['total_samples'], data['dropped_samples']), (5, 121, 116))
        incremental = simulation.metric_history(118)
        self.assertFalse(incremental['replace'])
        self.assertEqual([row['sequence'] for row in incremental['samples']], [119, 120])
        self.assertTrue(simulation.metric_history(1)['replace'])
        self.assertTrue(simulation.metric_history(200)['replace'])
        self.assertEqual(simulation.metric_history(120)['samples'], [])
        simulation.reset()
        self.assertEqual(simulation.metric_history()['total_samples'], 1)
        self.assertEqual(simulation.metric_history()['samples'][0]['sequence'], 0)

    def test_default_memory_limit_on_long_clock_run(self):
        simulation = Simulation(quiet_config(dt=1))
        simulation.advance(10050)
        data = simulation.metric_history()
        self.assertEqual(data['retained_samples'], 10000)
        self.assertEqual(data['samples'][0]['time'], 0)
        self.assertEqual(data['samples'][-1]['time'], 10050)
        self.assertEqual(data['dropped_samples'], 51)

    def test_measurements_do_not_mutate_world_or_rng_or_change_outcomes(self):
        config = SimulationConfig(initial_population=3, initial_food=20, world_width=8,
                                  world_height=6, starting_energy=100, food_spawn_rate=0.5,
                                  max_lifespan=2.3, speed_mutation_probability=1,
                                  vision_mutation_probability=1)
        observed = Simulation(config, seed=93)
        unobserved = Simulation(config, seed=93, collect_metrics=False)
        for steps in (1, 4, 7, 18):
            before, rng = observed.snapshot(), observed._rng.getstate()
            observed.current_metrics()
            observed.metric_history()
            distributions(before, config)
            export_csv(observed)
            export_json(observed)
            self.assertEqual(observed.snapshot(), before)
            self.assertEqual(observed._rng.getstate(), rng)
            observed.advance(steps)
            for _ in range(steps):
                unobserved.step()
            self.assertEqual(observed.snapshot(), unobserved.snapshot())
            self.assertEqual(observed._rng.getstate(), unobserved._rng.getstate())
        self.assertGreater(observed.snapshot().statistics.births, 0)
        self.assertGreater(observed.snapshot().statistics.age_deaths, 0)

    def test_histories_replay_in_batches_and_ignore_snapshot_mutation(self):
        config = quiet_config(starting_energy=100)
        a, b = Simulation(config, seed=9), Simulation(config, seed=9)
        a.advance(30)
        for _ in range(30):
            b.step()
        self.assertEqual(a.metric_history(), b.metric_history())
        changed = a.metric_history()
        changed['samples'][0]['population'] = 999
        self.assertNotEqual(changed, a.metric_history())
        a.reset(); a.advance(30)
        self.assertEqual(a.metric_history(), b.metric_history())

    def test_invalid_reporting_options(self):
        for dt in (0, -1, math.inf, True):
            with self.assertRaises(ValueError):
                MetricsCollector(dt)
        for interval in (0, -1, math.nan, True):
            with self.assertRaises(ValueError):
                MetricsCollector(0.1, interval=interval)
        for limit in (0, 1, 2.5, True):
            with self.assertRaises(ValueError):
                MetricsCollector(0.1, history_limit=limit)
        with self.assertRaises(ValueError):
            Simulation().metric_history(-2)


class ExportTests(unittest.TestCase):
    def test_csv_structure_current_endpoint_and_json_metadata(self):
        simulation = Simulation(quiet_config(initial_population=2), seed=42)
        simulation.advance(5)
        state, rng = simulation.snapshot(), simulation._rng.getstate()
        csv_rows = list(csv.DictReader(io.StringIO(export_csv(simulation))))
        self.assertEqual(list(csv_rows[0]), CSV_COLUMNS)
        self.assertEqual([row['sample_type'] for row in csv_rows], ['initial', 'current'])
        self.assertEqual(float(csv_rows[-1]['time']), 0.5)
        self.assertEqual(int(csv_rows[-1]['population']), 2)
        data = json.loads(export_json(simulation))
        self.assertEqual(data['seed'], 42)
        self.assertEqual(data['configuration'], asdict(simulation.config))
        self.assertEqual(data['engine_version'], __version__)
        self.assertEqual(data['python_version'], platform.python_version())
        self.assertEqual(data['final_time'], 0.5)
        self.assertEqual(data['final_statistics']['population'], 2)
        self.assertEqual(data['measurements'][-1]['mean_speed'], simulation.current_metrics().mean_speed)
        self.assertEqual(sum(data['histograms']['speed']['counts']), 2)
        self.assertEqual(simulation.snapshot(), state)
        self.assertEqual(simulation._rng.getstate(), rng)
        self.assertEqual(len(simulation.metric_history()['samples']), 1)

    def test_empty_and_extinct_exports(self):
        for config in (quiet_config(initial_population=0), quiet_config(max_lifespan=0.15)):
            simulation = Simulation(config)
            simulation.advance(20)
            data = json.loads(export_json(simulation))
            self.assertTrue(data['is_terminal'])
            self.assertEqual(data['measurements'][-1]['population'], 0)
            self.assertIsNone(data['measurements'][-1]['mean_vision'])
            rows = list(csv.DictReader(io.StringIO(export_csv(simulation))))
            self.assertEqual(rows[-1]['mean_speed'], '')
            self.assertEqual(rows[-1]['vision_stddev'], '')
            self.assertNotIn('NaN', export_json(simulation))

    def test_export_documents_truncated_retention_and_remains_deterministic(self):
        a = Simulation(quiet_config(dt=1), seed=42, history_limit=4)
        b = Simulation(quiet_config(dt=1), seed=42, history_limit=4)
        a.advance(20); b.advance(20)
        self.assertEqual(export_json(a), export_json(b))
        self.assertEqual(export_csv(a), export_csv(b))
        data = experiment_report(a)
        self.assertEqual(len(data['measurements']), 4)
        self.assertEqual(data['reporting']['dropped_samples'], 17)

    def test_headless_cli_writes_both_exports(self):
        with tempfile.TemporaryDirectory() as directory:
            json_path, csv_path = Path(directory) / 'report.json', Path(directory) / 'report.csv'
            result = subprocess.run([sys.executable, '-m', 'ai_evolution', 'headless',
                                     '--seed', '42', '--steps', '5', '--population', '0',
                                     '--export-json', str(json_path), '--export-csv', str(csv_path)],
                                    cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(json_path.read_text())['seed'], 42)
            self.assertEqual(len(list(csv.DictReader(io.StringIO(csv_path.read_text())))), 1)
            self.assertEqual(json.loads(result.stdout)['reporting']['samples'][0]['population'], 0)


class ReportingAPITests(unittest.TestCase):
    def setUp(self):
        self.config = quiet_config(initial_population=2, starting_energy=100)
        self.client = create_app(self.config, seed=42).test_client()
        self.report = self.client.get('/api/state').get_json()

    def action(self, action, **values):
        response = self.client.post('/api/control', json={'action': action, 'run_id': self.report['run_id'],
                                    'expected_step': self.report['state']['step_count'], **values})
        self.assertEqual(response.status_code, 200)
        self.report = response.get_json()

    def test_browser_and_headless_histories_are_identical(self):
        expected = Simulation(self.config, seed=42)
        self.action('start')
        for count in (3, 17, 10):
            self.action('advance', steps=count)
            expected.advance(count)
        history = self.client.get('/api/history').get_json()
        self.assertEqual(history['samples'], expected.metric_history()['samples'])
        self.assertEqual(self.report['measurement'], asdict(expected.current_metrics()))
        self.assertEqual(self.report['histograms'], distributions(expected.snapshot(), self.config))

    def test_pause_resume_reset_and_incremental_history(self):
        self.action('start'); self.action('advance', steps=20); self.action('pause')
        history = self.client.get('/api/history').get_json()
        self.assertEqual(self.client.get('/api/history').get_json(), history)
        self.assertEqual(self.client.get('/api/history?after=1').get_json()['samples'][0]['sequence'], 2)
        self.action('start'); self.action('advance', steps=10); self.action('pause')
        self.assertEqual(self.client.get('/api/history').get_json()['total_samples'], 4)
        old_run = self.report['run_id']
        self.action('reset')
        self.assertEqual(self.client.get('/api/history').get_json()['total_samples'], 1)
        self.assertEqual(self.client.get(f'/api/history?run_id={old_run}').status_code, 409)
        self.assertEqual(self.client.get('/api/history?after=bad').status_code, 400)
        self.assertEqual(self.client.get('/api/history?after=-2').status_code, 400)

    def test_exports_match_displayed_current_metrics_and_applied_configuration(self):
        self.action('step')
        response = self.client.get('/api/export.json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment;', response.headers['Content-Disposition'])
        data = response.get_json()
        self.assertEqual(data['configuration'], self.report['parameters'])
        for key, value in self.report['measurement'].items():
            self.assertEqual(data['final_statistics'][key], value)
        self.assertEqual(data['histograms'], self.report['histograms'])
        self.assertEqual(data['seed'], self.report['seed'])
        csv_response = self.client.get('/api/export.csv')
        self.assertEqual(csv_response.status_code, 200)
        rows = list(csv.DictReader(io.StringIO(csv_response.get_data(as_text=True))))
        self.assertEqual(float(rows[-1]['time']), self.report['time'])
        old_run = self.report['run_id']
        self.action('reset')
        self.assertEqual(self.client.get(f'/api/export.json?run_id={old_run}').status_code, 409)
        self.assertEqual(self.client.get('/api/export.xml').status_code, 400)

    def test_chart_module_is_served(self):
        response = self.client.get('/static/charts.js')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'export class Reports', response.data)
        response.close()


if __name__ == '__main__':
    unittest.main()
