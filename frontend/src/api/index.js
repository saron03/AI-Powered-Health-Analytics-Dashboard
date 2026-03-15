import axios from "axios";

const api = axios.create({
  baseURL: "https://health-data-analytics-7hm2.onrender.com",
  timeout: 30000,
});

/**
 * Sends a natural-language health query to the LangGraph backend.
 *
 * Returns a normalised object the UI can consume directly:
 *   status      – "ok" | "clarify" | "error"
 *   title       – short title for the chart card
 *   explanation – plain-language summary of the result
 *   sql         – the generated SQL (for debugging)
 *   data        – flat array of row objects  (table.rows from backend)
 *   columns     – column name list           (table.columns from backend)
 *   chart       – { type, data: { labels, datasets } }  (passthrough)
 *   chart_type  – shortcut to chart.type
 *   confidence_score – aggregate pipeline confidence
 */
export const queryHealthData = async (userQuery, sessionId = "default") => {
  try {
    const response = await api.post("/api/langgraph/query", {
      user_query: userQuery,
      session_id: sessionId,
    });

    const res = response.data;

    //  Clarification — backend asks the user a follow-up question
    if (res.clarification_needed) {
      return {
        status: "clarify",
        title: res.title || "Clarification Needed",
        message: res.explanation || res.error || "Could you provide more details?",
        sql: res.sql || "",
      };
    }

    //  Pipeline error — backend returned an error string
    if (res.error) {
      return {
        status: "error",
        title: res.title || "Query Issue",
        message: res.error,
        explanation: res.explanation || "",
        sql: res.sql || "",
      };
    }

    // Success — map backend fields to what ChartCard / App expect
    const tableRows = res.table?.rows ?? [];
    const tableColumns = res.table?.columns ?? [];
    const chart = res.chart ?? null;

    return {
      status: "ok",
      title: res.title || "Health Analytics",
      explanation: res.explanation || "",
      sql: res.sql || "",
      data: tableRows,
      columns: tableColumns,
      chart: chart,
      chart_type: chart?.type || "table",
      confidence_score: res.confidence_score ?? 0,
    };
  } catch (error) {
    console.error("API Error:", error);
    return {
      status: "error",
      message:
        error.response?.data?.detail ||
        (error.code === "ECONNABORTED"
          ? "Request timed out. The server may be busy — please try again."
          : "Server connection failed. Is the backend running?"),
    };
  }
};

/**
 * Resets the backend session memory so follow-up context is cleared.
 */
export const resetSession = async (sessionId = "default") => {
  try {
    await api.post("/api/langgraph/reset", { session_id: sessionId });
  } catch (error) {
    console.error("Session reset failed:", error);
  }
};