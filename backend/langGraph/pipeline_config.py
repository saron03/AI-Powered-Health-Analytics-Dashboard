from typing import Dict

DEFAULT_LLM_TIMEOUT_SECONDS = 12
DEFAULT_MAX_SQL_RETRIES = 2

DEFAULT_CONFIDENCE: Dict[str, float] = {
    "query_cleaner_success": 0.92,
    "query_cleaner_error": 0.1,
    "intent_detector_llm": 0.7,
    "intent_detector_clarification": 0.4,
    "entity_extractor": 0.82,
    "memory_resolver": 0.88,
    "sql_generator_success": 0.85,
    "sql_generator_error": 0.2,
    "sql_generator_clarification": 0.25,
    "sql_reflector_success": 0.9,
    "sql_reflector_retry": 0.55,
    "sql_reflector_error": 0.2,
    "sql_validator_success": 0.92,
    "db_api_success": 0.95,
    "db_api_error": 0.1,
    "result_processor_non_empty": 0.93,
    "result_processor_empty": 0.65,
    "result_processor_error": 0.2,
    "explanation_success": 0.9,
    "explanation_fallback": 0.75,
    "explanation_empty": 0.7,
    "chart_success": 0.9,
    "chart_fallback": 0.6,
    "execution_router": 0.9,
    "clarification_handler": 0.3,
}

DEFAULT_MESSAGES: Dict[str, str] = {
    "empty_query": "Empty query. Please enter a health analytics question.",
    "need_more_detail": "I need more detail to answer this request.",
    "sql_generation_failed": "Unable to generate SQL for this request.",
    "sql_retry_exhausted": "Unable to produce valid SQL after retries.",
    "unsafe_sql": "Unsafe SQL detected. Please rephrase your query.",
    "empty_sql": "Generated SQL is empty.",
    "select_only": "Only SELECT queries are allowed.",
    "db_query_failed": "Database query failed.",
    "clarification_needed": "I need more details to proceed.",
    "no_data": "No data found for this request.",
    "no_data_detailed": "No data was found for the requested filters. Try adjusting disease, region, or time range.",
    "partial_answer": "I could not generate a full answer, but partial data may be available.",
    "chart_only_summary": "A chart is available, but text explanation could not be generated.",
}
