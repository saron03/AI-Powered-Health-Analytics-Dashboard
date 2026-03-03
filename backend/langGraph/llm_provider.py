import os
from threading import Lock

from langchain_groq import ChatGroq

_llm_singleton: ChatGroq | None = None
_llm_lock = Lock()


def init_groq_client() -> ChatGroq:
    global _llm_singleton

    if _llm_singleton is None:
        with _llm_lock:
            if _llm_singleton is None:
                api_key = os.getenv("GROQ_API_KEY")
                if not api_key:
                    raise ValueError("GROQ_API_KEY is missing. Add it to .env before running LangGraph queries.")

                _llm_singleton = ChatGroq(
                    model="llama-3.3-70b-versatile",
                    groq_api_key=api_key,
                    temperature=0,
                )

    return _llm_singleton


def get_groq_client() -> ChatGroq:
    if _llm_singleton is None:
        return init_groq_client()
    return _llm_singleton


def reset_groq_client() -> None:
    global _llm_singleton
    with _llm_lock:
        _llm_singleton = None
