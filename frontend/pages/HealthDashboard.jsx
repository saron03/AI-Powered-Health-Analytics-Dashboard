import { useState, useEffect, useRef } from "react";
import { useSelector, useDispatch } from "react-redux";
import { motion, AnimatePresence } from "framer-motion";
import ChartCard from "../components/ChartCard";
import { queryHealthData } from "../api/health";
import { addMessage, setLoading } from "../store/chatSlice";

export default function HealthDashboard() {
  const [prompt, setPrompt] = useState("");
  const [apiResponse, setApiResponse] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const { history, isLoading } = useSelector((state) => state.chat);
  const dispatch = useDispatch();
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [history]);

  const handleFetch = async () => {
    if (!prompt) return;
    dispatch(addMessage({ role: 'user', content: prompt }));
    dispatch(setLoading(true));
    setLoading(true);
    setMessage("");

    const response = await queryHealthData(prompt, "user1");

    console.log("health api returned", response);
    if (response.status === "ok") {
      setApiResponse(response);
      // push assistant message with full API response 
      dispatch(addMessage({
        role: 'assistant',
        content: response.explanation || '(no explanation returned)',
        apiResponse: response,
        chartData: response.data,
        chartType: response.chart_type,
        explanation: response.explanation,
        title: response.title,
       
      }));
    } else if (response.status === "clarify") {
      setApiResponse(null);
      setMessage(response.message || "Clarification needed");
      dispatch(addMessage({ role: 'assistant', content: response.message }));
    } else {
      setApiResponse(null);
      setMessage(response.message || "An error occurred");
      dispatch(addMessage({ role: 'assistant', content: `${response.message}` }));
    }

    dispatch(setLoading(false));
    setLoading(false);
  };

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-4">Health Analytics Dashboard</h1>
      <div className="flex gap-2 mb-6">
        <input
          type="text"
          placeholder="Enter prompt..."
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          className="border p-2 rounded-md flex-1"
        />
        <button onClick={handleFetch} className="bg-indigo-600 text-white px-4 rounded-md">Analyze</button>
      </div>

      {loading && <p className="text-indigo-600">Loading...</p>}

      {message && !loading && (
        <p className="mb-4 text-red-600">{message}</p>
      )}

      {/* chat history */}
      <AnimatePresence mode="popLayout">
        {history.map((msg, i) => {
          return (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className={`flex flex-col gap-8 ${
                msg.role === 'user' ? 'items-end' : 'items-start'
              }`}
            >
              <div
                className={`max-w-2xl px-8 py-5 rounded-[30px] text-[16px] leading-relaxed shadow-sm border ${
                  msg.role === 'user'
                    ? 'bg-indigo-600 text-white border-none rounded-tr-none'
                    : 'bg-white dark:bg-slate-900 border-slate-100 dark:border-slate-800 rounded-tl-none'
                }`}
              >
                {msg.content}
              </div>
              {msg.apiResponse && (
                <ChartCard apiResponse={msg.apiResponse} />
              )}
            </motion.div>
          );
        })}
      </AnimatePresence>
      <div ref={scrollRef} className="h-4" />
    </div>
  );
}