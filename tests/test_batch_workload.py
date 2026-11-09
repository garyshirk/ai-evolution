"""Workload bounds follow real recording/export behavior, not physics tick count."""
from dataclasses import asdict
import unittest
from unittest.mock import patch

from ai_evolution.experiments.r1 import Simulation, SimulationConfig
from ai_evolution.experiments.r1.batch import BatchConfig, BatchLimits
from ai_evolution.experiments.r1.exports import experiment_report
from ai_evolution.experiments.r1.metrics import MetricsCollector
from ai_evolution.web.app import create_app


def quiet_config(**updates):
    values = dict(founder_age_mode="zero", initial_population=1, initial_food=0, food_spawn_rate=0,
                  baseline_cost=0, movement_cost=0, vision_cost=0,
                  search_speed_fraction=0, max_lifespan=1e9)
    values.update(updates)
    return SimulationConfig(**values)


class BatchMeasurementWorkloadTests(unittest.TestCase):
    def test_fifty_run_validation_experiment_is_accepted_without_execution(self):
        config = SimulationConfig(speed_mutation_probability=.1, vision_mutation_probability=.1)
        options = BatchConfig(runs=50, duration=2000, starting_seed=0, simulation=config)
        self.assertEqual(options.validate(BatchLimits()), 20000)
        self.assertEqual(MetricsCollector(config.dt).retained_measurement_bound(20000), 2001)
        self.assertEqual(50 * MetricsCollector(config.dt).retained_measurement_bound(20000), 100050)
        self.assertEqual(BatchLimits().max_retained_samples, 500000)
        self.assertEqual(BatchLimits().max_total_steps, 2000000)
        self.assertEqual(MetricsCollector(config.dt).effective_interval, 1)

    def test_cadence_bound_matches_real_collector_and_export_endpoints(self):
        for dt, cases in ((.1, ((0,1), (1,2), (9,2), (10,2), (11,3), (20,3))),
                          (.3, ((1,2), (3,2), (4,2), (5,3), (8,3))),
                          (2.0, ((1,2), (2,3), (3,4)))):
            for steps, expected in cases:
                with self.subTest(dt=dt, steps=steps):
                    simulation = Simulation(quiet_config(dt=dt))
                    simulation.advance(steps)
                    collector = MetricsCollector(dt)
                    self.assertEqual(collector.retained_measurement_bound(steps), expected)
                    self.assertEqual(len(experiment_report(simulation)['measurements']), expected)
                    self.assertEqual(simulation.reporting_metadata()['sample_every_steps'], collector.every_steps)

    def test_terminal_sample_on_or_between_sampling_ticks_not_double_counted(self):
        for lifespan, ticks, rows in ((.05,1,2), (.95,10,2), (1,10,2), (1.05,11,3), (1.95,20,3), (2,20,3)):
            with self.subTest(lifespan=lifespan):
                simulation = Simulation(quiet_config(max_lifespan=lifespan))
                simulation.advance(ticks)
                report = experiment_report(simulation)
                self.assertTrue(report['is_terminal'])
                self.assertEqual(len(report['measurements']), rows)
                self.assertEqual(MetricsCollector(.1).retained_measurement_bound(ticks), rows)
                self.assertEqual(report['measurements'][-1]['time'], lifespan)
                self.assertEqual(sum(row['terminal'] for row in report['measurements']), 1)

    def test_retention_limit_and_export_row_outside_window(self):
        collector = MetricsCollector(.1, history_limit=3)
        for ticks, expected in ((19,3), (20,3), (21,4), (30,3), (31,4)):
            with self.subTest(ticks=ticks):
                simulation = Simulation(quiet_config(), history_limit=3)
                simulation.advance(ticks)
                self.assertEqual(collector.retained_measurement_bound(ticks), expected)
                self.assertEqual(len(experiment_report(simulation)['measurements']), expected)
                self.assertLessEqual(simulation.reporting_metadata()['retained_samples'], 3)
        terminal = Simulation(quiet_config(max_lifespan=2.05), history_limit=3)
        terminal.advance(21)
        self.assertEqual(len(experiment_report(terminal)['measurements']), 3)
        self.assertLessEqual(3, collector.retained_measurement_bound(21))

    def test_initially_empty_and_earlier_extinction_are_conservatively_bounded(self):
        for config in (quiet_config(initial_population=0), quiet_config(max_lifespan=.15)):
            simulation = Simulation(config)
            simulation.advance(30)
            self.assertLessEqual(len(experiment_report(simulation)['measurements']),
                                 MetricsCollector(config.dt).retained_measurement_bound(30))
        self.assertEqual(MetricsCollector(.1).retained_measurement_bound(0), 1)

    def test_genuine_over_budget_and_exact_limit_boundaries(self):
        # 100 × 6,001 samples exceeds 500,000, while 600,000 physics ticks fit.
        excessive = BatchConfig(runs=100, duration=6000, simulation=quiet_config(dt=1))
        with self.assertRaisesRegex(ValueError, 'retained measurement workload'):
            excessive.validate(BatchLimits())
        # 50 × 10,000 retained rows exactly fills the unchanged default limit.
        exact = BatchConfig(runs=50, duration=9999, simulation=quiet_config(dt=1))
        self.assertEqual(exact.validate(BatchLimits()), 9999)
        for duration, budget, accepted in ((.9,2,True), (1,2,True), (1.1,2,False), (1.1,3,True)):
            with self.subTest(duration=duration, budget=budget):
                options = BatchConfig(runs=1, duration=duration, simulation=quiet_config())
                if accepted:
                    options.validate(BatchLimits(max_retained_samples=budget))
                else:
                    with self.assertRaisesRegex(ValueError, 'retained measurement workload'):
                        options.validate(BatchLimits(max_retained_samples=budget))

    def test_physics_tick_limit_is_still_enforced(self):
        with self.assertRaisesRegex(ValueError, 'total ticks'):
            BatchConfig(runs=50, duration=5000).validate(BatchLimits())

    def test_api_accepts_requested_configuration_without_launching_worker(self):
        app = create_app()
        runner = app.extensions['batch_runner']
        config = SimulationConfig(speed_mutation_probability=.1, vision_mutation_probability=.1)
        with patch.object(runner, 'start', return_value='validated-only') as start:
            response = app.test_client().post('/api/batch', json=dict(
                runs=50, duration=2000, starting_seed=0, simulation=asdict(config)))
        self.assertEqual(response.status_code, 202, response.get_data(as_text=True))
        start.assert_called_once()
        self.assertEqual(start.call_args.args[0].simulation, config)
        self.assertEqual(runner.status()['status'], 'idle')

    def test_bound_rejects_invalid_step_counts(self):
        for steps in (-1, True, 2.5, None):
            with self.subTest(steps=steps), self.assertRaises(ValueError):
                MetricsCollector(.1).retained_measurement_bound(steps)
