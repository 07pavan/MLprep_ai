"""Analyst Agent - Performs data analysis using pandas"""
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from config import settings
from tools import PandasTool
import pandas as pd
from typing import Dict, Any
import re

class AnalystAgent:
    """Agent that performs data analysis"""
    
    def __init__(self):
        try:
            self.llm = ChatGroq(
                model=settings.PRIMARY_MODEL,
                temperature=settings.TEMPERATURE,
                groq_api_key=settings.GROQ_API_KEY
            )
        except Exception as e:
            print(f"Error initializing Groq: {e}")
            try:
                self.llm = ChatGoogleGenerativeAI(
                    model=settings.BACKUP_MODEL,
                    temperature=settings.TEMPERATURE,
                    google_api_key=settings.GOOGLE_API_KEY
                )
            except Exception as e2:
                print(f"Error initializing Gemini: {e2}")
                self.llm = None
        
        self.pandas_tool = PandasTool()
    
    def analyze(self, df: pd.DataFrame, question: str) -> Dict[str, Any]:
        """Analyze data based on user question"""
        
        # First, try simple pattern matching
        simple_result = self._try_simple_analysis(df, question)
        if simple_result:
            return simple_result
        
        # If no LLM available, fallback to basic analysis
        if self.llm is None:
            return self._basic_analysis(df, question)
        
        # Use LLM for complex questions
        try:
            return self._llm_analysis(df, question)
        except Exception as e:
            print(f"LLM analysis failed: {e}")
            return self._basic_analysis(df, question)
    
    def _try_simple_analysis(self, df: pd.DataFrame, question: str) -> Dict[str, Any]:
        """Handle simple questions with pattern matching"""
        question_lower = question.lower()
        
        try:
            # Show first/head rows
            if any(word in question_lower for word in ['first', 'head', 'top', 'show me']):
                n = 10
                numbers = re.findall(r'\d+', question)
                if numbers:
                    n = min(int(numbers[0]), 100)
                
                result = df.head(n)
                code = f"result = df.head({n})"
                return {
                    "success": True,
                    "result": result,
                    "code": code,
                    "raw_response": "Pattern matching"
                }
            
            # Count rows
            if 'how many' in question_lower or 'count' in question_lower:
                if 'row' in question_lower:
                    result = len(df)
                    code = "result = len(df)"
                    return {
                        "success": True,
                        "result": result,
                        "code": code,
                        "raw_response": "Pattern matching"
                    }
            
            # Average/Mean
            if 'average' in question_lower or 'mean' in question_lower:
                numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
                if numeric_cols:
                    col = numeric_cols[0]
                    # Try to find column name in question
                    for c in df.columns:
                        if c.lower() in question_lower:
                            if c in numeric_cols:
                                col = c
                                break
                    
                    result = df[col].mean()
                    code = f"result = df['{col}'].mean()"
                    return {
                        "success": True,
                        "result": result,
                        "code": code,
                        "raw_response": "Pattern matching"
                    }
            
            # Sum/Total
            if 'sum' in question_lower or 'total' in question_lower:
                numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
                if numeric_cols:
                    col = numeric_cols[0]
                    for c in df.columns:
                        if c.lower() in question_lower:
                            if c in numeric_cols:
                                col = c
                                break
                    
                    result = df[col].sum()
                    code = f"result = df['{col}'].sum()"
                    return {
                        "success": True,
                        "result": result,
                        "code": code,
                        "raw_response": "Pattern matching"
                    }
            
            # Summary/Describe
            if 'summary' in question_lower or 'describe' in question_lower or 'overview' in question_lower:
                result = df.describe()
                code = "result = df.describe()"
                return {
                    "success": True,
                    "result": result,
                    "code": code,
                    "raw_response": "Pattern matching"
                }
            
        except Exception as e:
            print(f"Simple analysis error: {e}")
        
        return None
    
    def _basic_analysis(self, df: pd.DataFrame, question: str) -> Dict[str, Any]:
        """Fallback when LLM is unavailable"""
        result = df.describe()
        code = "result = df.describe()"
        return {
            "success": True,
            "result": result,
            "code": code,
            "raw_response": "Fallback description analysis"
        }

    def _llm_analysis(self, df: pd.DataFrame, question: str) -> Dict[str, Any]:
        """Use LLM to generate code"""
        columns = df.columns.tolist()
        
        prompt = f"""You are a data analyst. Generate Python pandas code to answer this question.

Dataset has {len(df)} rows and {len(df.columns)} columns:
Columns: {', '.join(columns[:10])}

Question: {question}

IMPORTANT RULES:
1. Use variable name 'df' for the dataframe
2. Store final result in variable called 'result'
3. Write ONLY executable Python code
4. Keep it simple and direct
5. No explanations, only code

Example:
```python
result = df['sales'].mean()
```
"""
        response = self.llm.invoke(prompt)
        text = response.content.strip()
        
        # Extract code
        code = text
        m = re.findall(r"```python\n(.*?)\n```", text, re.DOTALL)
        if m:
            code = m[0].strip()
        else:
            m = re.findall(r"```\n(.*?)\n```", text, re.DOTALL)
            if m:
                code = m[0].strip()
        
        # Run code
        success, result = self.pandas_tool.execute_code(df, code)
        
        return {
            "success": success,
            "result": result if success else None,
            "code": code,
            "error": None if success else result,
            "raw_response": text
        }