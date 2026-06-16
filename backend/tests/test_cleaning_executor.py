import pytest
import pandas as pd
import numpy as np
from tools.cleaning_executor import apply_cleaning_plan

def test_remove_duplicates():
    df = pd.DataFrame({"A": [1, 1, 2], "B": [3, 3, 4]})
    plan = {"steps": [{"action_id": "step1", "action": "remove_duplicates", "column": None}]}
    cleaned, stats = apply_cleaning_plan(df, plan)
    
    assert len(cleaned) == 2
    assert stats["duplicates_removed"] == 1
    assert len(stats["actions_executed"]) == 1
    assert stats["actions_executed"][0]["action_id"] == "step1"

def test_fill_mean_imputation():
    df = pd.DataFrame({"A": [1.0, 3.0, None]})
    plan = {"actions": [{"action_id": "step2", "recommendation": "mean_imputation", "column_name": "A"}]}
    cleaned, stats = apply_cleaning_plan(df, plan)
    
    assert cleaned["A"].iloc[2] == 2.0
    assert stats["missing_values_filled"] == 1

def test_fill_median_imputation():
    df = pd.DataFrame({"A": [1.0, 10.0, 100.0, None]})
    plan = {"actions": [{"action_id": "step3", "recommendation": "median_imputation", "column_name": "A"}]}
    cleaned, stats = apply_cleaning_plan(df, plan)
    
    assert cleaned["A"].iloc[3] == 10.0
    assert stats["missing_values_filled"] == 1

def test_fill_mode_imputation():
    df = pd.DataFrame({"A": ["apple", "banana", "apple", None]})
    plan = {"actions": [{"action_id": "step4", "recommendation": "mode_imputation", "column_name": "A"}]}
    cleaned, stats = apply_cleaning_plan(df, plan)
    
    assert cleaned["A"].iloc[3] == "apple"
    assert stats["missing_values_filled"] == 1

def test_fill_constant_imputation():
    df = pd.DataFrame({"A": [1.0, None]})
    # Test fallback to 0 for numeric
    plan1 = {"actions": [{"action_id": "step5a", "recommendation": "constant_imputation", "column_name": "A"}]}
    cleaned1, stats1 = apply_cleaning_plan(df, plan1)
    assert cleaned1["A"].iloc[1] == 0.0
    
    # Test explicit constant
    plan2 = {
        "actions": [{
            "action_id": "step5b",
            "recommendation": "constant_imputation",
            "column_name": "A",
            "constant_value": 99.0
        }]
    }
    cleaned2, stats2 = apply_cleaning_plan(df, plan2)
    assert cleaned2["A"].iloc[1] == 99.0

def test_clip_outliers():
    # Symmetric distribution with extreme outliers
    # IQR: Q3 (75th) - Q1 (25th)
    df = pd.DataFrame({"A": [10.0, 11.0, 12.0, 13.0, 100.0, -100.0]})
    plan = {"actions": [{"action_id": "step6", "recommendation": "clip_outliers", "column_name": "A"}]}
    cleaned, stats = apply_cleaning_plan(df, plan)
    
    assert cleaned["A"].max() < 100.0
    assert cleaned["A"].min() > -100.0
    assert stats["outliers_clipped"] == 2

def test_remove_outliers():
    df = pd.DataFrame({"A": [10.0, 11.0, 12.0, 13.0, 100.0, -100.0, None]})
    plan = {"actions": [{"action_id": "step7", "recommendation": "remove_outliers", "column_name": "A"}]}
    cleaned, stats = apply_cleaning_plan(df, plan)
    
    # Rows with 100 and -100 should be removed, None should be kept
    assert len(cleaned) == 5
    assert stats["outliers_removed"] == 2
    assert cleaned["A"].isnull().any()

def test_log_transform():
    df = pd.DataFrame({"A": [0.0, 1.0, 2.0]})
    plan = {"actions": [{"action_id": "step8", "recommendation": "log_transform", "column_name": "A"}]}
    cleaned, stats = apply_cleaning_plan(df, plan)
    
    assert np.allclose(cleaned["A"], [np.log1p(0), np.log1p(1), np.log1p(2)])
    assert stats["columns_log_transformed"] == 1

