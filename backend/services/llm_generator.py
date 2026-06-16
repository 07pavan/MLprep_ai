import logging
import time
import re
import pandas as pd
from typing import Tuple, Any, Optional

from utils.llm_factory import get_llm
from utils.compressor import select_relevant_columns
from tools.pandas_tool import PandasTool
from utils.prompts import ANALYST_PROMPT, ANALYST_FIX_PROMPT, get_persona_context

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
MAX_QUESTION_LENGTH = 2000

def _format_history_block(chat_history: list, n: int = 4) -> str:
    """Format the last N turns into a text block for the prompt."""
    if not chat_history:
        return ""
    recent = chat_history[-n:]
    lines = ["\n--- Conversation history (most recent first) ---"]
    for i, turn in enumerate(reversed(recent), 1):
        q = turn.get("question", "")
        a = str(turn.get("answer", "(no result)"))[:300]
        lines.append(f"Turn {i} — Q: {q}")
        lines.append(f"         A: {a}")
    lines.append("--- End of history ---\n")
    return "\n".join(lines)

def _extract_code(text: str) -> str:
    """Strip markdown fences from LLM response."""
    text = text.strip()
    m = re.findall(r"```python\n(.*?)\n```", text, re.DOTALL)
    if m:
        return m[0].strip()
    m = re.findall(r"```\n(.*?)\n```", text, re.DOTALL)
    if m:
        return m[0].strip()
    return text.strip()

class LLMGenerator:
    """Generates Python code for COMPLEX analytical queries using an LLM.
    
    Includes a self-correction loop up to 3 attempts.
    """
    
    @staticmethod
    def generate_and_execute(
        df: pd.DataFrame,
        question: str,
        chat_history: list = None,
        persona: str = "general"
    ) -> Tuple[bool, Any, str, Optional[str]]:
        """Generates, sanitizes, executes code in sandbox with self-correction.
        
        Returns (success, result, code, error_message).
        """
        chat_history = chat_history or []
        
        # Limit question length
        truncated_question = question[:MAX_QUESTION_LENGTH]
        
        # Select relevant columns (schema compression)
        relevant = select_relevant_columns(df, truncated_question, max_cols=15)
        col_list = ", ".join(relevant)
        dtype_info = ", ".join(f"{c}: {df[c].dtype}" for c in relevant)
        history_block = _format_history_block(chat_history)
        
        llm = get_llm("smart")
        if llm is None:
            # Fallback when LLM is unavailable: return error or simple describe
            return False, None, "", "LLM service is not available (check API keys)"
            
        last_code = ""
        last_error = ""
        
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                persona_context = get_persona_context(persona)
                if attempt == 1:
                    prompt = ANALYST_PROMPT.format(
                        rows=len(df), cols=len(df.columns),
                        col_list=col_list, dtype_info=dtype_info,
                        history_block=history_block, question=truncated_question,
                        persona_context=persona_context,
                    )
                else:
                    logger.warning("Copilot analyst attempt %d/%d — fixing: %s", attempt, MAX_RETRIES, last_error[:100])
                    prompt = ANALYST_FIX_PROMPT.format(
                        question=truncated_question, col_list=col_list,
                        broken_code=last_code, error_msg=last_error,
                        persona_context=persona_context,
                    )
                
                response = llm.invoke(prompt)
                last_code = _extract_code(response.content)
                
                success, result = PandasTool.execute_code(df, last_code)
                if success:
                    return True, result, last_code, None
                else:
                    last_error = str(result)
            except Exception as exc:
                last_error = str(exc)
                logger.warning("Copilot analyst attempt %d exception: %s", attempt, last_error)
                
        return False, None, last_code, f"Failed after {MAX_RETRIES} attempts. Last error: {last_error}"
