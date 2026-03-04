import json
import re
from typing import Any, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from backend.langGraph.constants import INTENT_KEYWORDS, SUPPORTED_INTENTS
from backend.langGraph.constants import SESSION_MEMORY
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
        "You classify intents for the AI-Powered Health Analytics Dashboard. "
        "Choose exactly one label from: trend (over time), comparison (across regions/diseases/time slices), aggregation (single number summary), ranking (top/bottom ordering), proportion (share/percentage), raw_data (explicit table/raw rows), clarification (insufficient detail). "
        "Use clarification when disease/region/time range is missing, the metric is unclear, the user relies on unstated context (e.g., 'same as before'), or the request is too vague to safely generate SQL. "
        "Output strict JSON only: {\"intent\": \"one_label\"}."
    )
    parsed = llm_json(system_prompt, query)
    intent = str(parsed.get("intent", "clarification")).strip().lower()
    if intent not in SUPPORTED_INTENTS:
        return "clarification"
    return intent



def build_schema_prompt() -> str:
    return (
        "AI-Powered Health Analytics Dashboard SQL generator.\n\n"
        "Schema (4 tables):\n"
        "population_stats(population_id, region, year, total_population, male_population, female_population)\n"
        "disease_statistics(disease_id, disease_name, region, year, total_cases, total_deaths, recovery_rate)\n"
        "hospital_resources(hospital_id, region, year, number_of_hospitals, available_beds, doctors_count, nurses_count)\n"
        "vaccination_records(vaccine_id, vaccine_name, region, year, vaccinated_population, coverage_percentage)\n\n"

        "Capabilities and filters: support region, year or year range, disease_name, and gender via male_population/female_population. Age groups are not available; if requested, ask for clarification.\n"
        "Use memory/context provided elsewhere only if explicitly given; otherwise do not assume prior filters.\n\n"

        "Output format (STRICT): return ONLY valid JSON with exactly these keys:\n"
        "{\"sql\": \"...\", \"params\": [], \"needs_clarification\": false, \"clarification_question\": \"\"}\n\n"

        "Query construction rules:\n"
        "1) SQL must be a single read-only SELECT query.\n"
        "2) Use '?' placeholders for EVERY user-provided value.\n"
        "3) The number of '?' in SQL MUST EXACTLY match len(params).\n"
        "4) params MUST NOT be empty when SQL contains '?'.\n"
        "5) Extract parameter values from the user query only; never hardcode them.\n"
        "6) Preserve the order of params exactly as the placeholders appear.\n"
        "7) Apply LOWER(column) = LOWER(?) for text filters; use LOWER(region) for region comparisons.\n"
        "8) Do NOT invent columns, tables, or values.\n"
        "9) When multiple rows can exist for the same region/year/disease and the user requests totals (e.g., total_cases, total_deaths), aggregate with SUM() and GROUP BY as needed.\n"
        "10) Use GROUP BY for comparisons, ORDER BY + LIMIT for ranking, and avoid SELECT * unless necessary.\n\n"

        "Clarification policy:\n"
        "- If disease/region/year (or time range) is missing for a specific metric, set needs_clarification=true, sql="", params=[].\n"
        "- If the user asks for age groups or genders beyond male/female, set needs_clarification=true and ask a concise question.\n"
        "- Provide a short clarification_question that requests only the missing detail.\n\n"

        "Example:\n"
        "User: Compare cholera deaths in Amhara vs Tigray in 2022\n"
        "Output:\n"
        "{\n"
        "  \"sql\": \"SELECT region, SUM(total_deaths) AS total_deaths FROM disease_statistics WHERE LOWER(disease_name) = LOWER(?) AND LOWER(region) IN (LOWER(?), LOWER(?)) AND year = ? GROUP BY region\",\n"
        "  \"params\": [\"cholera\", \"Amhara\", \"Tigray\", 2022],\n"
        "  \"needs_clarification\": false,\n"
        "  \"clarification_question\": \"\"\n"
        "}\n"
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
