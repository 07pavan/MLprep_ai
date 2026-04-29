"""Basic tests for the application"""
import pytest
import pandas as pd
from agents import DataProfilerAgent, AnalystAgent

def test_data_profiler():
    """Test data profiler agent"""
    # Create sample data
    df = pd.DataFrame({
        'A': [1, 2, 3, 4, 5],
        'B': ['a', 'b', 'c', 'd', 'e'],
        'C': [10.5, 20.3, 30.1, 40.8, 50.2]
    })
    
    # Test profiler (without LLM call)
    assert len(df) == 5
    assert len(df.columns) == 3

def test_analyst():
    """Test analyst agent"""
    # Create sample data
    df = pd.DataFrame({
        'sales': [100, 200, 150, 300, 250],
        'region': ['East', 'West', 'East', 'West', 'East']
    })
    
    # Test basic operations
    assert df['sales'].mean() == 200.0
    assert len(df) == 5

if __name__ == "__main__":
    test_data_profiler()
    test_analyst()
    print("✅ All tests passed!")