import json
from pathlib import Path
import subprocess
import sys
import unittest

from ai_evolution.experiments.r1 import Simulation


ROOT = Path(__file__).resolve().parents[1]


class HeadlessTests(unittest.TestCase):
    def run_cli(self, *arguments):
        return subprocess.run(
            [sys.executable, "-m", "ai_evolution", *arguments],
            cwd=ROOT, capture_output=True, text=True, check=False, timeout=10,
        )

    def test_headless_json_and_engine_agree(self):
        result = self.run_cli("headless", "--seed", "42", "--steps", "12")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        expected = Simulation(seed=42)
        expected.advance(12)
        state = expected.snapshot()
        self.assertEqual(report["seed"], 42)
        self.assertEqual(report["completed_steps"], 12)
        self.assertEqual(report["state"]["step_count"], state.step_count)
        self.assertEqual(report["time"], state.time)
        self.assertFalse(report["biology_implemented"])
        self.assertFalse(report["is_terminal"])
        self.assertEqual(report["state"]["organisms"]["1"]["energy"], state.organisms[1].energy)
        self.assertEqual(len(report["state"]["food"]), 200)
        self.assertIn("engine_version", report)
        self.assertIn("python_version", report)
        self.assertEqual(report["parameters"]["dt"], 0.1)

    def test_identical_cli_runs_are_identical(self):
        args = ("headless", "--seed", "76", "--steps", "20")
        first, second = self.run_cli(*args), self.run_cli(*args)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(first.stdout, second.stdout)

    def test_cli_custom_settings(self):
        result = self.run_cli("headless", "--population", "2", "--food", "0",
                              "--dt", "0.25", "--steps", "4")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(len(report["state"]["organisms"]), 2)
        self.assertEqual(report["state"]["food"], {})
        self.assertEqual(report["time"], 1)

    def test_cli_empty_population(self):
        result = self.run_cli("headless", "--population", "0", "--steps", "100")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["requested_steps"], 100)
        self.assertEqual(report["completed_steps"], 0)
        self.assertTrue(report["is_terminal"])
        self.assertEqual(report["time"], 0)

    def test_invalid_cli_input_has_no_traceback_or_json(self):
        for args in (("--steps", "-1"), ("--dt", "nan"), ("--population", "-2"),
                     ("--food", "501"), ("--seed", "not-an-integer")):
            with self.subTest(args=args):
                result = self.run_cli("headless", *args)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertIn("error:", result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_help_identifies_foundation_scope(self):
        result = self.run_cli("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Milestone A", result.stdout)


if __name__ == "__main__":
    unittest.main()
