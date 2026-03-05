import json
import re
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv

from backend.langGraph.constants import INTENT_MIN_CONFIDENCE, SESSION_MEMORY, SUPPORTED_INTENTS
from backend.langGraph.graph_state import HealthGraphState
from backend.langGraph.llm_adapter import safe_llm_json
from backend.langGraph.pipeline_config import DEFAULT_CONFIDENCE, DEFAULT_MAX_SQL_RETRIES, DEFAULT_MESSAGES
from backend.langGraph.sql_validation import normalize_text_filters, validate_sql_semantics
from backend.langGraph.helper import (build_chart_data, 
                                      build_schema_prompt, 
                                      choose_chart_type, 
                                      llm_intent_detector, 
                                      rule_based_intent_detector)

from ..database import execute_sql_query, get_dynamic_allowed_tables

load_dotenv()


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _normalize_errors(state: HealthGraphState) -> List[str]:
    errors = _as_list(state.get("errors"))
    error_text = state.get("error")
    if isinstance(error_text, str) and error_text.strip() and error_text not in errors:
        errors.append(error_text)
    return errors


def _with_error(state: HealthGraphState, message: str, clarification_needed: bool = True) -> HealthGraphState:
    errors = _normalize_errors(state)
    if message and message not in errors:
        errors.append(message)
    return {
        "error": message,
        "errors": errors,
        "clarification_needed": clarification_needed,
    }


def _ensure_confidence(state: HealthGraphState) -> Tuple[Dict[str, float], float]:
    confidence_scores = _as_dict(state.get("confidence_scores"))
    base_confidence = float(state.get("confidence_score", DEFAULT_CONFIDENCE["intent_detector_llm"]) or DEFAULT_CONFIDENCE["intent_detector_llm"])
    return confidence_scores, base_confidence


def _update_confidence(state: HealthGraphState, key: str, score: float) -> HealthGraphState:
    confidence_scores, _ = _ensure_confidence(state)
    bounded = max(0.0, min(1.0, float(score)))
    confidence_scores[key] = bounded
    aggregate = sum(confidence_scores.values()) / len(confidence_scores) if confidence_scores else bounded
    return {"confidence_scores": confidence_scores, "confidence_score": round(aggregate, 3)}


def _merge_errors(state: HealthGraphState, message: str) -> Dict[str, List[str]]:
    existing = _normalize_errors(state)
    if message:
        existing.append(message)
    return {"errors": existing}


def node_logger(state: HealthGraphState) -> HealthGraphState:
    trace = _as_list(state.get("debug_trace"))
    trace.append(
        {
            "intent": state.get("intent"),
            "clarification_needed": bool(state.get("clarification_needed") or state.get("needs_clarification")),
            "has_error": bool(state.get("error")),
            "sql_retry_count": int(state.get("sql_retry_count", 0) or 0),
            "execution_plan": _as_list(state.get("execution_plan")),
            "confidence_score": float(state.get("confidence_score", 0.0) or 0.0),
        }
    )
    return {"debug_trace": trace}


def node_execution_router(state: HealthGraphState) -> HealthGraphState:
    """Decide which branches to run after retrieval based on intent and results."""
    rows = _as_list(state.get("query_result"))
    intent = str(state.get("intent", "")).lower()
    needs_clarification = bool(state.get("needs_clarification") or state.get("clarification_needed"))

    if needs_clarification:
        return {
            "execution_plan": [],
            "needs_clarification": True,
            **_merge_errors(state, state.get("error", "Clarification needed")),
        }

    if state.get("error"):
        return {
            "execution_plan": [],
            "needs_clarification": True,
            **_merge_errors(state, state.get("error", "Pipeline error")),
        }

    plan: List[str]
    if not rows:
        plan = ["explanation"]
    elif intent == "visualization":
        plan = ["chart", "explanation"]
    elif intent == "analysis":
        plan = ["explanation"]
    elif len(rows) > 1:
        plan = ["chart", "explanation"]
    else:
        plan = ["explanation"]

    run_explanation = "explanation" in plan
    run_chart = "chart" in plan

    return {
        "execution_plan": plan,
        "needs_clarification": False,
        "run_explanation": run_explanation,
        "run_chart": run_chart,
        "explanation_done": False,
        "chart_done": False,
        "errors": _normalize_errors(state),
        **_update_confidence(state, "execution_router", DEFAULT_CONFIDENCE["execution_router"]),
    }


