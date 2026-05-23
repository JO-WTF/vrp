import json
import sys
import tempfile
import unittest
from pathlib import Path

PYTHON_INTEROP = Path(__file__).resolve().parents[1]
if str(PYTHON_INTEROP) not in sys.path:
    sys.path.insert(0, str(PYTHON_INTEROP))

from vrp_cli.vis.tracker import SolveTracker


class DummySolution:
    def __init__(self, cost: float, tours=None, unassigned=None):
        self.total_cost = cost
        self.statistic = {"cost": cost, "distance": 1, "duration": 1, "times": {}}
        self.tours = tours or [{"vehicleId": "vehicle_1", "stops": []}]
        self.unassigned = unassigned or []


class SolveTrackerTest(unittest.TestCase):
    def test_tracker_persists_route_data_for_non_best_snapshots(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = SolveTracker(run_name="test-run", save_dir=tmpdir, save_every=1)

            tracker.callback(1, DummySolution(cost=10.0))
            tracker.callback(2, DummySolution(cost=20.0))

            saved = json.loads(Path(tmpdir, "test-run.json").read_text(encoding="utf-8"))

            self.assertEqual(len(saved["history"]), 2)
            self.assertIn("tours", saved["history"][0])
            self.assertIn("unassigned", saved["history"][0])
            self.assertIn("tours", saved["history"][1])
            self.assertIn("unassigned", saved["history"][1])


if __name__ == "__main__":
    unittest.main()
