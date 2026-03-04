import json
import re

from dotenv import load_dotenv

from backend.langGraph.constants import ALLOWED_TABLES, INTENT_MIN_CONFIDENCE, SESSION_MEMORY, SUPPORTED_INTENTS
from backend.langGraph.graph_state import HealthGraphState
from backend.langGraph.helper import (build_chart_data, 
                                      build_schema_prompt, 
                                      choose_chart_type, 
                                      llm_intent_detector, 
                                      llm_json, 
                                      rule_based_intent_detector)

from ..database import execute_sql_query

load_dotenv()


def node_query_cleaner(state: HealthGraphState) -> HealthGraphState:
    user_query = state.get("user_query", "").strip()
    if not user_query:
        return {"error": "Empty query. Please enter a health analytics question.", "clarification_needed": True}

    system_prompt = (
        "You are a query normalizer for a health analytics system. "
        "Task 1: rewrite the user question into a concise, grammatically clear version without changing meaning. "
        "Task 2: generate a short, descriptive title for this query. "
        "Do not add assumptions, filters, regions, diseases, years, or metrics that are not explicitly present. "
        "Preserve all numbers, year ranges, and named entities exactly. "
        "Return strict JSON only with one key: {\"clean_query\": \"...\", \"title\": \"...\"}."
    )
    parsed = llm_json(system_prompt, user_query)
    clean_query = parsed.get("clean_query") if isinstance(parsed, dict) else None
    title = parsed.get("title") if isinstance(parsed, dict) else None
    if not clean_query:
        clean_query = re.sub(r"\s+", " ", user_query).strip()
    return {"clean_query": clean_query, "title": title}


def node_intent_detector(state: HealthGraphState) -> HealthGraphState:
    if state.get("error"):
        return {}

    clean_query = state.get("clean_query", "")

    # Step 1: Rule-based intent classification (fast path)
    rb_result = rule_based_intent_detector(clean_query)
    rb_intent = rb_result.get("intent", "clarification")
    rb_confidence = float(rb_result.get("confidence", 0.0))

    # Step 2: Fallback to LLM when rule confidence is low or unknown
    if rb_intent in SUPPORTED_INTENTS and rb_intent != "clarification" and rb_confidence >= INTENT_MIN_CONFIDENCE:
        return {
            "intent": rb_intent,
            "memory_context": {
                **state.get("memory_context", {}),
                "intent_source": "rule_based",
                "intent_confidence": rb_confidence,
            },
        }

    llm_intent = llm_intent_detector(clean_query)
    return {
        "intent": llm_intent,
        "memory_context": {
            **state.get("memory_context", {}),
            "intent_source": "llm_fallback",
            "rule_based_intent": rb_intent,
            "rule_based_confidence": rb_confidence,
        },
    }


def node_entity_extractor(state: HealthGraphState) -> HealthGraphState:
    if state.get("error"):
        return {}

    clean_query = state.get("clean_query", "")
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
    parsed = llm_json(system_prompt, clean_query)
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

    return {"entities": entities}


def node_memory_resolver(state: HealthGraphState) -> HealthGraphState:
    if state.get("error"):
        return {}

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

    entities = dict(state.get("entities", {}))
    previous = memory.get("last_entities", {})

    for key in ["disease", "vaccine", "region", "year_start", "year_end", "metric", "gender", "age_group", "output_mode"]:
        if not entities.get(key) and previous.get(key):
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
    }



def node_sql_generator(state: HealthGraphState) -> HealthGraphState:
    if state.get("error"):
        return {}

    clean_query = state.get("clean_query", "")
    intent = state.get("intent", "clarification")
    entities = state.get("entities", {})
    memory_context = state.get("memory_context", {})

    if intent == "clarification":
        return {
            "error": "I need more detail to answer this request.",
            "clarification_needed": True,
            "sql": "",
            "sql_params": [],
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
        f"Memory context: {json.dumps(memory_context)}"
    )
    parsed = llm_json(system_prompt, user_prompt)

    if parsed.get("needs_clarification"):
        question = parsed.get("clarification_question") or "Do you want a specific disease, region, and year range?"
        return {
            "error": question,
            "clarification_needed": True,
            "sql": "",
            "sql_params": [],
        }

    sql = str(parsed.get("sql", "")).strip()
    params = parsed.get("params", [])
    if not isinstance(params, list):
        params = []

    if not sql:
        return {
            "error": "Unable to generate SQL for this request.",
            "clarification_needed": True,
            "sql": "",
            "sql_params": [],
        }

    return {"sql": sql, "sql_params": params}


