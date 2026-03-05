import { useState } from "react";
import { Send, Loader2 } from "lucide-react";
import { motion } from "framer-motion";

const PROMPT_SUGGESTIONS = [
  "Show malaria trends in 2023",
  "Compare male vs female patients",
  "Top 5 regions by disease cases",
];

export default function ChatInput({ onSend, isLoading }) {
  const [input, setInput] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;
    onSend(input.trim());
    setInput("");
  };

  const handleSuggestionClick = (text) => {
    if (isLoading) return;
    setInput(text);
  };

  return (
    <div className="max-w-4xl mx-auto w-full px-4">
      {/* ================= INPUT FORM ================= */}
      <form onSubmit={handleSubmit} className="relative group">

        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask AI Health Analytics"
          disabled={isLoading}
          className="
            w-full
            bg-white/80 dark:bg-slate-900/80
            backdrop-blur-xl
            border border-slate-200 dark:border-slate-800
            rounded-[28px]
            py-5 pl-7 pr-16
            shadow-2xl
            focus:outline-none
            focus:ring-2 focus:ring-indigo-500
            transition-all
            font-sans text-base
            text-slate-800 dark:text-white
            placeholder:text-slate-400
            disabled:opacity-60
          "
        />

        {/* ================= SEND BUTTON ================= */}
        <button
          type="submit"
          disabled={isLoading || !input.trim()}
          className="
            absolute right-2.5 top-2.5
            p-3.5
            bg-indigo-600 text-white
            rounded-full
            hover:bg-indigo-700
            disabled:bg-slate-300 dark:disabled:bg-slate-800
            transition-all
            shadow-lg
            active:scale-95
          "
        >
          {isLoading ? (
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
            >
              <Loader2 size={20} />
            </motion.div>
          ) : (
            <Send size={20} />
          )}
        </button>
      </form>

      {/* ================= PROMPT GUIDANCE ================= */}
      <div className="mt-5 flex flex-wrap justify-center gap-2">
        {PROMPT_SUGGESTIONS.map((prompt, i) => (
          <button
            key={i}
            onClick={() => handleSuggestionClick(prompt)}
            disabled={isLoading}
            className="
              px-3 py-1.5
              rounded-full
              text-[11px]
              font-semibold
              bg-slate-100 dark:bg-slate-800
              text-slate-600 dark:text-slate-300
              hover:bg-indigo-100 hover:text-indigo-700
              dark:hover:bg-indigo-500/10 dark:hover:text-indigo-400
              transition
              disabled:opacity-50
            "
          >
            {prompt}
          </button>
        ))}
      </div>

      {/* ================= FOOTER LABEL ================= */}
      <div className="flex justify-center mt-4">
        <span className="text-[10px] text-slate-400 font-bold uppercase tracking-widest">
          AI-Powered Health Analytics
        </span>
      </div>
    </div>
  );
}