def node_query_cleaner(state: HealthGraphState) -> HealthGraphState:
    user_query = str(state.get("user_query", "") or "").strip()
    if not user_query:
        return {
            **_with_error(state, DEFAULT_MESSAGES["empty_query"], clarification_needed=True),
            **_update_confidence(state, "query_cleaner", DEFAULT_CONFIDENCE["query_cleaner_error"]),
        }

    system_prompt = (
        "You are a query normalizer for a health analytics system. "
        "Task 1: rewrite the user question into a concise, grammatically clear version without changing meaning. "
        "Task 2: generate a short, descriptive title for this query. "
        "Do not add assumptions, filters, regions, diseases, years, or metrics that are not explicitly present. "
        "Preserve all numbers, year ranges, and named entities exactly. "
        "Return strict JSON only with one key: {\"clean_query\": \"...\", \"title\": \"...\"}."
    )
    parsed = safe_llm_json(system_prompt, user_query, {"clean_query": user_query, "title": "Health Query"})
    clean_query = parsed.get("clean_query") if isinstance(parsed, dict) else None
    title = parsed.get("title") if isinstance(parsed, dict) else None
    if not clean_query:
        clean_query = re.sub(r"\s+", " ", user_query).strip()
    return {
        "clean_query": clean_query,
        "title": title,
        "errors": _normalize_errors(state),
        **_update_confidence(state, "query_cleaner", DEFAULT_CONFIDENCE["query_cleaner_success"]),
    }


def node_intent_detector(state: HealthGraphState) -> HealthGraphState:
    if state.get("error"):
        return {"errors": _normalize_errors(state)}

    clean_query = str(state.get("clean_query", "") or "")

    # Step 1: Rule-based intent classification (fast path)
    rb_result = rule_based_intent_detector(clean_query)
    rb_intent = rb_result.get("intent", "clarification")
    rb_confidence = float(rb_result.get("confidence", 0.0))

    # Step 2: Fallback to LLM when rule confidence is low or unknown
    if rb_intent in SUPPORTED_INTENTS and rb_intent != "clarification" and rb_confidence >= INTENT_MIN_CONFIDENCE:
        return {
            "intent": rb_intent,
            "memory_context": {
                **_as_dict(state.get("memory_context")),
                "intent_source": "rule_based",
                "intent_confidence": rb_confidence,
            },
            **_update_confidence(state, "intent_detector", rb_confidence),
        }

    llm_fallback = safe_llm_json(
        (
            "You classify intents for health analytics queries. "
            "Return strict JSON with one key: {\"intent\": \"trend|comparison|aggregation|ranking|proportion|raw_data|clarification\"}."
        ),
        clean_query,
        {"intent": "clarification"},
    )
    llm_intent = str(llm_fallback.get("intent", "clarification")).strip().lower()
    if llm_intent not in SUPPORTED_INTENTS:
        llm_intent = llm_intent_detector(clean_query)
    return {
        "intent": llm_intent,
        "memory_context": {
            **_as_dict(state.get("memory_context")),
            "intent_source": "llm_fallback",
            "rule_based_intent": rb_intent,
            "rule_based_confidence": rb_confidence,
        },
        **_update_confidence(
            state,
            "intent_detector",
            DEFAULT_CONFIDENCE["intent_detector_llm"]
            if llm_intent != "clarification"
            else DEFAULT_CONFIDENCE["intent_detector_clarification"],
        ),
    }


