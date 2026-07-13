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
            
        # Assert absolute values with tolerance
        assert abs(out["nwe_center_price"] - exp["nwe_center_price"]) < 1e-9, f"Center price mismatch at index {idx}: Py={out['nwe_center_price']}, JS={exp['nwe_center_price']}"
        assert abs(out["nwe_upper_price"] - exp["nwe_upper_price"]) < 1e-9, f"Upper price mismatch at index {idx}: Py={out['nwe_upper_price']}, JS={exp['nwe_upper_price']}"
        assert abs(out["nwe_lower_price"] - exp["nwe_lower_price"]) < 1e-9, f"Lower price mismatch at index {idx}: Py={out['nwe_lower_price']}, JS={exp['nwe_lower_price']}"
        assert abs(out["nwe_slope"] - exp["nwe_slope"]) < 1e-9, f"Slope mismatch at index {idx}: Py={out['nwe_slope']}, JS={exp['nwe_slope']}"
        
        # Assert colored values (nwe_up_price, nwe_down_price)
        if exp.get("nwe_up_price") is None:
            assert out["nwe_up_price"] is None, f"nwe_up_price should be None at index {idx}"
        else:
            assert abs(out["nwe_up_price"] - exp["nwe_up_price"]) < 1e-9, f"nwe_up_price mismatch at index {idx}: Py={out['nwe_up_price']}, JS={exp['nwe_up_price']}"
            
        if exp.get("nwe_down_price") is None:
            assert out["nwe_down_price"] is None, f"nwe_down_price should be None at index {idx}"
        else:
            assert abs(out["nwe_down_price"] - exp["nwe_down_price"]) < 1e-9, f"nwe_down_price mismatch at index {idx}: Py={out['nwe_down_price']}, JS={exp['nwe_down_price']}"

    print("ALL NWE PARITY TESTS PASSED!")
