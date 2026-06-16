import pytest
import pandas as pd
from unittest.mock import MagicMock, patch

from services.intent_classifier import IntentClassifier
from services.query_engine import DeterministicQueryEngine, CopilotQueryEngine
from services.llm_generator import LLMGenerator
from services.response_formatter import ResponseFormatter

def test_intent_classifier():
    columns = ["age", "salary", "department_name", "joining_date"]
    
    # Simple Operations
    assert IntentClassifier.classify("how many rows?", columns) == ("SIMPLE", {"op": "count"})
    assert IntentClassifier.classify("count records", columns) == ("SIMPLE", {"op": "count"})
    assert IntentClassifier.classify("average salary", columns) == ("SIMPLE", {"op": "aggregation", "agg_op": "mean", "column": "salary"})
    assert IntentClassifier.classify("sum salary by department_name", columns) == ("SIMPLE", {"op": "groupby", "agg_op": "sum", "val_column": "salary", "group_column": "department_name"})
    assert IntentClassifier.classify("age > 30", columns) == ("SIMPLE", {"op": "filter", "column": "age", "operator": ">", "value": 30})
    
    # Complex/Unsupported Operations
    assert IntentClassifier.classify("what is the correlation between age and salary?", columns) == ("COMPLEX", None)
    assert IntentClassifier.classify("join this with another table", columns) == ("COMPLEX", None)
    assert IntentClassifier.classify("give me the distribution of age", columns) == ("COMPLEX", None)


def test_deterministic_query_execution():
    df = pd.DataFrame({
        "age": [25, 30, 35, 40],
        "salary": [50000, 60000, 70000, 80000],
        "dept": ["IT", "HR", "IT", "HR"]
    })
    
    # Count
    assert DeterministicQueryEngine.execute(df, {"op": "count"}) == 4
    
    # Aggregation
    assert DeterministicQueryEngine.execute(df, {"op": "aggregation", "agg_op": "mean", "column": "age"}) == 32.5
    assert DeterministicQueryEngine.execute(df, {"op": "aggregation", "agg_op": "sum", "column": "salary"}) == 260000
    assert DeterministicQueryEngine.execute(df, {"op": "aggregation", "agg_op": "min", "column": "age"}) == 25
    assert DeterministicQueryEngine.execute(df, {"op": "aggregation", "agg_op": "max", "column": "age"}) == 40
    
    # Groupby
    groupby_res = DeterministicQueryEngine.execute(df, {"op": "groupby", "agg_op": "mean", "val_column": "salary", "group_column": "dept"})
    assert isinstance(groupby_res, pd.DataFrame)
    assert len(groupby_res) == 2
    # Verify values
    hr_sal = groupby_res[groupby_res["dept"] == "HR"]["salary"].values[0]
    it_sal = groupby_res[groupby_res["dept"] == "IT"]["salary"].values[0]
    assert hr_sal == 70000
    assert it_sal == 60000
    
    # Filter
    filter_res = DeterministicQueryEngine.execute(df, {"op": "filter", "column": "age", "operator": ">", "value": 30})
    assert len(filter_res) == 2
    assert list(filter_res["age"]) == [35, 40]


def test_invalid_query_handling():
    # References non-existent column
    columns = ["age", "salary"]
    intent, args = IntentClassifier.classify("average of bonus", columns)
    assert intent == "COMPLEX"  # Should fall back to COMPLEX because column not found


def test_row_truncation_limit():
    # Create large dataframe
    df = pd.DataFrame({"x": range(1000)})
    
    # Format success response
    res = ResponseFormatter.format_result(
        success=True,
        result=df,
        executed_code="result = df",
        error_msg=None,
        execution_type="DETERMINISTIC",
        execution_time_ms=10,
        debug_mode=False
    )
    
    assert res["success"] is True
    assert len(res["data"]) == 500  # Truncated to 500
    assert res["truncation_meta"] == {
        "truncated": True,
        "total_rows": 1000,
        "returned_rows": 500
    }
    assert "code" not in res  # code key is hidden when debugMode is False


def test_metadata_generation():
    df = pd.DataFrame({"age": [20, 30]})
    res = ResponseFormatter.format_result(
        success=True,
        result=df,
        executed_code="result = df",
        error_msg=None,
        execution_type="DETERMINISTIC",
        execution_time_ms=123,
        debug_mode=True
    )
    assert res["execution_type"] == "DETERMINISTIC"
    assert res["execution_time_ms"] == 123
    assert res["code"] == "result = df"  # Returned in debug mode


def test_llm_fallback_behavior():
    df = pd.DataFrame({"age": [20, 30]})
    
    # Mock LLM generation to return a dummy value
    with patch("services.llm_generator.LLMGenerator.generate_and_execute") as mock_llm:
        mock_llm.return_value = (True, 25.0, "result = df['age'].mean()", None)
        
        # Test complex query routing
        res = CopilotQueryEngine.process_query(
            df=df,
            question="what is the average age plus 5?",
            chat_history=[],
            persona="general",
            debug_mode=True
        )
        
        assert res["success"] is True
        assert res["execution_type"] == "LLM"
        assert res["data"] == 25.0
        assert res["code"] == "result = df['age'].mean()"
        mock_llm.assert_called_once()