def node_entity_extractor(state: HealthGraphState) -> HealthGraphState:
    if state.get("error"):
        return {"errors": _normalize_errors(state)}

    clean_query = str(state.get("clean_query", "") or "")
    system_prompt = (
        "Extract query entities for a health analytics database pipeline. "
        "Return strict JSON only with exactly these keys: "
        "disease, vaccine, region, year_start, year_end, year_exact, metric, gender, age_group, output_mode. "
        "Rules: "
        "1) Use null for unknown values. "
        "2) year_start/year_end/year_exact must be integers when present. "
        "3) output_mode must be one of chart_only, table_only, both (default both). "
        "4) metric should be one of total_cases, total_deaths, recovery_rate, total_population, male_population, female_population, number_of_hospitals, available_beds, doctors_count, nurses_count, vaccinated_population, coverage_percentage when inferable; otherwise null. "
        "5) Do not invent values not grounded in the user query."
    )
    parsed = safe_llm_json(system_prompt, clean_query, {})
    entities = {
        "disease": parsed.get("disease"),
        "vaccine": parsed.get("vaccine"),
        "region": parsed.get("region"),
        "year_start": parsed.get("year_start"),
        "year_end": parsed.get("year_end"),
        "year_exact": parsed.get("year_exact"),
        "metric": parsed.get("metric"),
        "gender": parsed.get("gender"),
        "age_group": parsed.get("age_group"),
        "output_mode": parsed.get("output_mode") or "both",
    }

    if entities["year_exact"] and (not entities["year_start"] and not entities["year_end"]):
        entities["year_start"] = entities["year_exact"]
        entities["year_end"] = entities["year_exact"]

    if entities["output_mode"] not in {"chart_only", "table_only", "both"}:
        entities["output_mode"] = "both"

    return {
        "entities": entities,
        **_update_confidence(state, "entity_extractor", DEFAULT_CONFIDENCE["entity_extractor"]),
    }


def node_memory_resolver(state: HealthGraphState) -> HealthGraphState:
    if state.get("error"):
        return {"errors": _normalize_errors(state)}

    session_id = state.get("session_id") or "default"
    memory = SESSION_MEMORY.setdefault(
        session_id,
        {
            "last_entities": {},
            "query_history": [],
            "last_chart_type": None,
            "last_sql": None,
            "last_user_query": None,
        },
    )

    entities = dict(_as_dict(state.get("entities")))
    previous = _as_dict(memory.get("last_entities"))

    for key in ["disease", "vaccine", "region", "year_start", "year_end", "metric", "gender", "age_group", "output_mode"]:
        extracted = entities.get(key)
        if (key not in entities or extracted is None or extracted == "") and previous.get(key) is not None:
            entities[key] = previous[key]

    query_history = memory.get("query_history", [])[-9:]
    query_history.append(state.get("clean_query", ""))
    memory["query_history"] = query_history

    return {
        "entities": entities,
        "memory_context": {
            "last_entities": previous,
            "query_history": query_history,
            "last_user_query": memory.get("last_user_query"),
        },
        **_update_confidence(state, "memory_resolver", DEFAULT_CONFIDENCE["memory_resolver"]),
    }



