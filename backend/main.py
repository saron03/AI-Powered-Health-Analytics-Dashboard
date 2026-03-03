# [SARON] Entry point for FastAPI/Flask; connects the whole system
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging

from backend.langGraph.service import run_health_langgraph_query
from backend.langGraph.llm_provider import init_groq_client

from .database import execute_sql_query
from .langGraph.helper import reset_session_context
from backend.schema import LangGraphQueryRequest, ResetContextRequest, SQLQueryRequest

# Configure logging once here at the app entrypoint.
# All modules (e.g. database.py) use logging.getLogger(__name__) and will inherit this.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)


# Initialize FastAPI app
app = FastAPI(
    title="AI-Powered Health Analytics Dashboard",
    description="API for querying health data and generating analytics (FR-1, FR-2, FR-17)",
    version="1.0.0"
)

# Enable CORS (Cross-Origin Resource Sharing) to allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify the frontend domain
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_initialize_dependencies():
    init_groq_client()


@app.get("/")
def read_root():
    """
    Root endpoint to verify the API is running.
    """
    return {"message": "Health Analytics API is running", "status": "active"}

@app.get("/health")
def health_check():
    """
    System health check. Verifies database connection.
    """
    result = execute_sql_query("SELECT 1")
    if result.get("status") == "success":
        return {"database": "connected", "api": "healthy"}
    else:
        raise HTTPException(status_code=500, detail="Database connection failed")

@app.post("/api/query")
def run_query(request: SQLQueryRequest):
    """
    Executes a raw SQL query provided by the NLP engine or Frontend.
    
    Args:
        request (SQLQueryRequest): JSON body containing 'query' string.
        
    Returns:
        dict: Query results formatted for the frontend.
    """
    if not request.query.strip().upper().startswith("SELECT"):
        raise HTTPException(status_code=400, detail="Only SELECT queries are allowed for safety.")

    # Normalize each param to a SQLite-safe type (str, int, float, or None)
    # This prevents tuple(params) from breaking when unexpected types are passed
    safe_params = tuple(
        p if isinstance(p, (str, int, float, type(None))) else str(p)
        for p in request.params
    )

    # readonly=True enforces: read-only DB connection + allowed-tables check + MAX_QUERY_ROWS cap
    try:
        result = execute_sql_query(request.query, safe_params, readonly=True)
    except ValueError as e:
        # Raised by _validate_query_tables if a disallowed table is referenced
        raise HTTPException(status_code=400, detail=str(e))
    
    if result["status"] == "error":
        # Distinguish client-side input errors from actual server/DB failures.
        # Client errors (bad SQL syntax, unknown column) → 400 Bad Request
        # Server errors (DB unavailable, unexpected crash)  → 500 Internal Server Error
        error_message = result.get("message", "Database query failed")
        client_error_signals = (
            "syntax error",
            "parse error",
            "no such table",
            "no such column",
            "invalid input syntax",
        )
        is_client_error = any(sig in error_message.lower() for sig in client_error_signals)
        status_code = 400 if is_client_error else 500
        raise HTTPException(status_code=status_code, detail=error_message)
        
    return result


@app.post("/api/langgraph/query")
def run_langgraph_query(request: LangGraphQueryRequest):
    """
    Runs the Groq-powered LangGraph pipeline for natural language health analytics.
    """
    user_query = request.user_query.strip()
    if not user_query:
        raise HTTPException(status_code=400, detail="user_query is required.")

    try:
        result = run_health_langgraph_query(
            user_query=user_query,
            session_id=request.session_id.strip() or "default",
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logging.getLogger(__name__).exception("LangGraph pipeline failed")
        raise HTTPException(status_code=500, detail=f"LangGraph pipeline error: {str(e)}")


@app.post("/api/langgraph/reset")
def reset_langgraph_context(request: ResetContextRequest):
    """
    Resets session memory for follow-up context.
    """
    session_id = request.session_id.strip() or "default"
    return reset_session_context(session_id)

if __name__ == "__main__":
    import uvicorn
    # Run the server on port 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)

