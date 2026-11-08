"""Small hand-calculated replicates; observations are simulations, not samples."""
from copy import deepcopy
from dataclasses import asdict
import json
import math
import platform
import unittest

from ai_evolution import __version__
from ai_evolution.experiments.r1 import Simulation, SimulationConfig
from ai_evolution.experiments.r1.metrics import MetricSample
from ai_evolution.experiments.r1.statistics import describe, percentile, experiment_statistics, trajectories, compare_experiments
from ai_evolution.experiments.r1.library import ExperimentLibrary, validate_batch
from ai_evolution.web.app import create_app


def fixture(food=8):
    config = asdict(SimulationConfig(initial_population=10, founder_speed_max=8, food_spawn_rate=food))
    experiments = [([0, 1, 2], [10, 4, 8], [2, 3, 4], [4, 5, 6]),
                   ([0, 1, 1.5], [10, 1, 0], [4, 5, None], [8, 9, None]),
                   ([0, 1, 2], [10, 6, 4], [6, 7, 8], [12, 13, 14])]
    results = []
    for index, (times, pops, speeds, visions) in enumerate(experiments):
        samples = []; births = deaths = 0; previous = 10
        for sequence, (time, pop, speed, vision) in enumerate(zip(times, pops, speeds, visions)):
            birth, death = max(0, pop - previous), max(0, previous - pop)
            births += birth; deaths += death
            kind = 'initial' if sequence == 0 else 'terminal' if pop == 0 else 'regular'
            samples.append(asdict(MetricSample(sequence, kind, time, round(time / .1), pop == 0,
                pop, 10, births, deaths, deaths, 0, 1 if births else 0, speed, vision,
                0 if pop else None, 0 if pop else None, birth, death, 0)))
            previous = pop
        results.append(dict(schema_version=1, experiment='R1', milestone='E', run_number=index+1,
            seed=index, configuration=config, engine_version=__version__, python_version=platform.python_version(),
            final_time=times[-1], final_step=samples[-1]['step'], is_terminal=pops[-1]==0,
            survived=pops[-1]>0, stop_reason='duration' if pops[-1] else 'extinction',
            final_statistics=dict(samples[-1]), measurements=samples,
            reporting=dict(effective_interval=1.0, dropped_samples=0, retained_samples=3, total_samples=3)))
    return dict(schema_version=1, batch_id='source-batch', status='completed', engine_version=__version__,
        python_version=platform.python_version(), configuration=dict(runs=3, duration=2, starting_seed=0, simulation=config),
        completed_runs=3, total_runs=3, results=results, summary={})