def node_sql_generator(state: HealthGraphState) -> HealthGraphState:
    if state.get("error"):
        return {"errors": _normalize_errors(state)}

    clean_query = str(state.get("clean_query", "") or "")
    intent = str(state.get("intent", "clarification") or "clarification")
    entities = _as_dict(state.get("entities"))
    memory_context = _as_dict(state.get("memory_context"))
    retry_count = int(state.get("sql_retry_count", 0) or 0)
    reflection_feedback = str(state.get("sql_reflection_feedback", "") or "")

    if intent == "clarification":
        return {
            **_with_error(state, DEFAULT_MESSAGES["need_more_detail"], clarification_needed=True),
            "sql": "",
            "sql_params": [],
            **_update_confidence(state, "sql_generator", DEFAULT_CONFIDENCE["sql_generator_error"]),
        }

    system_prompt = (
        "You are a senior SQLite SQL generator for health analytics. "
        "Generate only safe, executable SELECT statements that follow the provided schema and rules. "
        "Never produce markdown or explanations."
    )
    user_prompt = (
        f"{build_schema_prompt()}\n\n"
        f"User query: {clean_query}\n"
        f"Intent: {intent}\n"
        f"Entities: {json.dumps(entities)}\n"
        f"Memory context: {json.dumps(memory_context)}\n"
        f"SQL retry count: {retry_count}\n"
        f"Reflection feedback: {reflection_feedback}"
    )
    parsed = safe_llm_json(
        system_prompt,
        user_prompt,
        {
            "sql": "",
            "params": [],
            "clarification_needed": True,
            "clarification_question": "Please paraphrase your query with more specific details.",
        },
    )

    if parsed.get("clarification_needed"):
        question = parsed.get("clarification_question") or "Do you want a specific disease, region, and year range?"
        return {
            **_with_error(state, question, clarification_needed=True),
            "sql": "",
            "sql_params": [],
            **_update_confidence(state, "sql_generator", DEFAULT_CONFIDENCE["sql_generator_clarification"]),
        }

    sql = str(parsed.get("sql", "")).strip()
    params = parsed.get("params", [])
    if not isinstance(params, list):
        params = []

    if not sql:
        return {
            **_with_error(state, DEFAULT_MESSAGES["sql_generation_failed"], clarification_needed=True),
            "sql": "",
            "sql_params": [],
            **_update_confidence(state, "sql_generator", DEFAULT_CONFIDENCE["sql_generator_error"]),
        }

    return {
        "sql": sql,
        "sql_params": params,
        "sql_retry_count": retry_count,
        "retry_sql_generation": False,
        **_update_confidence(state, "sql_generator", DEFAULT_CONFIDENCE["sql_generator_success"]),
    }

def node_sql_reflector(state: HealthGraphState):
    if state.get("error"):
        return {"errors": _normalize_errors(state)}

    sql = str(state.get("sql", "") or "")
    query = str(state.get("clean_query", "") or "")
    retry_count = int(state.get("sql_retry_count", 0) or 0)
    max_retries = int(state.get("max_sql_retries", DEFAULT_MAX_SQL_RETRIES) or DEFAULT_MAX_SQL_RETRIES)

    system_prompt = """
    You are a strict SQL reviewer.
    Check if the SQL correctly answers the query.
    If wrong → suggest corrected SQL.
    Return JSON:
    {
        "valid": true/false,
        "corrected_sql": "...",
        "reason": "..."
    }
    """

    result = safe_llm_json(
        system_prompt,
        f"Query: {query}\nSQL: {sql}",
        {"valid": True, "corrected_sql": sql, "reason": "reflection_timeout_fallback"},
    )

    if not bool(result.get("valid", False)):
        corrected_sql = str(result.get("corrected_sql", sql) or sql)
        reason = str(result.get("reason", "SQL needs adjustment") or "SQL needs adjustment")
        new_retry = retry_count + 1
        if new_retry > max_retries:
            return {
                **_with_error(state, DEFAULT_MESSAGES["sql_retry_exhausted"], clarification_needed=True),
                "sql": corrected_sql,
                "sql_review_valid": False,
                "retry_sql_generation": False,
                "sql_reflection_feedback": reason,
                "sql_retry_count": new_retry,
                **_update_confidence(state, "sql_reflector", DEFAULT_CONFIDENCE["sql_reflector_error"]),
            }
        return {
            "sql": corrected_sql,
            "sql_review_valid": False,
            "retry_sql_generation": True,
            "sql_reflection_feedback": reason,
            "sql_retry_count": new_retry,
            "errors": _normalize_errors(state),
            **_update_confidence(state, "sql_reflector", DEFAULT_CONFIDENCE["sql_reflector_retry"]),
        }

    return {
        "sql_review_valid": True,
        "retry_sql_generation": False,
        "sql_reflection_feedback": "",
        "errors": _normalize_errors(state),
        **_update_confidence(state, "sql_reflector", DEFAULT_CONFIDENCE["sql_reflector_success"]),
    }