def node_sql_validator(state: HealthGraphState) -> HealthGraphState:
    if state.get("error"):
        return {}

    sql = state.get("sql", "").strip()
    if not sql:
        return {"error": "Generated SQL is empty.", "clarification_needed": True}

    lowered = sql.lower()
    if not lowered.startswith("select"):
        return {"error": "Only SELECT queries are allowed.", "clarification_needed": True}

    blocked = ["insert ", "update ", "delete ", "drop ", "alter ", "pragma ", "attach ", "detach "]
    if any(token in lowered for token in blocked):
        return {"error": "Unsafe SQL detected. Please rephrase your query.", "clarification_needed": True}

    referenced = re.findall(r"(?:from|join)\s+(\w+)", lowered, flags=re.IGNORECASE)
    for table_name in referenced:
        if table_name not in {t.lower() for t in ALLOWED_TABLES}:
            return {
                "error": f"Disallowed table referenced: {table_name}.",
                "clarification_needed": True,
            }

    text_filter_columns = ["disease_name", "vaccine_name", "region"]
    for column in text_filter_columns:
        sql = re.sub(
            rf"\b{column}\s*=\s*\?",
            f"LOWER({column}) = LOWER(?)",
            sql,
            flags=re.IGNORECASE,
        )

        def _replace_in_clause(match: re.Match) -> str:
            inner = match.group(1)
            if re.fullmatch(r"\s*\?(?:\s*,\s*\?)*\s*", inner or ""):
                placeholders = [part.strip() for part in inner.split(",")]
                lowered_placeholders = ", ".join("LOWER(?)" for _ in placeholders)
                return f"LOWER({column}) IN ({lowered_placeholders})"
            return match.group(0)

        sql = re.sub(
            rf"\b{column}\s+IN\s*\(([^)]*)\)",
            _replace_in_clause,
            sql,
            flags=re.IGNORECASE,
        )

    if "limit" not in lowered:
        sql = f"{sql.rstrip(';')} LIMIT 1000"

    return {"sql": sql}


def node_db_api_caller(state: HealthGraphState) -> HealthGraphState:
    if state.get("error"):
        return {"query_result": [], "columns": []}

    sql = state.get("sql", "")
    params = state.get("sql_params", [])
    safe_params = tuple(p if isinstance(p, (str, int, float, type(None))) else str(p) for p in params)

    result = execute_sql_query(sql, safe_params, readonly=True)
    if result.get("status") != "success":
        return {
            "error": result.get("message", "Database query failed."),
            "query_result": [],
            "columns": [],
        }

    return {
        "query_result": result.get("data", []),
        "columns": result.get("columns", []),
    }

def node_explanation_generator(state: HealthGraphState) -> HealthGraphState:
    if state.get("error"):
        return {"explanation": ""}

    sql = state.get("sql", "")
    clean_query = state.get("clean_query", "")
    intent = state.get("intent", "clarification")
    entities = state.get("entities", {})
    rows = state.get("query_result", [])

    system_prompt = (
        "You are the SQL explanation module for the AI-Powered Health Analytics Dashboard. "
        "Use ONLY the provided intent, entities, SQL, and query results—do not invent values or rely on external knowledge. "
        "Explain in plain language how the SQL addresses the user question, including key filters (disease, region, year/range) and the metric/aggregation used. "
        "Summarize the result set succinctly; if no rows are returned, say that no data was found. "
        "Output strict JSON: {\"explanation\": \"...\"} with no extra keys or formatting."
    )
    user_prompt = (
        f"User query: {clean_query}\n"
        f"Intent: {intent}\n"
        f"Entities: {json.dumps(entities)}\n"
        f"Generated SQL: {sql}\n"
        f"Query Results: {json.dumps(rows)}"
    )
    explanation = llm_json(system_prompt, user_prompt)
    if isinstance(explanation, dict):
        return {"explanation": explanation.get("explanation", "")}
    return {"explanation": str(explanation)}


def node_chart_determinator(state: HealthGraphState) -> HealthGraphState:
    if state.get("error"):
        return {"chart_type": "table", "chart_data": {}}

    intent = state.get("intent", "raw_data")
    entities = state.get("entities", {})
    rows = state.get("query_result", [])
    clean_query = state.get("clean_query", "")

    chart_type = choose_chart_type(intent, entities, rows, clean_query)
    chart_data = build_chart_data(chart_type, rows)
    return {"chart_type": chart_type, "chart_data": chart_data}


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
        "explanation": state.get("explanation", ""),
        "sql": state.get("sql", ""),
        "table": {
            "columns": state.get("columns", []),
            "rows": state.get("query_result", []),
        },
        "chart": {
            "type": state.get("chart_type", "table"),
            "data": state.get("chart_data", {}),
        },
        "clarification_needed": bool(state.get("clarification_needed", False)),
        "error": state.get("error", ""),
    }

    return {"response_payload": payload}

