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
    final_answer: Dict[str, Any]
    errors: List[str]
    execution_plan: List[str]
    run_explanation: bool
    run_chart: bool
    explanation_done: bool
    chart_done: bool
    needs_clarification: bool
    sql_retry_count: int
    max_sql_retries: int
    retry_sql_generation: bool
    sql_review_valid: bool
    sql_reflection_feedback: str
    processed_result: Dict[str, Any]
    empty_result: bool
    confidence_scores: Dict[str, float]
    confidence_score: float
    debug_trace: List[Dict[str, Any]]

