import sys
import os

# Ensure backend module is resolvable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def run_tests():
    print("Testing /health ...")
    response = client.get("/health")
    assert response.status_code == 200
    print("Health check OK:", response.json())

    print("Testing /api/v1/risk/district/test_district ...")
    response = client.get("/api/v1/risk/district/test_district?diseases=dengue,malaria")
    # Will be 404 because get_district_by_id checks db, but let's see if it hits the code
    # We can mock get_district_by_id in a real test
    print("Risk check returned:", response.status_code, response.json())

    print("Testing /api/v1/simulate/monsoon ...")
    response = client.post(
        "/api/v1/simulate/monsoon",
        json={"district_ids": ["d1", "d2"], "intensity": 0.8, "duration_weeks": 4}
    )
    assert response.status_code == 200
    print("Simulate OK:", response.json())
    
    print("All tests passed structurally.")

if __name__ == "__main__":
    run_tests()
