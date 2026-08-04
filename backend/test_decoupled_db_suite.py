"""Test suite for decoupled backend API & SQLite database routes."""
import os
import sys
import unittest
from fastapi.testclient import TestClient

backend_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(backend_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from backend.app import app
from backend.database import save_job_and_records, get_all_jobs, get_job_detail, search_records


class TestDecoupledBackendAndDB(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)
        # Create a sample test job in SQLite
        self.test_job_id = save_job_and_records(
            filename="sample_perovskite.pdf",
            sam_dataset=[
                {
                    "ref_id": "1-MeO-2PACz",
                    "sam_material": "MeO-2PACz",
                    "smiles": "COc1ccc2c(c1)c3ccccc3n2CCCP(=O)(O)O",
                    "cs": 0.05, "fa": 0.85, "ma": 0.10, "pce": 22.8,
                    "confidence_colors": {"energy_e": "red"},
                    "notes": "Test SQLite row"
                }
            ],
            doi_list=[{"doi": "10.1002/adma.202301234"}]
        )

    def test_health_route(self):
        """Test GET /api/health."""
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("SQLite + CSV Dual Persistence Active", data["database_storage"])

    def test_get_jobs_route(self):
        """Test GET /api/jobs."""
        res = self.client.get("/api/jobs")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["count"] >= 1)
        self.assertTrue(any(j["job_id"] == self.test_job_id for j in data["jobs"]))

    def test_get_jobs_by_date_route(self):
        """Test GET /api/jobs with date query filter."""
        import datetime
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        res = self.client.get(f"/api/jobs?date={today_str}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["count"] >= 1)

    def test_get_job_detail_route(self):
        """Test GET /api/jobs/{job_id}."""
        res = self.client.get(f"/api/jobs/{self.test_job_id}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["job_id"], self.test_job_id)
        self.assertEqual(len(data["sam_dataset"]), 1)
        self.assertEqual(data["sam_dataset"][0]["sam_material"], "MeO-2PACz")

    def test_search_route(self):
        """Test GET /api/search?q=MeO-2PACz."""
        res = self.client.get("/api/search?q=MeO-2PACz")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["count"] >= 1)
        self.assertEqual(data["records"][0]["sam_material"], "MeO-2PACz")

    def test_export_job_excel_route(self):
        """Test GET /api/export-job-excel/{job_id}."""
        res = self.client.get(f"/api/export-job-excel/{self.test_job_id}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers["content-type"], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        self.assertTrue(len(res.content) > 1000)


if __name__ == "__main__":
    unittest.main()