class StatisticsTests(unittest.TestCase):
    def test_describe_and_percentile_independent_expected_values(self):
        self.assertEqual(describe([0,4,8]), dict(count=3, mean=4, stddev=4, median=4, minimum=0, maximum=8))
        self.assertIsNone(describe([])['mean'])
        self.assertIsNone(describe([5])['stddev'])
        self.assertEqual(describe([3,7])['median'], 5)
        self.assertAlmostEqual(percentile([2,4,6], .1), 2.4)
        self.assertAlmostEqual(percentile([2,4,6], .9), 5.6)
        self.assertEqual(percentile([9], .9), 9)
        self.assertIsNone(percentile([], .1))

    def test_population_traits_and_observed_bottlenecks(self):
        stats = experiment_statistics(fixture())
        self.assertEqual(stats['population']['mean'], 4)
        self.assertEqual(stats['population']['stddev'], 4)
        self.assertEqual(stats['population']['median'], 4)
        self.assertEqual(stats['speed']['count'], 2)
        self.assertEqual(stats['speed']['mean'], 6)
        self.assertAlmostEqual(stats['speed']['stddev'], math.sqrt(8))
        self.assertEqual(stats['vision']['mean'], 10)
        self.assertAlmostEqual(stats['vision']['stddev'], math.sqrt(32))
        self.assertAlmostEqual(stats['extinction_percentage'], 100/3)
        self.assertEqual(stats['bottlenecks']['at_most_5'], 3)
        self.assertEqual(stats['bottlenecks']['exactly_1'], 1)
        self.assertEqual([row['minimum'] for row in stats['minimum_populations']], [4,0,4])
        self.assertAlmostEqual(stats['minimum_observed_population']['mean'], 8/3)

    def test_initial_measurement_excluded_and_single_all_extinct(self):
        data = fixture(); data['results'] = [data['results'][0]]
        data['results'][0]['measurements'][0]['population'] = 1
        stats = experiment_statistics(data)
        self.assertEqual(stats['bottlenecks']['exactly_1'], 0)
        self.assertIsNone(stats['population']['stddev'])
        data['results'] = [fixture()['results'][1]]
        stats = experiment_statistics(data)
        self.assertEqual(stats['population']['mean'], 0)
        self.assertEqual(stats['speed']['count'], 0)
        self.assertIsNone(stats['vision']['mean'])
        self.assertEqual(stats['extinction_percentage'], 100)
        data['results'][0]['measurements'] = [data['results'][0]['measurements'][0]]
        self.assertIsNone(experiment_statistics(data)['minimum_populations'][0]['minimum'])

    def test_trajectories_use_recorded_values_and_zero_only_for_extinct_population(self):
        result = trajectories(fixture())
        self.assertTrue(result['available'])
        self.assertEqual([row['time'] for row in result['rows']], [0,1,2])
        first, middle, last = result['rows']
        self.assertEqual(first['speed']['mean'], 4)
        self.assertAlmostEqual(first['speed']['p10'], 2.4)
        self.assertAlmostEqual(middle['population']['mean'], 11/3)
        self.assertAlmostEqual(middle['population']['p90'], 5.6)
        self.assertEqual(last['population']['mean'], 4)
        self.assertAlmostEqual(last['population']['p10'], .8)
        self.assertEqual(last['speed']['mean'], 6)
        self.assertEqual(last['speed']['count'], 2)
        self.assertEqual(last['population']['count'], 3)

    def test_incompatible_or_incomplete_sampling_explained_without_interpolation(self):
        for change in ('interval', 'missing', 'retained', 'irregular'):
            data = fixture()
            if change == 'interval': data['results'][0]['reporting']['effective_interval'] = 1.2
            if change == 'missing': data['results'][0]['measurements'].pop(1)
            if change == 'retained': data['results'][0]['reporting']['dropped_samples'] = 1
            if change == 'irregular': data['results'][0]['measurements'][1]['time'] = .5
            with self.subTest(change=change):
                result = trajectories(data)
                self.assertFalse(result['available'])
                self.assertTrue(result['reason'])

    def test_float_time_tolerance_and_extinction_zero_extension(self):
        data = fixture()
        data['results'][0]['measurements'][1]['time'] += 1e-12
        self.assertTrue(trajectories(data)['available'])
        data['results'] = [data['results'][1]]
        rows = trajectories(data)['rows']
        self.assertEqual(rows[-1]['population']['mean'], 0)
        self.assertIsNone(rows[-1]['speed']['mean'])
        self.assertEqual(rows[-1]['speed']['count'], 0)

    def test_paired_seed_differences_and_configuration_comparison(self):
        a, b = fixture(), fixture(food=1)
        for row, pop, speed in zip(b['results'], [10,0,2], [5,None,7]):
            row['final_statistics']['population'] = pop
            row['final_statistics']['mean_speed'] = speed
        comparison = compare_experiments(a,b)
        changed = [row['parameter'] for row in comparison['configuration'] if row['different']]
        self.assertEqual(changed, ['food_spawn_rate'])
        self.assertTrue(comparison['trajectory_compatible'])
        self.assertEqual([row['population'] for row in comparison['paired']['rows']], [2,0,-2])
        self.assertEqual(comparison['paired']['statistics']['population']['mean'], 0)
        self.assertEqual(comparison['paired']['statistics']['population']['stddev'], 2)
        self.assertEqual(comparison['paired']['statistics']['speed']['count'], 2)
        self.assertAlmostEqual(comparison['paired']['statistics']['speed']['stddev'], math.sqrt(2))
        self.assertIsNone(comparison['paired']['rows'][1]['speed'])

    def test_unpaired_durations_multiple_changes_and_zero_denominator(self):
        a, b = fixture(), fixture()
        b['results'][0]['seed'] = 99
        b['configuration']['duration'] = 3
        b['configuration']['simulation']['movement_cost'] = 1
        b['configuration']['simulation']['vision_cost'] = 1
        result = compare_experiments(a,b)
        self.assertFalse(result['paired']['available'])
        self.assertFalse(result['trajectory_compatible'])
        self.assertTrue(any('Multiple' in value for value in result['warnings']))
        a['results'] = [a['results'][1]]
        result = compare_experiments(a,b)
        self.assertIsNone(result['differences']['population']['percentage_change_from_a'])
        self.assertIsNone(result['differences']['speed']['difference_b_minus_a'])


