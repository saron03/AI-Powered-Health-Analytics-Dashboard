# [SARON] Entry point for FastAPI/Flask; connects the whole system
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Any
import sys
import os

# Ensure backend module is found
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import execute_sql_query

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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request schema for executing SQL queries
class SQLQueryRequest(BaseModel):
    query: str
    params: Optional[List[Any]] = []

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
        
    result = execute_sql_query(request.query, tuple(request.params))
    
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
        
    return result

if __name__ == "__main__":
    import uvicorn
    # Run the server on port 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)