def node_sql_validator(state: HealthGraphState) -> HealthGraphState:
    if state.get("error"):
        return {"errors": _normalize_errors(state)}

    sql = str(state.get("sql", "") or "").strip()
    if not sql:
        return _with_error(state, DEFAULT_MESSAGES["empty_sql"], clarification_needed=True)

    lowered = sql.lower()
    if not lowered.startswith("select"):
        return _with_error(state, DEFAULT_MESSAGES["select_only"], clarification_needed=True)

    blocked = ["insert ", "update ", "delete ", "drop ", "alter ", "pragma ", "attach ", "detach "]
    if any(token in lowered for token in blocked):
        return _with_error(state, DEFAULT_MESSAGES["unsafe_sql"], clarification_needed=True)

    dynamic_allowed_tables = get_dynamic_allowed_tables()
    referenced = re.findall(r"(?:from|join)\s+(\w+)", lowered, flags=re.IGNORECASE)
    for table_name in referenced:
        if table_name not in dynamic_allowed_tables:
            return _with_error(state, f"Disallowed table referenced: {table_name}.", clarification_needed=True)

    semantic_error = validate_sql_semantics(sql)
    if semantic_error:
        return _with_error(state, semantic_error, clarification_needed=True)

    sql = normalize_text_filters(sql, ["disease_name", "vaccine_name", "region"])

    if "limit" not in lowered:
        sql = f"{sql.rstrip(';')} LIMIT 1000"

    return {
        "sql": sql,
        "errors": _normalize_errors(state),
        **_update_confidence(state, "sql_validator", DEFAULT_CONFIDENCE["sql_validator_success"]),
    }


def node_db_api_caller(state: HealthGraphState) -> HealthGraphState:
    if state.get("error"):
        return {"query_result": [], "columns": [], "errors": _normalize_errors(state)}

    sql = str(state.get("sql", "") or "")
    params = _as_list(state.get("sql_params"))
    safe_params = tuple(p if isinstance(p, (str, int, float, type(None))) else str(p) for p in params)

    result = execute_sql_query(sql, safe_params, readonly=True)
    if result.get("status") != "success":
        return {
            **_with_error(state, result.get("message", DEFAULT_MESSAGES["db_query_failed"]), clarification_needed=True),
            "query_result": [],
            "columns": [],
            **_update_confidence(state, "db_api_caller", DEFAULT_CONFIDENCE["db_api_error"]),
        }

    return {
        "query_result": _as_list(result.get("data")),
        "columns": _as_list(result.get("columns")),
        "errors": _normalize_errors(state),
        **_update_confidence(state, "db_api_caller", DEFAULT_CONFIDENCE["db_api_success"]),
    }


def node_result_processor(state: HealthGraphState) -> HealthGraphState:
    rows = _as_list(state.get("query_result"))
    columns = _as_list(state.get("columns"))
    if state.get("error"):
        return {
            "processed_result": {"row_count": 0, "is_empty": True, "columns": columns},
            "empty_result": True,
            "errors": _normalize_errors(state),
            **_update_confidence(state, "result_processor", DEFAULT_CONFIDENCE["result_processor_error"]),
        }

    is_empty = len(rows) == 0
    return {
        "processed_result": {
            "row_count": len(rows),
            "is_empty": is_empty,
            "columns": columns,
        },
        "empty_result": is_empty,
        "errors": _normalize_errors(state),
        **_update_confidence(
            state,
            "result_processor",
            DEFAULT_CONFIDENCE["result_processor_non_empty"] if not is_empty else DEFAULT_CONFIDENCE["result_processor_empty"],
        ),
    }