class LibraryTests(unittest.TestCase):
    def test_multiple_unique_ids_rename_remove_and_original_batch_export(self):
        library = ExperimentLibrary(); data = fixture()
        a, b = library.add(data, 'A.json'), library.add(deepcopy(data), 'B.json')
        self.assertNotEqual(a['id'], b['id'])
        self.assertNotEqual(a['id'], data['batch_id'])
        library.rename(a['id'], '<b>A</b>')
        self.assertEqual(library.get(a['id'])['name'], '<b>A</b>')
        self.assertIs(library.get(a['id'])['data'], data)  # No extra history copies.
        library.remove(a['id'])
        self.assertEqual(len(library.list()),1)
        self.assertEqual(library.get(b['id'])['data']['results'][0]['seed'],0)
        with self.assertRaises(ValueError): library.get(a['id'])

    def test_reject_invalid_schema_single_run_missing_fields_counts_and_nonfinite(self):
        mutations = [lambda d: d.update(schema_version=2), lambda d: d.pop('results'),
                     lambda d: d.update(completed_runs=2), lambda d: d['configuration'].update(simulation={}),
                     lambda d: d['results'][0]['measurements'][1].update(mean_speed=float('nan')),
                     lambda d: d['results'][0]['measurements'][1].pop('vision_stddev'),
                     lambda d: d['results'][0]['measurements'][1].update(population=-1),
                     lambda d: d['results'][0]['measurements'][1].update(time=3),
                     lambda d: d['results'][0].update(seed=44),
                     lambda d: d['results'][0]['final_statistics'].update(population=9)]
        for mutation in mutations:
            data = fixture(); mutation(data)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): validate_batch(data)
        with self.assertRaises(ValueError): validate_batch({'schema_version':1, 'experiment':'R1'})

    def test_missing_samples_disable_trajectories_but_valid_final_data_remains(self):
        data = fixture(); data['results'][0]['measurements'].pop(1)
        library = ExperimentLibrary(); meta = library.add(data,'missing')
        self.assertFalse(library.get(meta['id'])['trajectories']['available'])
        self.assertEqual(library.get(meta['id'])['statistics']['population']['mean'],4)

    def test_name_and_capacity_validation(self):
        library = ExperimentLibrary()
        for name in ('', 'x'*121, 'line\nfeed'):
            with self.assertRaises(ValueError): library.add(fixture(),name)
        for index in range(8): library.add(fixture(),str(index))
        with self.assertRaisesRegex(ValueError,'full'): library.add(fixture(),'overflow')


class ExperimentApiTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(); self.client = self.app.test_client()
        self.runner = self.app.extensions['batch_runner']
        self.addCleanup(self.runner.wait, 3)

    def upload(self, data=None, name='old-F1.json'):
        return self.client.post('/api/experiments/import?name='+name, data=json.dumps(data or fixture()), content_type='application/json')

    def test_import_valid_F1_export_and_safe_name(self):
        data = fixture()
        data['engine_version'] = '0.6.0'
        for run in data['results']: run['engine_version'] = '0.6.0'
        response = self.upload(data, 'F1.json')
        self.assertEqual(response.status_code,201,response.get_data(as_text=True))
        identity = response.get_json()['id']
        detail = self.client.get('/api/experiments/'+identity).get_json()
        self.assertEqual(detail['statistics']['population']['mean'],4)
        self.assertTrue(detail['trajectories']['available'])
        self.assertEqual(self.client.post(f'/api/experiments/{identity}/name',json={'name':'<script>alert(1)</script>'}).status_code,200)
        self.assertEqual(self.client.get('/api/experiments').get_json()['experiments'][0]['name'],'<script>alert(1)</script>')
        exported = self.client.get(f'/api/experiments/{identity}/export.json').get_json()
        self.assertEqual(exported,data)

    def test_malformed_json_wrong_schema_nonfinite_and_oversized_request(self):
        for raw in ('not json','[]', '{"schema_version":99}', '{"schema_version":NaN}'):
            response = self.client.post('/api/experiments/import',data=raw,content_type='application/json')
            self.assertEqual(response.status_code,400)
            self.assertIn('error',response.get_json())
        self.app.config['MAX_CONTENT_LENGTH'] = 10
        self.assertEqual(self.upload().status_code,413)
        self.assertEqual(self.client.get('/api/experiments').get_json()['experiments'],[])

    def test_automatic_completed_batches_coexist_and_current_batch_replacement(self):
        for seed in (10,20):
            response = self.client.post('/api/batch',json=dict(runs=2,duration=.2,starting_seed=seed,simulation={'initial_population':2,'initial_food':0,'food_spawn_rate':0}))
            self.assertEqual(response.status_code,202)
            self.runner.wait(3)
            self.assertIsNone(self.runner.status()['library_error'])
        entries = self.client.get('/api/experiments').get_json()['experiments']
        self.assertEqual(len(entries),2)
        self.assertEqual([row['configuration']['starting_seed'] for row in entries],[10,20])
        self.assertEqual(self.client.delete('/api/experiments/'+entries[0]['id']).status_code,200)
        self.assertEqual(len(self.client.get('/api/experiments').get_json()['experiments']),1)
        self.assertEqual(self.runner.status()['completed_runs'],2)

    def test_imported_and_executed_replays_start_at_zero_preserve_rng_and_single_state(self):
        before = self.client.get('/api/state').get_json()
        identity = self.upload().get_json()['id']
        self.client.get('/api/experiments/'+identity)
        self.assertEqual(self.client.get('/api/state').get_json(),before)
        response = self.client.post('/api/control',json=dict(action='replay_experiment',experiment_id=identity,run_number=2,run_id=before['run_id'],expected_step=0))
        self.assertEqual(response.status_code,200,response.get_data(as_text=True))
        replay = response.get_json()
        self.assertEqual(replay['parameters']['initial_population'],10)
        self.assertEqual(replay['seed'],1)
        self.assertEqual(replay['time'],0)
        expected = Simulation(SimulationConfig(**fixture()['configuration']['simulation']),seed=1)
        self.assertEqual(replay['state'],json.loads(json.dumps(asdict(expected.snapshot()))))

    def test_replay_unknown_version_refused_without_single_state_changes(self):
        data = fixture(); data['engine_version']='99.0'
        for run in data['results']: run['engine_version']='99.0'
        identity = self.upload(data).get_json()['id']
        self.assertIn('unsupported',self.client.get('/api/experiments/'+identity).get_json()['replay_issue'])
        before=self.client.get('/api/state').get_json()
        response=self.client.post('/api/control',json=dict(action='replay_experiment',experiment_id=identity,run_number=1,run_id=before['run_id'],expected_step=0))
        self.assertEqual(response.status_code,409)
        self.assertEqual(self.client.get('/api/state').get_json(),before)

    def test_comparison_routes_and_stale_ids(self):
        a=self.upload().get_json()['id']; b=self.upload(fixture(food=1),'B.json').get_json()['id']
        data=self.client.get(f'/api/experiments/compare?a={a}&b={b}').get_json()
        self.assertTrue(data['paired']['available'])
        self.assertEqual(data['paired']['statistics']['population']['mean'],0)
        self.assertEqual(self.client.get(f'/api/experiments/compare?a={a}&b={a}').status_code,400)
        self.assertEqual(self.client.get('/api/experiments/missing').status_code,404)
        self.assertEqual(self.client.get(f'/api/experiments/{a}/runs/99').status_code,404)


