import logging
import time
import pandas as pd
from typing import Dict, Any, Optional

from services.intent_classifier import IntentClassifier
from services.llm_generator import LLMGenerator
from services.response_formatter import ResponseFormatter

logger = logging.getLogger(__name__)

class DeterministicQueryEngine:
    """Executes SIMPLE parsed queries deterministically on a DataFrame copy.
    
    Guarantees no arbitrary code execution (no eval/exec).
    """
    
    @staticmethod
    def execute(df: pd.DataFrame, parsed_args: Dict[str, Any]) -> Any:
        df_copy = df.copy()
        op = parsed_args.get("op")
        
        if op == "count":
            return len(df_copy)
            
        elif op == "aggregation":
            agg_op = parsed_args["agg_op"]
            col = parsed_args["column"]
            
            if agg_op == "mean":
                return df_copy[col].mean()
            elif agg_op == "sum":
                return df_copy[col].sum()
            elif agg_op == "min":
                return df_copy[col].min()
            elif agg_op == "max":
                return df_copy[col].max()
            else:
                raise ValueError(f"Unknown aggregation operator: {agg_op}")
                
        elif op == "groupby":
            agg_op = parsed_args["agg_op"]
            val_col = parsed_args["val_column"]
            group_col = parsed_args["group_column"]
            
            grouped = df_copy.groupby(group_col)[val_col]
            if agg_op == "mean":
                res = grouped.mean()
            elif agg_op == "sum":
                res = grouped.sum()
            elif agg_op == "min":
                res = grouped.min()
            elif agg_op == "max":
                res = grouped.max()
            else:
                raise ValueError(f"Unknown aggregation operator: {agg_op}")
                
            return res.reset_index()
            
        elif op == "filter":
            col = parsed_args["column"]
            op_str = parsed_args["operator"]
            val = parsed_args["value"]
            
            if op_str == "==" or op_str == "=":
                return df_copy[df_copy[col] == val]
            elif op_str == "!=":
                return df_copy[df_copy[col] != val]
            elif op_str == ">":
                return df_copy[df_copy[col] > val]
            elif op_str == ">=":
                return df_copy[df_copy[col] >= val]
            elif op_str == "<":
                return df_copy[df_copy[col] < val]
            elif op_str == "<=":
                return df_copy[df_copy[col] <= val]
            else:
                raise ValueError(f"Unsupported filter operator: {op_str}")
            
        else:
            raise ValueError(f"Unknown operation type: {op}")


class CopilotQueryEngine:
    """Main orchestrator for the Copilot Query Engine.
    
    Coordinates intent classification, deterministic evaluation, LLM code generation,
    and response formatting.
    """
    
    @staticmethod
    def process_query(
        df: pd.DataFrame,
        question: str,
        chat_history: list = None,
        persona: str = "general",
        debug_mode: bool = False
    ) -> Dict[str, Any]:
        start_time = time.perf_counter()
        chat_history = chat_history or []
        columns = list(df.columns)
        
        # 1. Intent Classification
        intent, parsed_args = IntentClassifier.classify(question, columns)
        logger.info("Copilot query: '%s' classified as %s", question[:80], intent)
        
        success = False
        result = None
        code = ""
        error_msg = None
        execution_type = "COMPLEX"
        
        # 2. Execution Routing
        if intent == "SIMPLE" and parsed_args:
            execution_type = "DETERMINISTIC"
            try:
                result = DeterministicQueryEngine.execute(df, parsed_args)
                success = True
                code = f"# Deterministic operation: {parsed_args}"
                logger.info("Deterministic execution succeeded.")
            except Exception as exc:
                # Fall back to LLM if deterministic fails to be robust
                logger.warning("Deterministic execution failed, falling back to LLM. Error: %s", exc)
                execution_type = "LLM"
                llm_success, llm_result, llm_code, llm_err = LLMGenerator.generate_and_execute(
                    df, question, chat_history, persona
                )
                success = llm_success
                result = llm_result
                code = llm_code
                error_msg = llm_err
        else:
            execution_type = "LLM"
            # LLM Code Generator
            llm_success, llm_result, llm_code, llm_err = LLMGenerator.generate_and_execute(
                df, question, chat_history, persona
            )
            success = llm_success
            result = llm_result
            code = llm_code
            error_msg = llm_err
            
        execution_time_ms = int((time.perf_counter() - start_time) * 1000)
        
        # 3. Log results
        logger.info(
            "Copilot query execution complete: type=%s, success=%s, duration_ms=%d",
            execution_type, success, execution_time_ms
        )
        
        # 4. Formatting
        return ResponseFormatter.format_result(
            success=success,
            result=result,
            executed_code=code,
            error_msg=error_msg,
            execution_type=execution_type,
            execution_time_ms=execution_time_ms,
            debug_mode=debug_mode
        )