def node_explanation_generator(state: HealthGraphState) -> HealthGraphState:
    if state.get("error"):
        return {"explanation": "", "explanation_done": True, "errors": _normalize_errors(state)}

    sql = str(state.get("sql", "") or "")
    clean_query = str(state.get("clean_query", "") or "")
    intent = str(state.get("intent", "clarification") or "clarification")
    entities = _as_dict(state.get("entities"))
    rows = _as_list(state.get("query_result"))

    if not rows:
        return {
            "explanation": DEFAULT_MESSAGES["no_data_detailed"],
            "explanation_done": True,
            **_update_confidence(state, "explanation_generator", DEFAULT_CONFIDENCE["explanation_empty"]),
        }

    system_prompt = (
                    "You are an AI Health Data Analyst explaining analytics results to non-technical users "
                    "such as public health officers, hospital administrators, and policy makers.\n\n"

                    "Your goal is to convert database query results into clear, useful insights written in "
                    "simple natural language.\n\n"

                    "IMPORTANT RULES:\n"
                    "1. Do NOT explain SQL, databases, or technical implementation.\n"
                    "2. Focus only on the meaning of the results.\n"
                    "3. Use clear and simple language suitable for non-technical users.\n"
                    "4. Mention important numbers, regions, diseases, or years when relevant.\n"
                    "5. Use ONLY the provided data. Do NOT invent values.\n"
                    "6. Keep the explanation concise (2–4 sentences).\n"
                    "7. If no data is returned, politely explain that no records were found.\n\n"

                    "ADAPT THE EXPLANATION BASED ON QUERY INTENT:\n"
                    "- ranking → highlight the highest or lowest values.\n"
                    "- comparison → describe the differences between groups.\n"
                    "- trend → describe increases or decreases over time.\n"
                    "- aggregation → summarize totals or averages.\n"
                    "- raw_data → briefly describe what the table represents.\n\n"

                    "INSIGHT STRUCTURE:\n"
                    "1. First sentence: directly answer the user's question.\n"
                    "2. Second sentence: highlight the most important values or comparisons.\n"
                    "3. Third sentence (optional): provide an additional insight or observation.\n\n"

                    "Return STRICT JSON only:\n"
                    "{\"explanation\": \"...\"}"
                )
    user_prompt = (
        f"User query: {clean_query}\n"
        f"Intent: {intent}\n"
        f"Entities: {json.dumps(entities)}\n"
        f"Generated SQL: {sql}\n"
        f"Query Results: {json.dumps(rows)}"
    )
    explanation = safe_llm_json(system_prompt, user_prompt, {"explanation": "I could not generate a detailed explanation, but the query executed successfully."})
    if isinstance(explanation, dict):
        return {
            "explanation": explanation.get("explanation", ""),
            "explanation_done": True,
            **_update_confidence(state, "explanation_generator", DEFAULT_CONFIDENCE["explanation_success"]),
        }
    return {
        "explanation": str(explanation),
        "explanation_done": True,
        **_update_confidence(state, "explanation_generator", DEFAULT_CONFIDENCE["explanation_fallback"]),
    }


def node_chart_determinator(state: HealthGraphState) -> HealthGraphState:
    if state.get("clarification_needed"):
        return {"chart_type": "table", "chart_data": {}, "chart_done": True}

    execution_plan = state.get("execution_plan") or ["explanation"]
    if "chart" not in execution_plan:
        return {"chart_type": "table", "chart_data": {}, "chart_done": True}

    if state.get("error"):
        return {"chart_type": "table", "chart_data": {}, "chart_done": True, "errors": _normalize_errors(state)}

    intent = str(state.get("intent", "raw_data") or "raw_data")
    entities = _as_dict(state.get("entities"))
    rows = _as_list(state.get("query_result"))
    clean_query = str(state.get("clean_query", "") or "")

    chart_type = choose_chart_type(intent, entities, rows, clean_query)
    chart_data = build_chart_data(chart_type, rows)
    score = DEFAULT_CONFIDENCE["chart_success"] if chart_data else DEFAULT_CONFIDENCE["chart_fallback"]
    return {
        "chart_type": chart_type,
        "chart_data": chart_data,
        "chart_done": True,
        **_update_confidence(state, "chart_determinator", score),
    }