class AdditionalRegressionTests(unittest.TestCase):
    def test_all_extinct_initially_and_zero_completed_statistics(self):
        app = create_app(); client=app.test_client(); runner=app.extensions['batch_runner']
        client.post('/api/batch', json=dict(runs=2,duration=2,simulation={'initial_population':0}))
        runner.wait(3)
        entries=client.get('/api/experiments').get_json()['experiments']
        self.assertEqual(len(entries),1)
        detail=client.get('/api/experiments/'+entries[0]['id']).get_json()
        self.assertEqual(detail['statistics']['extinction_percentage'],100)
        self.assertEqual(detail['statistics']['bottlenecks']['observed_runs'],0)
        self.assertIsNone(detail['statistics']['bottlenecks']['at_most_5_percentage'])
        self.assertTrue(all(row['population']['mean']==0 and row['speed']['count']==0 for row in detail['trajectories']['rows']))
        data=fixture(); data.update(results=[], completed_runs=0,status='cancelled')
        library=ExperimentLibrary(); identity=library.add(data,'cancelled')['id']
        self.assertIsNone(library.get(identity)['statistics']['population']['mean'])
        self.assertFalse(library.get(identity)['trajectories']['available'])

    def test_new_executed_library_run_replay_after_another_batch_replaces_current(self):
        app=create_app(); client=app.test_client(); runner=app.extensions['batch_runner']
        for seed in (12,24):
            client.post('/api/batch',json=dict(runs=1,duration=.2,starting_seed=seed,simulation={'initial_population':3}))
            runner.wait(3)
        identity=client.get('/api/experiments').get_json()['experiments'][0]['id']
        before=client.get('/api/state').get_json()
        replay=client.post('/api/control',json=dict(action='replay_experiment',experiment_id=identity,run_number=1,run_id=before['run_id'],expected_step=0))
        self.assertEqual(replay.status_code,200)
        self.assertEqual(replay.get_json()['seed'],12)
        self.assertEqual(replay.get_json()['time'],0)
        self.assertEqual(replay.get_json()['parameters']['initial_population'],3)

    def test_import_inconsistent_configuration_bool_and_terminal_sequence_rejected(self):
        data=fixture(); data['results'][0]['configuration']=dict(data['configuration']['simulation'],initial_population=True)
        with self.assertRaises(ValueError):validate_batch(data)
        data=fixture();data['results'][0]['run_number']=True
        with self.assertRaises(ValueError):validate_batch(data)
        data=fixture(); data['results'][0]['measurements'][1].update(terminal=True,population=0,mean_speed=None,mean_vision=None,speed_stddev=None,vision_stddev=None,total_deaths=10,starvation_deaths=10)
        with self.assertRaises(ValueError):validate_batch(data)

    def test_nonfinite_extra_metadata_python_version_and_invalid_replay_id(self):
        app=create_app();client=app.test_client()
        raw=json.dumps(fixture())[:-1]+',"extra":1e999}'
        self.assertEqual(client.post('/api/experiments/import',data=raw,content_type='application/json').status_code,400)
        data=fixture();data['python_version']='0.0.0'
        for run in data['results']:run['python_version']='0.0.0'
        identity=client.post('/api/experiments/import',json=data).get_json()['id']
        self.assertIn('Python',client.get('/api/experiments/'+identity).get_json()['replay_issue'])
        before=client.get('/api/state').get_json()
        self.assertEqual(client.post('/api/control',json=dict(action='replay_experiment',experiment_id=[],run_number=1,run_id=before['run_id'],expected_step=0)).status_code,409)

    def test_library_full_does_not_fail_completed_batch_or_discard_previous(self):
        app=create_app();client=app.test_client();library=app.extensions['experiment_library'];runner=app.extensions['batch_runner']
        for index in range(8):library.add(fixture(),str(index))
        client.post('/api/batch',json=dict(runs=1,duration=.1,simulation={'initial_population':0}))
        runner.wait(3)
        self.assertEqual(runner.status()['status'],'completed')
        self.assertIn('full',runner.status()['library_error'])
        self.assertEqual(len(library.list()),8)
        self.assertEqual(runner.status()['completed_runs'],1)


class NumericBoundaryTests(unittest.TestCase):
    def test_tiny_interval_disables_grid_without_overflow(self):
        data=fixture()
        for run in data['results']:run['reporting']['effective_interval']=1e-300
        result=trajectories(data)
        self.assertFalse(result['available'])
        self.assertIn('limit',result['reason'])

    def test_overflowing_percentage_change_is_unavailable_not_infinity(self):
        a,b=fixture(),fixture()
        for run in a['results']:
            if run['survived']:run['final_statistics']['mean_speed']=1e-310
        result=compare_experiments(a,b)
        self.assertIsNone(result['differences']['speed']['percentage_change_from_a'])
        json.dumps(result,allow_nan=False)


class FineTimeResolutionTests(unittest.TestCase):
    def test_tolerance_does_not_merge_adjacent_tiny_recorded_times(self):
        data=fixture();data['configuration']['duration']=2e-10
        for run in data['results']:
            run['final_time'] *= 1e-10
            run['reporting']['effective_interval']=1e-10
            for row in run['measurements']:row['time'] *= 1e-10
        result=trajectories(data)
        self.assertTrue(result['available'])
        self.assertEqual(len(result['rows']),3)
        self.assertAlmostEqual(result['rows'][1]['population']['mean'],11/3)
        self.assertEqual(result['rows'][0]['population']['mean'],10)
        self.assertEqual(result['rows'][-1]['population']['mean'],4)
