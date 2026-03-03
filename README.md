# AI-Powered Health Analytics Dashboard

A system that allows users to query health statistics using natural language prompts, converting them into structured database queries to visualize trends in health data.

## 🚀 Project Status
| Domain | Lead | Status |
| :--- | :--- | :--- |
| **Backend & Database** | **Saron** |  **Completed** (DB Schema, Seeding, API Setup) |
| NLP & Logic | Sisay | Pending |
| Frontend & Viz | Mekdelawit | Pending |


---

## 🛠️ Backend & Database Setup (Saron's Domain)
This section details the implementation of the Data Management (FR-1 to FR-4) and Backend Architecture.

### 1. Prerequisites
- Python 3.8+
- SQLite3

### 2. Installation
Clone the repository and navigate to the project folder:
```bash
git clone https://github.com/saron03/AI-Powered-Health-Analytics-Dashboard.git
cd AI-Powered-Health-Analytics-Dashboard
```

Create a virtual environment and verify dependencies:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Database Initialization (FR-1)
The system uses **SQLite** with 4 main tables: `population_stats`, `disease_statistics`, `hospital_resources`, and `vaccination_records`.

To initialize the database and generate **10,000+ dummy records** for testing:
```bash
python3 data/seed_data.py
```
*   This creates `data/health_data.db`.
*   It populates the tables with realistic data for Ethiopian regions (2010-2024).

### 4. Running the Backend API (FR-2, FR-17)
The backend is built with **FastAPI**. It handles database connections and SQL execution.

Create a `.env` file in the project root with your Groq API key:
```bash
GROQ_API_KEY=your_groq_api_key
```

Start the server:
```bash
uvicorn backend.main:app --reload
```
The API will be available at: `http://127.0.0.1:8000`

### 5. API Documentation
Once the server is running, visit **[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)** to see the interactive Swagger UI.

#### Available Endpoints
-   `GET /`: Health check for the API.
-   `GET /health`: Verifies database connection.
-   `POST /api/query`: Executes a secure `SELECT` SQL query against the health database.
    -   **Payload**: `{"query": "SELECT * FROM disease_statistics LIMIT 5"}`
-   `POST /api/langgraph/query`: Runs the full LangGraph NLP-to-SQL pipeline using Groq with session memory.
    -   **Payload**: `{"user_query": "Show malaria cases in Oromia in 2022", "session_id": "demo-user-1"}`
-   `POST /api/langgraph/reset`: Clears memory context for a session.
    -   **Payload**: `{"session_id": "demo-user-1"}`

---

## 📂 Project Structure
```
├── data/
│   ├── health_data.db
│   └── seed_data.py
├── backend/
│   ├── main.py
│   ├── database.py
│   ├── nlp_engine.py
│   ├── memory_manager.py
│   └── query_gen.py
├── frontend/
│   ├── index.html
│   ├── assets/
│   └── js/
│       ├── app.js
│       └── charts.js
├── requirements.txt
└── README.md
```
