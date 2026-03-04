from typing import Any, Dict, List, TypedDict

class HealthGraphState(TypedDict, total=False):
    session_id: str
    user_query: str
    clean_query: str
    title: str
    intent: str
    entities: Dict[str, Any]
    sql: str
    sql_params: List[Any]
    query_result: List[Dict[str, Any]]
    columns: List[str]
    chart_type: str
    chart_data: Dict[str, Any]
    explanation: str
    error: str
    clarification_needed: bool
    memory_context: Dict[str, Any]
    response_payload: Dict[str, Any]

