import unittest
from dataclasses import asdict

from ai_evolution.experiments.r1 import Simulation, SimulationConfig
from ai_evolution.web.app import create_app


class WebTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app(seed=42).test_client()
        self.state = self.client.get("/api/state").get_json()

    def control(self, action, **extra):
        response = self.client.post("/api/control", json={
            "action": action, "run_id": self.state["run_id"],
            "expected_step": self.state["state"]["step_count"], **extra,
        })
        if response.status_code == 200:
            self.state = response.get_json()
        return response

    def test_page_and_assets(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Milestone E", response.data)
        response.close()
        for name in ("controls.js", "api.js", "world.js", "styles.css"):
            response = self.client.get(f"/static/{name}")
            self.assertEqual(response.status_code, 200)
            response.close()

    def test_initial_population_defaults_reset_and_exports(self):
        self.assertEqual(self.state["parameters"]["initial_population"], 50)
        self.assertEqual(len(self.state["state"]["organisms"]), 50)
        for population in (7, 0, 50):
            self.assertEqual(self.control("reset", parameters={"initial_population": population}).status_code, 200)
            self.assertEqual(len(self.state["state"]["organisms"]), population)
            self.assertEqual(self.state["time"], 0)
            self.assertEqual(self.state["measurement"]["initial_population"], population)
            exported = self.client.get("/api/export.json").get_json()
            self.assertEqual(exported["configuration"]["initial_population"], population)
            self.assertEqual(exported["final_statistics"]["population"], population)
            self.assertEqual(len(exported["living_organisms"]), population)
            self.assertEqual(exported["measurements"][0]["population"], population)
        self.control("step")
        self.assertEqual(self.control("reset", parameters={"initial_population": 7}).status_code, 200)
        self.assertEqual(len(self.state["state"]["organisms"]), 7)
        self.assertEqual(self.state["state"]["statistics"]["births"], 0)

    def test_initial_population_validation_is_atomic_and_reset_only(self):
        original = self.state
        for value in (-1, 2.5, True, "7", None, 501):
            with self.subTest(value=value):
                self.assertEqual(self.control("reset", parameters={"initial_population": value}).status_code, 400)
                self.assertEqual(self.client.get("/api/state").get_json(), original)
        self.assertEqual(self.control("start", parameters={"initial_population": 7}).status_code, 400)
        self.assertEqual(self.client.get("/api/state").get_json(), original)
        self.assertEqual(self.control("reset", parameters={"initial_population": 500}).status_code, 200)
        self.assertEqual(len(self.state["state"]["organisms"]), 500)

    def test_initial_population_uses_configured_application_limit(self):
        from ai_evolution.experiments.r1.batch import BatchLimits
        self.client = create_app(batch_limits=BatchLimits(max_initial_population=60)).test_client()
        self.state = self.client.get("/api/state").get_json()
        self.assertEqual(self.state["population_limit"], 60)
        self.assertEqual(self.control("reset", parameters={"initial_population": 61}).status_code, 400)
        self.assertEqual(self.control("reset", parameters={"initial_population": 60}).status_code, 200)
        self.assertEqual(len(self.state["state"]["organisms"]), 60)

    def test_initial_state_and_single_step(self):
        self.assertFalse(self.state["running"])
        self.assertEqual(self.control("step").status_code, 200)
        self.assertEqual(self.state["state"]["step_count"], 1)
        self.assertEqual(self.state["time"], 0.1)

    def test_pause_preserves_state_and_refuses_background_advance(self):
        self.control("start")
        self.control("advance", steps=5)
        self.control("pause")
        state = self.state
        self.assertEqual(self.control("advance", steps=2).status_code, 409)
        self.assertEqual(self.client.get("/api/state").get_json(), state)
        self.assertFalse(state["running"])
        self.control("start")
        self.control("advance", steps=1)
        self.assertEqual(self.state["state"]["step_count"], 6)

    def test_reset_same_seed_replays_and_invalidates_old_requests(self):
        initial = self.state
        self.control("step")
        self.control("reset")
        self.assertEqual(self.state["state"], initial["state"])
        self.assertNotEqual(self.state["run_id"], initial["run_id"])
        response = self.client.post("/api/control", json={
            "action": "step", "run_id": initial["run_id"], "expected_step": 0,
        })
        self.assertEqual(response.status_code, 409)

    def test_new_seed_takes_effect_only_on_reset(self):
        original = self.state["state"]
        self.control("reset", seed=81)
        self.assertEqual(self.state["seed"], 81)
        self.assertNotEqual(self.state["state"], original)
        self.assertFalse(self.state["running"])

    def test_batch_sizes_playback_schedules_and_headless_agree(self):
        def run(batches):
            self.control("reset", seed=42)
            self.control("start")
            for count in batches:
                self.assertEqual(self.control("advance", steps=count).status_code, 200)
            self.control("pause")
            return self.state["state"]
        slow = run([1] * 40)
        fast = run([20, 20])
        self.assertEqual(slow, fast)
        expected = Simulation(seed=42)
        expected.advance(40)
        self.assertEqual(fast["organisms"]["1"]["position"],
                         {"x": expected.snapshot().organisms[1].position.x,
                          "y": expected.snapshot().organisms[1].position.y})

    def test_duplicate_advance_is_rejected(self):
        self.control("start")
        old_step = self.state["state"]["step_count"]
        self.control("advance", steps=2)
        self.assertEqual(self.control("advance", expected_step=old_step, steps=2).status_code, 409)
        self.assertEqual(self.state["state"]["step_count"], 2)

    def test_validation_is_atomic(self):
        initial = self.state
        for action, values in (("reset", {"seed": True}), ("reset", {"seed": 2**54}),
                               ("unknown", {})):
            with self.subTest(action=action, values=values):
                self.assertEqual(self.control(action, **values).status_code, 400)
                self.assertEqual(self.client.get("/api/state").get_json(), initial)
        self.assertEqual(self.client.post("/api/control", json=[]).status_code, 400)
        self.assertEqual(self.client.post("/api/control", json={}).status_code, 409)
        self.control("start")
        for count in (0, 21, -1, True, 1.5, None):
            self.assertEqual(self.control("advance", steps=count).status_code, 400)
        self.assertEqual(self.control("step").status_code, 409)

    def test_empty_world_stays_paused(self):
        self.client = create_app(SimulationConfig(initial_population=0)).test_client()
        self.state = self.client.get("/api/state").get_json()
        self.control("start")
        self.assertFalse(self.state["running"])
        self.assertTrue(self.state["is_terminal"])
        self.control("step")
        self.assertEqual(self.state["state"]["step_count"], 0)

    def test_biological_parameters_only_apply_on_reset(self):
        original = self.state
        self.assertEqual(self.control("step", parameters={"movement_cost": 2}).status_code, 400)
        self.assertEqual(self.state, original)
        self.assertEqual(self.control("reset", parameters={"food_spawn_rate": -1}).status_code, 400)
        self.assertEqual(self.client.get("/api/state").get_json(), original)
        self.control("reset", parameters={"food_spawn_rate": 0, "movement_cost": 2, "vision_cost": 3})
        self.assertEqual(self.state["parameters"]["movement_cost"], 2)
        self.assertEqual(self.state["parameters"]["vision_cost"], 3)
        self.assertEqual(self.state["parameters"]["food_spawn_rate"], 0)
        self.assertEqual(self.state["state"]["step_count"], 0)

    def test_extinction_pauses_preserves_records_and_stops_batch(self):
        config = SimulationConfig(initial_population=2, initial_food=0, food_spawn_rate=0,
                                  max_lifespan=0.15, founder_age_mode="zero")
        self.client = create_app(config, seed=42).test_client()
        self.state = self.client.get("/api/state").get_json()
        self.control("start")
        self.control("advance", steps=20)
        self.assertTrue(self.state["is_terminal"])
        self.assertFalse(self.state["running"])
        self.assertEqual(self.state["time"], 0.15)
        self.assertEqual(self.state["state"]["step_count"], 2)
        self.assertEqual(self.state["state"]["statistics"]["age_deaths"], 2)
        self.assertEqual(len(self.state["state"]["deaths"]), 2)
        expected = Simulation(config, seed=42)
        expected.advance(20)
        import json
        self.assertEqual(self.state["state"], json.loads(json.dumps(asdict(expected.snapshot()))))
        final = self.state
        self.control("step")
        self.assertEqual(self.state["state"], final["state"])
        self.control("reset")
        self.assertFalse(self.state["is_terminal"])
        self.assertEqual(self.state["state"]["deaths"], {})


if __name__ == "__main__":
    unittest.main()
