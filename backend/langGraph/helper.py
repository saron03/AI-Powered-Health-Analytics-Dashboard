import json
import re
from typing import Any, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from backend.langGraph.constants import INTENT_KEYWORDS, SUPPORTED_INTENTS
from backend.langGraph.graph_state import HealthGraphState
from backend.langGraph.langgraph_node import SESSION_MEMORY
from backend.langGraph.langgraph_pipeline import GRAPH
from backend.langGraph.llm_provider import get_groq_client

def _get_llm() -> ChatGroq:
    return get_groq_client()


def _extract_json(text: str) -> Dict[str, Any]:
    if not text:
        return {}
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}


def llm_json(system_prompt: str, user_prompt: str) -> Dict[str, Any]:
    llm = _get_llm()
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ])
    return _extract_json(response.content if isinstance(response.content, str) else "")

def rule_based_intent_detector(query: str) -> Dict[str, Any]:
    text = query.lower().strip()
    if not text:
        return {"intent": "clarification", "confidence": 0.0}

    scores: Dict[str, float] = {intent: 0.0 for intent in INTENT_KEYWORDS}
    keyword_hits: Dict[str, int] = {intent: 0 for intent in INTENT_KEYWORDS}

    for intent, keywords in INTENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                keyword_hits[intent] += 1
                if " " in keyword:
                    scores[intent] += 1.5
                else:
                    scores[intent] += 1.0

    if re.search(r"\b(19|20)\d{2}\b", text) and any(token in text for token in ["trend", "from", "to", "between", "over time"]):
        scores["trend"] += 1.2
    if " by " in f" {text} " and any(token in text for token in ["region", "disease", "vaccine", "year"]):
        scores["comparison"] += 1.0

    best_intent = max(scores, key=scores.get)
    best_score = scores[best_intent]
    total_signal = sum(scores.values())

    if total_signal <= 0:
        return {"intent": "clarification", "confidence": 0.0}

    confidence = min(1.0, best_score / (best_score + max(total_signal - best_score, 0.6)))
    if keyword_hits[best_intent] == 0:
        confidence = 0.0

    return {
        "intent": best_intent,
        "confidence": round(confidence, 3),
    }


def llm_intent_detector(query: str) -> str:
    system_prompt = (
        "You are an intent classifier for health analytics questions. "
        "Choose exactly one label from: trend, comparison, aggregation, ranking, proportion, raw_data, clarification. "
        "Use clarification when the request is too vague to safely generate a query. "
        "Return strict JSON only: {\"intent\": \"one_label\"}."
    )
    parsed = llm_json(system_prompt, query)
    intent = str(parsed.get("intent", "clarification")).strip().lower()
    if intent not in SUPPORTED_INTENTS:
        return "clarification"
    return intent



