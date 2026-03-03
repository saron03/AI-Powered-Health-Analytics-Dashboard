from typing import Any, Dict
from langgraph.graph import END, START, StateGraph
from backend.langGraph.graph_state import HealthGraphState
from backend.langGraph.langgraph_node import (
    node_chart_determinator,
    node_entity_extractor,
    node_intent_detector,
    node_memory_resolver,
    node_query_cleaner,
    node_response_formatter,
    node_sql_generator,
    node_sql_validator,
    node_db_api_caller,
)


def _build_graph():
    workflow = StateGraph(HealthGraphState)

    workflow.add_node("query_cleaner", node_query_cleaner)
    workflow.add_node("intent_detector", node_intent_detector)
    workflow.add_node("entity_extractor", node_entity_extractor)
    workflow.add_node("memory_resolver", node_memory_resolver)
    workflow.add_node("sql_generator", node_sql_generator)
    workflow.add_node("sql_validator", node_sql_validator)
    workflow.add_node("db_api_caller", node_db_api_caller)
    workflow.add_node("chart_determinator", node_chart_determinator)
    workflow.add_node("response_formatter", node_response_formatter)

    workflow.add_edge(START, "query_cleaner")
    workflow.add_edge("query_cleaner", "intent_detector")
    workflow.add_edge("intent_detector", "entity_extractor")
    workflow.add_edge("entity_extractor", "memory_resolver")
    workflow.add_edge("memory_resolver", "sql_generator")
    workflow.add_edge("sql_generator", "sql_validator")
    workflow.add_edge("sql_validator", "db_api_caller")
    workflow.add_edge("db_api_caller", "chart_determinator")
    workflow.add_edge("chart_determinator", "response_formatter")
    workflow.add_edge("response_formatter", END)

    return workflow.compile()


GRAPH = _build_graph()

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