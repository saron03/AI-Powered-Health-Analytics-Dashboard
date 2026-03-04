import re
from typing import Dict, List, Optional


AGGREGATE_PATTERN = re.compile(r"\b(count|sum|avg|min|max)\s*\(", re.IGNORECASE)


def validate_sql_semantics(sql: str) -> Optional[str]:
    select_match = re.search(r"select\s+(.*?)\s+from\s", sql, flags=re.IGNORECASE | re.DOTALL)
    select_clause = select_match.group(1) if select_match else ""
    select_parts = [part.strip() for part in select_clause.split(",") if part.strip()]

    group_by_match = re.search(
        r"group\s+by\s+(.*?)(?:\s+having|\s+order\s+by|\s+limit|$)",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    group_cols: List[str] = []
    if group_by_match:
        group_cols = [col.strip().lower() for col in group_by_match.group(1).split(",") if col.strip()]

    has_aggregate = any(AGGREGATE_PATTERN.search(part) for part in select_parts)

    non_agg_columns: List[str] = []
    for part in select_parts:
        cleaned = re.sub(r"\s+as\s+\w+$", "", part, flags=re.IGNORECASE).strip()
        if AGGREGATE_PATTERN.search(cleaned):
            continue
        if cleaned == "*":
            continue
        non_agg_columns.append(cleaned.lower())

    if has_aggregate and non_agg_columns and not group_cols:
        return "Invalid aggregation: non-aggregated columns require GROUP BY."

    if has_aggregate and group_cols:
        missing_group_by = []
        for col in non_agg_columns:
            normalized_col = col.split(".")[-1]
            if not any(normalized_col == group_col.split(".")[-1] for group_col in group_cols):
                missing_group_by.append(col)
        if missing_group_by:
            return "Invalid GROUP BY: selected non-aggregated columns are missing in GROUP BY."

    return None


def normalize_text_filters(sql: str, text_filter_columns: List[str]) -> str:
    updated_sql = sql
    for column in text_filter_columns:
        updated_sql = re.sub(
            rf"\b{column}\s*=\s*\?",
            f"LOWER({column}) = LOWER(?)",
            updated_sql,
            flags=re.IGNORECASE,
        )

        def _replace_in_clause(match: re.Match) -> str:
            inner = match.group(1)
            if re.fullmatch(r"\s*\?(?:\s*,\s*\?)*\s*", inner or ""):
                placeholders = [part.strip() for part in inner.split(",")]
                lowered_placeholders = ", ".join("LOWER(?)" for _ in placeholders)
                return f"LOWER({column}) IN ({lowered_placeholders})"
            return match.group(0)

        updated_sql = re.sub(
            rf"\b{column}\s+IN\s*\(([^)]*)\)",
            _replace_in_clause,
            updated_sql,
            flags=re.IGNORECASE,
        )

    return updated_sql
