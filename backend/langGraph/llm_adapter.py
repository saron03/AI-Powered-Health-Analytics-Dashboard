from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any, Dict

from backend.langGraph.helper import llm_json
from backend.langGraph.pipeline_config import DEFAULT_LLM_TIMEOUT_SECONDS


def safe_llm_json(system_prompt: str, user_prompt: str, fallback: Dict[str, Any], timeout_seconds: int = DEFAULT_LLM_TIMEOUT_SECONDS) -> Dict[str, Any]:
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(llm_json, system_prompt, user_prompt)
            result = future.result(timeout=timeout_seconds)
            return result if isinstance(result, dict) else dict(fallback)
    except (FuturesTimeoutError, Exception):
        return dict(fallback)
