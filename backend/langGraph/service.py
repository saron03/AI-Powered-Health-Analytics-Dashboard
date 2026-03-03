from typing import Any, Dict

from backend.langGraph.graph_state import HealthGraphState
from backend.langGraph.langgraph_pipeline import GRAPH


def run_health_langgraph_query(user_query: str, session_id: str = "default") -> Dict[str, Any]:
    initial_state: HealthGraphState = {
        "session_id": session_id,
        "user_query": user_query,
        "clean_query": "",
        "intent": "",
        "entities": {},
        "sql": "",
        "sql_params": [],
        "query_result": [],
        "columns": [],
        "chart_type": "table",
        "chart_data": {},
        "error": "",
        "clarification_needed": False,
        "memory_context": {},
        "response_payload": {},
    }
    final_state = GRAPH.invoke(initial_state)
    return final_state.get("response_payload", {})