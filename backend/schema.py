# Request schema for executing SQL queries.
# params uses Field(default_factory=list) to avoid mutable default issues.
# It is non-optional so clients must always send a list (even if empty).
from pydantic import BaseModel, Field
from typing import List, Any

class SQLQueryRequest(BaseModel):
    query: str
    params: List[Any] = Field(default_factory=list)


class LangGraphQueryRequest(BaseModel):
    user_query: str
    session_id: str = "default"


class ResetContextRequest(BaseModel):
    session_id: str = "default"
