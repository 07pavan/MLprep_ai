"""Validation utilities"""
import pandas as pd
import re

def validate_csv_file(file) -> tuple[bool, str]:
    """Validate uploaded CSV file"""
    try:
        # Check file extension
        if not file.name.endswith('.csv'):
            return False, "File must be a CSV file"
        
        # Check file size (100MB limit)
        file.seek(0, 2)  # Seek to end
        size_mb = file.tell() / (1024 * 1024)
        file.seek(0)  # Reset
        
        if size_mb > 100:
            return False, f"File too large ({size_mb:.1f}MB). Maximum 100MB"
        
        return True, "Valid"
    except Exception as e:
        return False, f"Validation error: {str(e)}"

def validate_dataframe(df: pd.DataFrame) -> tuple[bool, str]:
    """Validate dataframe"""
    if df is None or df.empty:
        return False, "DataFrame is empty"
    
    if len(df) == 0:
        return False, "No rows in dataset"
    
    if len(df.columns) == 0:
        return False, "No columns in dataset"
    
    return True, "Valid"

def sanitize_code(code: str) -> str:
    """Remove potentially dangerous code"""
    # Remove import statements except allowed ones
    allowed_imports = ['pandas', 'numpy', 'plotly', 'matplotlib', 'seaborn']
    
    lines = code.split('\n')
    safe_lines = []
    
    for line in lines:
        # Skip dangerous operations
        if any(danger in line.lower() for danger in ['os.', 'sys.', 'subprocess', 'eval', 'exec', '__import__']):
            continue
        safe_lines.append(line)
    
    return '\n'.join(safe_lines)

def extract_code_from_response(response: str) -> str:
    """Extract Python code from LLM response"""
    # Try to find code blocks
    code_pattern = r'```python\n(.*?)\n```'
    matches = re.findall(code_pattern, response, re.DOTALL)
    
    if matches:
        return matches[0]
    
    # If no code blocks, return the whole response
    return response.strip()