def build_schema_prompt() -> str:
    return (
        "Schema:\n"
        "population_stats(population_id, region, year, total_population, male_population, female_population)\n"
        "disease_statistics(disease_id, disease_name, region, year, total_cases, total_deaths, recovery_rate)\n"
        "hospital_resources(hospital_id, region, year, number_of_hospitals, available_beds, doctors_count, nurses_count)\n"
        "vaccination_records(vaccine_id, vaccine_name, region, year, vaccinated_population, coverage_percentage)\n\n"

        "Output format (STRICT):\n"
        "Return ONLY valid JSON with exactly these keys:\n"
        "{\"sql\": \"...\", \"params\": [], \"needs_clarification\": false, \"clarification_question\": \"\"}\n\n"

        "CRITICAL RULES:\n"
        "1) SQL must be a single read-only SELECT query.\n"
        "2) Use '?' placeholders for EVERY user-provided value.\n"
        "3) The number of '?' in SQL MUST EXACTLY match the length of params.\n"
        "4) params MUST NEVER be empty if SQL contains '?'.\n"
        "5) Extract parameter values directly from the user query (e.g., disease, region, year).\n"
        "6) Preserve correct order of params as they appear in SQL.\n"
        "7) Apply LOWER(column) = LOWER(?) for text filters.\n"
        "8) Use LOWER(region) for region comparisons.\n"
        "9) Do NOT hardcode user values inside SQL.\n"
        "10) Do not invent columns, tables, or values.\n"
        "11) If multiple rows can exist for the same region/year/disease and the user asks for a metric like total_cases or total_deaths, you MUST aggregate using SUM().\n\n"

        "Behavior rules:\n"
        "- Use aggregation (SUM, AVG, etc.) only when needed.\n"
        "- Use GROUP BY for comparisons.\n"
        "- Use ORDER BY + LIMIT for ranking.\n"
        "- Avoid SELECT * unless necessary.\n\n"

        "Clarification:\n"
        "- If required info is missing, set needs_clarification=true and leave sql empty.\n\n"

        "Example:\n"
        "User: Compare cholera deaths in Amhara vs Tigray in 2022\n"
        "Output:\n"
        "{\n"
        "  \"sql\": \"SELECT region, SUM(total_deaths) AS total_deaths FROM disease_statistics WHERE LOWER(disease_name) = LOWER(?) AND LOWER(region) IN (LOWER(?), LOWER(?)) AND year = ? GROUP BY region\",\n"
        "  \"params\": [\"cholera\", \"Amhara\", \"Tigray\", 2022],\n"
        "  \"needs_clarification\": false,\n"
        "  \"clarification_question\": \"\"\n"
        "}"
    )


def choose_chart_type(intent: str, entities: Dict[str, Any], rows: List[Dict[str, Any]], clean_query: str) -> str:
    output_mode = entities.get("output_mode")
    if output_mode == "table_only":
        return "table"

    query_lower = clean_query.lower()
    if "table only" in query_lower:
        return "table"
    if "chart only" in query_lower:
        if intent == "trend":
            return "line"
        if intent == "comparison":
            return "bar"

    if not rows:
        return "table"
    if intent == "trend":
        return "line"
    if intent == "comparison":
        return "bar"
    if intent == "proportion":
        return "pie"
    if intent == "ranking":
        return "bar"
    if intent == "aggregation":
        return "stacked_bar"
    return "table"


def _first_numeric_columns(rows: List[Dict[str, Any]]) -> List[str]:
    if not rows:
        return []
    numeric_columns: List[str] = []
    sample = rows[0]
    for key, value in sample.items():
        if isinstance(value, (int, float)):
            numeric_columns.append(key)
    return numeric_columns


def build_chart_data(chart_type: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    if chart_type == "table" or not rows:
        return {}

    columns = list(rows[0].keys())
    numeric_columns = _first_numeric_columns(rows)
    if not numeric_columns or not columns:
        return {}

    label_column = "year" if "year" in columns else columns[0]
    value_candidates = [column for column in numeric_columns if column != label_column]

    if chart_type in {"line", "bar", "pie"}:
        value_column = value_candidates[0] if value_candidates else numeric_columns[0]
        aggregated: Dict[str, float] = {}
        for row in rows:
            label = str(row.get(label_column, ""))
            value = row.get(value_column, 0)
            numeric_value = float(value) if isinstance(value, (int, float)) else 0.0
            aggregated[label] = aggregated.get(label, 0.0) + numeric_value

        labels = list(aggregated.keys())
        values = list(aggregated.values())

        if all(float(v).is_integer() for v in values):
            values = [int(v) for v in values]

        return {
            "labels": labels,
            "datasets": [
                {
                    "label": value_column,
                    "data": values,
                }
            ],
        }

    if chart_type == "stacked_bar":
        labels = [str(row.get(label_column, "")) for row in rows]
        datasets = []
        stack_columns = value_candidates if value_candidates else numeric_columns
        for column in stack_columns[:4]:
            datasets.append(
                {
                    "label": column,
                    "data": [row.get(column, 0) for row in rows],
                }
            )
        return {
            "labels": labels,
            "datasets": datasets,
        }

    return {}

def reset_session_context(session_id: str) -> Dict[str, Any]:
    SESSION_MEMORY.pop(session_id, None)
    return {
        "status": "success",
        "session_id": session_id,
        "message": "Session context has been reset.",
    }

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