def test_frequency_encoding():
    df = pd.DataFrame({"A": ["apple", "apple", "banana"]})
    plan = {"actions": [{"action_id": "step9", "recommendation": "frequency_encoding", "column_name": "A"}]}
    cleaned, stats = apply_cleaning_plan(df, plan)
    
    # apple: 2/3, banana: 1/3
    assert np.allclose(cleaned["A"], [2/3, 2/3, 1/3])
    assert stats["columns_frequency_encoded"] == 1

def test_cast_datatype_numeric():
    # Pass check: 100% parseable
    df = pd.DataFrame({"A": ["1", "2", "3"]})
    plan = {"actions": [{"action_id": "step10a", "recommendation": "cast_numeric", "column_name": "A", "reason": "Convert to numeric"}]}
    cleaned, stats = apply_cleaning_plan(df, plan)
    assert pd.api.types.is_numeric_dtype(cleaned["A"])
    assert stats["types_converted"] == ["Converted column 'A' (object) to numeric"]
    
    # Fail check: <80% parseable
    df2 = pd.DataFrame({"A": ["1", "invalid", "invalid"]})
    cleaned2, stats2 = apply_cleaning_plan(df2, plan)
    assert not pd.api.types.is_numeric_dtype(cleaned2["A"])
    assert len(stats2["types_converted"]) == 0

def test_cast_datatype_datetime():
    df = pd.DataFrame({"A": ["2026-06-14", "2026-06-15", "2026-06-16"]})
    plan = {"actions": [{"action_id": "step10b", "recommendation": "cast_datetime", "column_name": "A", "reason": "Convert to datetime"}]}
    cleaned, stats = apply_cleaning_plan(df, plan)
    assert pd.api.types.is_datetime64_any_dtype(cleaned["A"])

def test_validate_emails():
    df = pd.DataFrame({"A": ["test@example.com", "invalid-email", None, "valid.email@domain.co.uk"]})
    plan = {"actions": [{"action_id": "step11", "recommendation": "validate_emails", "column_name": "A"}]}
    cleaned, stats = apply_cleaning_plan(df, plan)
    
    assert cleaned["A"].iloc[1] is np.nan
    assert cleaned["A"].iloc[0] == "test@example.com"
    assert cleaned["A"].iloc[3] == "valid.email@domain.co.uk"
    assert stats["emails_cleaned"] == 1

def test_trim_text():
    df = pd.DataFrame({"A": ["  hello  ", "world", None]})
    plan = {"actions": [{"action_id": "step12", "recommendation": "trim_text", "column_name": "A"}]}
    cleaned, stats = apply_cleaning_plan(df, plan)
    
    assert cleaned["A"].iloc[0] == "hello"
    assert cleaned["A"].iloc[1] == "world"
    assert stats["text_trimmed"] == 1

def test_drop_constant():
    df = pd.DataFrame({"A": [1, 1, 1], "B": [1, 2, 3]})
    plan = {"actions": [{"action_id": "step13", "recommendation": "drop_constant", "column_name": "A"}]}
    cleaned, stats = apply_cleaning_plan(df, plan)
    
    assert "A" not in cleaned.columns
    assert "B" in cleaned.columns
    assert stats["columns_dropped"] == ["A"]

def test_selective_execution():
    df = pd.DataFrame({"A": [1, 1, 2], "B": [10.0, None, 12.0]})
    plan = {
        "actions": [
            {"action_id": "act1", "recommendation": "remove_duplicates", "column_name": None},
            {"action_id": "act2", "recommendation": "mean_imputation", "column_name": "B"}
        ]
    }
    
    # Only execute act2 (mean imputation)
    cleaned, stats = apply_cleaning_plan(df, plan, action_ids=["act2"])
    
    # Duplicates should NOT be removed (length remains 3)
    assert len(cleaned) == 3
    # Mean imputation should be applied (B[1] filled with 11.0)
    assert cleaned["B"].iloc[1] == 11.0
    assert stats["duplicates_removed"] == 0
    assert stats["missing_values_filled"] == 1
    assert len(stats["actions_executed"]) == 1
    assert stats["actions_executed"][0]["action_id"] == "act2"
