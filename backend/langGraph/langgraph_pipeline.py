from langgraph.graph import END, START, StateGraph
from backend.langGraph.graph_state import HealthGraphState
from backend.langGraph.langgraph_node import (
    node_chart_determinator,
    node_clarification_handler,
    node_logger,
    node_execution_router,
    node_entity_extractor,
    node_explanation_generator,
    node_intent_detector,
    node_memory_resolver,
    node_query_cleaner,
    node_response_formatter,
    node_response_aggregator,
    node_sql_generator,
    node_sql_reflector,
    node_sql_validator,
    node_db_api_caller,
    node_result_processor,
)


def _route_after_query_cleaner(state: HealthGraphState) -> str:
    if state.get("error") or state.get("clarification_needed"):
        return "clarification_handler"
    return "intent_detector"


def _route_after_sql_reflector(state: HealthGraphState) -> str:
    if state.get("error") or state.get("clarification_needed"):
        return "clarification_handler"
    if state.get("retry_sql_generation"):
        return "sql_generator"
    return "sql_validator"


def _route_after_sql_validator(state: HealthGraphState) -> str:
    if state.get("error") or state.get("clarification_needed"):
        return "clarification_handler"
    return "db_api_caller"


def _route_after_db_call(state: HealthGraphState) -> str:
    if state.get("error") or state.get("clarification_needed"):
        return "clarification_handler"
    return "result_processor"


def _route_after_execution_router(state: HealthGraphState) -> str:
    if state.get("error") or state.get("clarification_needed") or state.get("needs_clarification"):
        return "clarification_handler"
    if state.get("run_explanation") and not state.get("explanation_done"):
        return "explanation_generator"
    if state.get("run_chart") and not state.get("chart_done"):
        return "chart_determinator"
    return "response_aggregator"


def _route_after_explanation(state: HealthGraphState) -> str:
    if state.get("error") or state.get("clarification_needed"):
        return "clarification_handler"
    if state.get("run_chart") and not state.get("chart_done"):
        return "chart_determinator"
    return "response_aggregator"


def _route_after_chart(state: HealthGraphState) -> str:
    if state.get("error") or state.get("clarification_needed"):
        return "clarification_handler"
    if state.get("run_explanation") and not state.get("explanation_done"):
        return "explanation_generator"
    return "response_aggregator"


def _build_graph():
    workflow = StateGraph(HealthGraphState)

    workflow.add_node("logger", node_logger)
    workflow.add_node("query_cleaner", node_query_cleaner)
    workflow.add_node("intent_detector", node_intent_detector)
    workflow.add_node("entity_extractor", node_entity_extractor)
    workflow.add_node("memory_resolver", node_memory_resolver)
    workflow.add_node("sql_generator", node_sql_generator)
    workflow.add_node("sql_reflector", node_sql_reflector)
    workflow.add_node("sql_validator", node_sql_validator)
    workflow.add_node("db_api_caller", node_db_api_caller)
    workflow.add_node("result_processor", node_result_processor)
    workflow.add_node("execution_router", node_execution_router)
    workflow.add_node("response_aggregator", node_response_aggregator)
    workflow.add_node("explanation_generator", node_explanation_generator)
    workflow.add_node("chart_determinator", node_chart_determinator)
    workflow.add_node("clarification_handler", node_clarification_handler)
    workflow.add_node("response_formatter", node_response_formatter)

    workflow.add_edge(START, "logger")
    workflow.add_edge("logger", "query_cleaner")
    workflow.add_conditional_edges(
        "query_cleaner",
        _route_after_query_cleaner,
        {
            "intent_detector": "intent_detector",
            "clarification_handler": "clarification_handler",
        },
    )
    workflow.add_edge("intent_detector", "entity_extractor")
    workflow.add_edge("entity_extractor", "memory_resolver")
    workflow.add_edge("memory_resolver", "sql_generator")
    # workflow.add_edge("sql_generator", "sql_reflector")
    workflow.add_conditional_edges(
        "sql_generator",
        _route_after_sql_reflector,
        {
            "sql_validator": "sql_validator",
            "clarification_handler": "clarification_handler",
        },
    )
    workflow.add_conditional_edges(
        "sql_validator",
        _route_after_sql_validator,
        {
            "db_api_caller": "db_api_caller",
            "clarification_handler": "clarification_handler",
        },
    )
    workflow.add_conditional_edges(
        "db_api_caller",
        _route_after_db_call,
        {
            "result_processor": "result_processor",
            "clarification_handler": "clarification_handler",
        },
    )
    workflow.add_edge("result_processor", "execution_router")
    workflow.add_conditional_edges(
        "execution_router",
        _route_after_execution_router,
        {
            "explanation_generator": "explanation_generator",
            "chart_determinator": "chart_determinator",
            "response_aggregator": "response_aggregator",
            "clarification_handler": "clarification_handler",
        },
    )
    workflow.add_conditional_edges(
        "explanation_generator",
        _route_after_explanation,
        {
            "chart_determinator": "chart_determinator",
            "response_aggregator": "response_aggregator",
            "clarification_handler": "clarification_handler",
        },
    )
    workflow.add_conditional_edges(
        "chart_determinator",
        _route_after_chart,
        {
            "explanation_generator": "explanation_generator",
            "response_aggregator": "response_aggregator",
            "clarification_handler": "clarification_handler",
        },
    )
    workflow.add_edge("clarification_handler", "response_formatter")
    workflow.add_edge("response_aggregator", "response_formatter")
    workflow.add_edge("response_formatter", END)

    return workflow.compile()


GRAPH = _build_graph()
