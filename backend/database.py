# [SARON] Logic to connect to the 4 tables and handle SQL execution (FR-1, FR-2, FR-3)
import sqlite3
import os
import logging
from typing import List, Dict, Any, Optional

# Configure logging to track database operations
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Absolute path to the database ensuring we can find it from anywhere
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'data', 'health_data.db')

def get_db_connection():
    """
    Establishes a connection to the SQLite database.
    Sets the row_factory to sqlite3.Row to access columns by name.
    """
    if not os.path.exists(DB_PATH):
        logger.error(f"Database file not found at: {DB_PATH}")
        raise FileNotFoundError(f"Database file not found at {DB_PATH}. Did you run seed_data.py?")
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Allows accessing results like dicts (row['column'])
    return conn

def execute_sql_query(query: str, params: tuple = ()) -> Dict[str, Any]:
    """
    Executes a raw SQL query safely and returns the results.
    
    req: FR-2 (SQL-based querying)
    req: FR-3 (Data validation and handling missing values)
    
    Args:
        query (str): The SQL query string.
        params (tuple): Optional parameters for safe SQL parameter substitution.
        
    Returns:
        Dict: A dictionary containing:
            - 'status': 'success' or 'error'
            - 'data': List of dictionaries (rows) or None
            - 'message': Error message or success count
            - 'columns': List of column names (useful for frontend tables)
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        logger.info(f"Executing Query: {query} | Params: {params}")
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
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

    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        return {
            "status": "error",
            "data": None,
            "message": f"Database error: {str(e)}"
        }
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {
            "status": "error",
            "data": None,
            "message": f"System error: {str(e)}"
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

