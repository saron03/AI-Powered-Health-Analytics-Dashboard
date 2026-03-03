from typing import Any, Dict

SUPPORTED_INTENTS = {"trend", "comparison", "aggregation", "ranking", "proportion", "raw_data", "clarification"}
INTENT_MIN_CONFIDENCE = 0.6
INTENT_KEYWORDS = {
    "trend": {
        "trend", "over time", "across years", "timeline", "time series", "from", "to", "between", "increase", "decrease"
    },
    "comparison": {
        "compare", "comparison", "vs", "versus", "across regions", "by region", "difference", "which region"
    },
    "aggregation": {
        "total", "sum", "average", "mean", "aggregate", "overall", "group by", "combined"
    },
    "ranking": {
        "top", "bottom", "highest", "lowest", "rank", "ranking", "most", "least"
    },
    "proportion": {
        "proportion", "percentage", "share", "distribution", "ratio", "composition", "breakdown"
    },
    "raw_data": {
        "table", "raw", "list", "show data", "rows", "records", "table only"
    },
}
ALLOWED_TABLES = {
    "population_stats",
    "disease_statistics",
    "hospital_resources",
    "vaccination_records",
}

SESSION_MEMORY: Dict[str, Dict[str, Any]] = {}