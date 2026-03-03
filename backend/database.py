# [SARON] Logic to connect to the 4 tables and handle SQL execution (FR-1, FR-2, FR-3)
import sqlite3
import os
import logging
from typing import List, Dict, Any, Optional

# Use a module-level logger only. Logging is configured at the app entrypoint (main.py)
# to avoid overriding the global root logger configuration at import time.
logger = logging.getLogger(__name__)

# Absolute path to the database ensuring we can find it from anywhere
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'data', 'health_data.db')

# Server-side safety constants for the public query endpoint
# Only these 4 tables may be referenced in user-facing queries (FR-4)
ALLOWED_TABLES = {
    "population_stats",
    "disease_statistics",
    "hospital_resources",
    "vaccination_records",
}
# Maximum number of rows returned per query to prevent heavy accidental scans
MAX_QUERY_ROWS = 1000

def get_db_connection(readonly: bool = False):
    """
    Establishes a connection to the SQLite database.
    Sets the row_factory to sqlite3.Row to access columns by name.

    Args:
        readonly (bool): If True, opens the database in read-only mode using
                         SQLite URI mode. This is used for all user-facing
                         query endpoints to prevent any accidental writes.
    """
    if not os.path.exists(DB_PATH):
        logger.error(f"Database file not found at: {DB_PATH}")
        raise FileNotFoundError(f"Database file not found at {DB_PATH}. Did you run seed_data.py?")

    if readonly:
        # URI mode with mode=ro opens the file in read-only mode at the OS level.
        # SQLite will raise an error if anything tries to write through this connection.
        uri = f"file:{DB_PATH}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
    else:
        conn = sqlite3.connect(DB_PATH)

    conn.row_factory = sqlite3.Row  # Allows accessing results like dicts (row['column'])
    return conn

def _validate_query_tables(query: str):
    """
    Checks that every table referenced in the query is in the ALLOWED_TABLES set.
    Raises ValueError if an unrecognised table is found.
    This prevents users from probing internal SQLite tables (e.g. sqlite_master).
    """
    import re
    # Extract all word tokens that follow FROM or JOIN (case-insensitive)
    referenced = re.findall(r'(?:FROM|JOIN)\s+(\w+)', query, re.IGNORECASE)
    for table in referenced:
        if table.lower() not in {t.lower() for t in ALLOWED_TABLES}:
            raise ValueError(
                f"Table '{table}' is not in the allowed table list: {sorted(ALLOWED_TABLES)}"
            )

def execute_sql_query(query: str, params: tuple = (), readonly: bool = False) -> Dict[str, Any]:
    """
    Executes a SQL query and returns the results.

    req: FR-2 (SQL-based querying)
    req: FR-3 (Data validation and handling missing values)

    Args:
        query (str): The SQL query string.
        params (tuple): Optional parameters for safe SQL parameter substitution.
        readonly (bool): If True, opens the DB in read-only mode and enforces
                         the ALLOWED_TABLES allowlist and MAX_QUERY_ROWS limit.
                         Should be True for all user-facing API endpoints.

    Returns:
        Dict: A dictionary containing:
            - 'status': 'success' or 'error'
            - 'data': List of dictionaries (rows) or None
            - 'message': Error message or success count
            - 'columns': List of column names (useful for frontend tables)
    """
    conn = None
    try:
        # Validate allowed tables before opening a connection
        if readonly:
            _validate_query_tables(query)

        conn = get_db_connection(readonly=readonly)
        cursor = conn.cursor()
        
        logger.info(f"Executing Query: {query} | Params: {params}")

        cursor.execute(query, params)

        # Enforce a hard row cap for user-facing queries to prevent heavy scans
        rows = cursor.fetchmany(MAX_QUERY_ROWS) if readonly else cursor.fetchall()
        
        # Convert sqlite3.Row objects to standard dictionaries
        data = [dict(row) for row in rows]
        
        # Extract column names for frontend table headers
        columns = []
        if cursor.description:
            columns = [description[0] for description in cursor.description]

        # FR-3: Handle missing values / Empty results
        if not data:
            logger.warning("Query executed successfully but returned no results.")
            return {
                "status": "success",
                "data": [],
                "columns": columns,
                "message": "No records found matching the criteria."
            }

        return {
            "status": "success",
            "data": data,
            "columns": columns,
            "message": f"Successfully retrieved {len(data)} records."
        }

    except FileNotFoundError:
        # DB file is missing. Log the full path details internally, return safe message to client.
        logger.error("Database file not found during query execution.", exc_info=True)
        return {
            "status": "error",
            "data": [],
            "columns": [],
            "message": "Database is currently unavailable. Please contact support."
        }

    except sqlite3.Error:
        # Log full SQLite error details (including stack trace) internally only.
        # Raw SQLite messages can expose schema/path info to clients.
        logger.error("Database error during query execution.", exc_info=True)
        return {
            "status": "error",
            "data": [],
            "columns": [],
            "message": "A database error occurred while processing the request."
        }

    except Exception:
        # Catch-all: log full details internally, return a generic message to client.
        logger.error("Unexpected error during query execution.", exc_info=True)
        return {
            "status": "error",
            "data": [],
            "columns": [],
            "message": "An internal server error occurred while processing the request."
        }
        
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    # Quick test to verify connection and query execution works
    print("--- Testing Database Connection ---")
    
    # Test 1: Simple Select
    test_query = "SELECT * FROM population_stats LIMIT 5"
    result = execute_sql_query(test_query)
    
    if result['status'] == 'success':
        print(f"✅ Test Passed. Retrieved {len(result['data'])} rows.")
        print(f"Columns: {result['columns']}")
        print(f"Sample Row: {result['data'][0]}")
    else:
        print(f"❌ Test Failed: {result['message']}")

