import re
from typing import Optional, Tuple, Dict, Any

class IntentClassifier:
    """Classifies user natural language query complexity into SIMPLE or COMPLEX.
    
    SIMPLE queries are parsed into structured configurations for deterministic execution.
    All other queries fall back to COMPLEX (LLM code generation).
    """
    
    @staticmethod
    def classify(query: str, columns: list[str]) -> Tuple[str, Optional[Dict[str, Any]]]:
        """Classify a user query.
        
        Returns a tuple of (intent_type, parsed_args) where:
          - intent_type is either "SIMPLE" or "COMPLEX"
          - parsed_args is a dictionary of query parameters if SIMPLE, else None
        """
        # Clean query: lowercase, strip question marks, and trim spaces
        q = query.strip().lower()
        q = re.sub(r'[?]', '', q)
        
        # Helper to find column matching (case-insensitive)
        def find_column(name: str) -> Optional[str]:
            name_clean = name.strip().replace(" ", "_").lower()
            for col in columns:
                if col.lower() == name_clean or col.lower().replace(" ", "_") == name_clean:
                    return col
            return None

        # Rule 1: Row count
        count_patterns = [
            r"^how many rows$",
            r"^how many records$",
            r"^count rows$",
            r"^count records$",
            r"^total rows$",
            r"^total records$",
            r"^number of rows$",
            r"^row count$",
            r"^count$"
        ]
        if any(re.match(pat, q) for pat in count_patterns):
            return "SIMPLE", {"op": "count"}

        # Rule 2: Groupby aggregations
        # e.g., "average salary by department", "total sales group by region"
        groupby_pat = r"^(average|mean|avg|sum|total|min|minimum|lowest|max|maximum|highest)\s+(?:of\s+)?([a-zA-Z0-9_\s]+)\s+(?:by|group\s+by|grouped\s+by)\s+([a-zA-Z0-9_\s]+)$"
        m = re.match(groupby_pat, q)
        if m:
            op_name, val_col_raw, group_col_raw = m.groups()
            val_col = find_column(val_col_raw)
            group_col = find_column(group_col_raw)
            if val_col and group_col:
                op_map = {
                    "average": "mean", "mean": "mean", "avg": "mean",
                    "sum": "sum", "total": "sum",
                    "min": "min", "minimum": "min", "lowest": "min",
                    "max": "max", "maximum": "max", "highest": "max"
                }
                return "SIMPLE", {
                    "op": "groupby",
                    "agg_op": op_map[op_name],
                    "val_column": val_col,
                    "group_column": group_col
                }

        # Rule 3: Column aggregations (mean, sum, min, max)
        # e.g., "average of age", "sum profit", "maximum salary"
        agg_pat = r"^(average|mean|avg|sum|total|min|minimum|lowest|max|maximum|highest)\s+(?:of\s+)?([a-zA-Z0-9_\s]+)$"
        m = re.match(agg_pat, q)
        if m:
            op_name, col_raw = m.groups()
            col = find_column(col_raw)
            if col:
                op_map = {
                    "average": "mean", "mean": "mean", "avg": "mean",
                    "sum": "sum", "total": "sum",
                    "min": "min", "minimum": "min", "lowest": "min",
                    "max": "max", "maximum": "max", "highest": "max"
                }
                return "SIMPLE", {
                    "op": "aggregation",
                    "agg_op": op_map[op_name],
                    "column": col
                }

        # Rule 4: Filtering
        # e.g. "rows where age > 30", "filter status == active", "age >= 30"
        filter_pat = r"^(?:show|find|get|rows|records|filter)?\s*(?:where|with)?\s*([a-zA-Z0-9_\s]+)\s*([>=<!]+)\s*([a-zA-Z0-9_\s'\"\-]+)$"
        m = re.match(filter_pat, q)
        if m:
            col_raw, op, val_raw = m.groups()
            col = find_column(col_raw)
            if col:
                val = val_raw.strip().strip("'\"")
                # Try casting to numeric if possible
                try:
                    if "." in val:
                        val = float(val)
                    else:
                        val = int(val)
                except ValueError:
                    pass
                return "SIMPLE", {
                    "op": "filter",
                    "column": col,
                    "operator": op,
                    "value": val
                }

        return "COMPLEX", None
