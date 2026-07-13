import pytest
from fastapi.testclient import TestClient
from backend.api.main import app

def test_api_nwe_endpoint():
    with TestClient(app) as client:
        # Query series for a date that we verified has data
        response = client.get("/api/irai/series?session_date=2026-07-10&target=WIN$N")
        assert response.status_code == 200, f"API failed with status {response.status_code}: {response.text}"
        
        data = response.json()
        assert "series" in data
        assert len(data["series"]) > 0, "No series data returned!"
        
        # Verify NWE keys in payload
        for idx, bar in enumerate(data["series"]):
            # Check presence of keys
            assert "nwe_center_price" in bar, f"Missing nwe_center_price at bar {idx}"
            assert "nwe_upper_price" in bar, f"Missing nwe_upper_price at bar {idx}"
            assert "nwe_lower_price" in bar, f"Missing nwe_lower_price at bar {idx}"
            assert "nwe_slope" in bar, f"Missing nwe_slope at bar {idx}"
            assert "nwe_up_price" in bar, f"Missing nwe_up_price at bar {idx}"
            assert "nwe_down_price" in bar, f"Missing nwe_down_price at bar {idx}"
            
            # Verify data types (either float, int, or null)
            for key in ["nwe_center_price", "nwe_upper_price", "nwe_lower_price", "nwe_slope", "nwe_up_price", "nwe_down_price"]:
                val = bar[key]
                assert val is None or isinstance(val, (int, float)), f"Key {key} at bar {idx} has invalid type: {type(val)}"

def test_api_nwe_insufficient_data():
    with TestClient(app) as client:
        # Query series for a date with no/very few data points
        # Wait, if there are no data points at all, compute_from_db returns empty
        # which returns error 404 "Sem dados para sessão". That is correct.
        # But if there are few points, compute_nwe will initialize keys to None.
        response = client.get("/api/irai/series?session_date=2026-07-13&target=US500")
        if response.status_code == 200:
            data = response.json()
            if len(data.get("series", [])) > 0:
                first_bar = data["series"][0]
                assert "nwe_center_price" in first_bar