def node_response_aggregator(state: HealthGraphState) -> HealthGraphState:
    needs_clarification = bool(state.get("clarification_needed"))
    execution_plan = _as_list(state.get("execution_plan"))

    errors = _normalize_errors(state)

    explanation_text = str(state.get("explanation") or "")
    chart_output = {
        "type": state.get("chart_type"),
        "data": _as_dict(state.get("chart_data")),
    }

    has_chart = bool(chart_output.get("data")) and ("chart" in execution_plan if execution_plan else True)
    has_explanation = bool(explanation_text.strip())
    has_rows = len(_as_list(state.get("query_result"))) > 0
    confidence_score = float(state.get("confidence_score", 0.0) or 0.0)

    if "explanation" in execution_plan and not has_explanation:
        if "explanation_unavailable" not in errors:
            errors.append("explanation_unavailable")
    if "chart" in execution_plan and not has_chart:
        if "chart_unavailable" not in errors:
            errors.append("chart_unavailable")

    if needs_clarification:
        summary = state.get("error") or DEFAULT_MESSAGES["clarification_needed"]
        final_answer = {
            "summary": summary,
            "has_chart": False,
            "chart": None,
            "confidence": "low",
            "confidence_score": round(min(confidence_score, 0.35), 3),
            "has_explanation": bool(summary),
            "partial": True,
        }
        return {"final_answer": final_answer, "errors": errors}

    if not has_rows:
        summary = explanation_text if has_explanation else DEFAULT_MESSAGES["no_data"]
        final_answer = {
            "summary": summary,
            "has_chart": has_chart,
            "chart": chart_output if has_chart else None,
            "confidence": "low" if errors else "medium",
            "confidence_score": round(min(confidence_score, 0.65), 3),
            "has_explanation": bool(summary),
            "partial": True,
        }
        return {"final_answer": final_answer, "errors": errors}

    if has_explanation or has_chart:
        confidence = "medium" if errors else "high"
        summary = explanation_text if has_explanation else DEFAULT_MESSAGES["chart_only_summary"]
        final_answer = {
            "summary": summary,
            "has_chart": has_chart,
            "chart": chart_output if has_chart else None,
            "confidence": confidence,
            "confidence_score": round(confidence_score, 3),
            "has_explanation": has_explanation,
            "partial": not (has_explanation and has_chart),
        }
        return {"final_answer": final_answer, "errors": errors}

    fallback_summary = "No data available for this request."
    if errors:
        fallback_summary = DEFAULT_MESSAGES["partial_answer"]
    final_answer = {
        "summary": fallback_summary,
        "has_chart": False,
        "chart": None,
        "confidence": "low",
        "confidence_score": round(min(confidence_score, 0.4), 3),
        "has_explanation": False,
        "partial": False,
    }
    return {"final_answer": final_answer, "errors": errors}


def node_clarification_handler(state: HealthGraphState) -> HealthGraphState:
    errors = _normalize_errors(state)
    message = state.get("error") or DEFAULT_MESSAGES["clarification_needed"]
    final_answer = {
        "summary": message,
        "has_chart": False,
        "chart": None,
        "confidence": "low",
        "confidence_score": round(min(float(state.get("confidence_score", 0.3) or 0.3), 0.35), 3),
        "has_explanation": True,
        "partial": True,
    }
    return {
        "clarification_needed": True,
        "errors": errors,
        "final_answer": final_answer,
        **_update_confidence(state, "clarification_handler", DEFAULT_CONFIDENCE["clarification_handler"]),
    }
    

def node_response_formatter(state: HealthGraphState) -> HealthGraphState:
    session_id = state.get("session_id") or "default"
    memory = SESSION_MEMORY.setdefault(session_id, {"last_entities": {}, "query_history": []})

    if not state.get("error"):
        memory["last_entities"] = state.get("entities", {})
        memory["last_chart_type"] = state.get("chart_type")
        memory["last_sql"] = state.get("sql")
        memory["last_user_query"] = state.get("clean_query")

    payload = {
        "session_id": session_id,
        "title": state.get("title"),
        "explanation": state.get("final_answer", {}).get("summary", ""),
        "sql": state.get("sql", ""),
        "table": {
            "columns": state.get("columns", []),
            "rows": state.get("query_result", []),
        },
        "chart":state.get("final_answer", {}).get("chart"),
        "clarification_needed": bool(state.get("clarification_needed", False)),
        "error": state.get("error", ""),
        "errors": _normalize_errors(state),
        "confidence_score": state.get("final_answer", {}).get("confidence_score", state.get("confidence_score", 0.0)),
    }

    return {"response_payload": payload}

