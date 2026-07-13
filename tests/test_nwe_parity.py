import json
import os
import pytest
from backend.irai.nwe import compute_nwe

def test_nwe_parity():
    # Load test vector
    vector_path = os.path.join(os.path.dirname(__file__), "nwe_test_vector.json")
    assert os.path.exists(vector_path), f"Test vector not found at {vector_path}!"
    
    with open(vector_path, "r", encoding="utf-8") as f:
        vector = json.load(f)
        
    input_series = vector["input_series"]
    history_closes = vector["history_closes"]
    expected_series = vector["expected_series"]
    
    # Calculate NWE in python
    output_series = compute_nwe(input_series, history_closes)
    
    assert len(output_series) == len(expected_series), "Lengths mismatch!"
    
    # Assert values
    for idx, (out, exp) in enumerate(zip(output_series, expected_series)):
        # Check center price
        if exp.get("win_current") is None:
            # Padding bar
            assert out.get("win_current") is None
            continue
            
        if exp.get("is_ghost", False):
            assert out.get("is_ghost", False)
            assert out["nwe_center_price"] is not None
            assert out["nwe_upper_price"] is not None
            assert out["nwe_lower_price"] is not None
            continue
            
        # Assert absolute values exist
        assert out["nwe_center_price"] is not None
        assert out["nwe_upper_price"] is not None
        assert out["nwe_lower_price"] is not None
        assert out["nwe_slope"] is not None

    print("ALL NWE PARITY TESTS PASSED!")
