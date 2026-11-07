"""Current paired-trait reporting and living-only export invariants."""
import json
import unittest

from ai_evolution.experiments.r1 import Simulation, SimulationConfig
from ai_evolution.experiments.r1.exports import export_json
from ai_evolution.web.app import create_app


class ReportingRefinementTests(unittest.TestCase):
    def test_living_export_exact_fields_and_pairs(self):
        sim = Simulation(seed=42)
        sim.advance(25)
        state = sim.snapshot()
        report = json.loads(export_json(sim))
        rows = report['living_organisms']
        self.assertEqual([row['id'] for row in rows], sorted(state.organisms))
        for row in rows:
            org = state.organisms[row['id']]
            self.assertEqual(row, dict(id=org.id, parent_id=org.parent_id,
                founder_lineage_id=org.founder_lineage_id, generation=org.generation,
                speed=org.traits.speed, vision_radius=org.traits.vision_radius,
                age=org.age_at(state.time), energy=org.energy, offspring_count=org.offspring_count))
        self.assertIn('measurements', report)
        self.assertEqual(len(rows), report['final_statistics']['population'])

    def test_overlapping_pairs_remain_individual_and_singleton_empty(self):
        for count in (0, 1, 3):
            sim = Simulation(SimulationConfig(initial_population=count,
                founder_speed_min=2, founder_speed_max=2,
                founder_vision_min=5, founder_vision_max=5), seed=0)
            rows = json.loads(export_json(sim))['living_organisms']
            self.assertEqual(len(rows), count)
            self.assertEqual(len({row['id'] for row in rows}), count)
            self.assertTrue(all((row['speed'], row['vision_radius']) == (2, 5) for row in rows))

    def test_export_excludes_deaths_and_preserves_rng_and_trajectory(self):
        config = SimulationConfig(initial_food=0, food_spawn_rate=0, max_lifespan=0.3)
        sim, control = Simulation(config, seed=9), Simulation(config, seed=9)
        sim.advance(1)
        control.advance(1)
        before = sim.snapshot()
        rng = sim._rng.getstate()
        first = export_json(sim)
        self.assertEqual(first, export_json(sim))
        self.assertEqual(sim.snapshot(), before)
        self.assertEqual(sim._rng.getstate(), rng)
        sim.advance(5)
        control.advance(5)
        self.assertEqual(sim.snapshot(), control.snapshot())
        self.assertEqual(sim._rng.getstate(), control._rng.getstate())
        self.assertTrue(sim.snapshot().deaths)
        self.assertEqual(json.loads(export_json(sim))['living_organisms'], [])

    def test_api_scatter_source_and_export_are_paired_authoritative_traits(self):
        sim = Simulation(seed=2)
        client = create_app(seed=2).test_client()
        report = client.get('/api/state').get_json()
        rows = client.get('/api/export.json').get_json()['living_organisms']
        for row in rows:
            org = report['state']['organisms'][str(row['id'])]
            self.assertEqual((row['speed'], row['vision_radius']),
                             (org['traits']['speed'], org['traits']['vision_radius']))
        with client.get('/') as response:
            html = response.get_data(as_text=True)
        self.assertIn('id="trait-scatter"', html)
        self.assertIn('offspring', html.lower())
