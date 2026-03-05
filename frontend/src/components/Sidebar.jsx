import { useSelector, useDispatch } from "react-redux";
import { motion } from "framer-motion";
import { RotateCw } from "lucide-react";
import { resetChat } from "../store/chatSlice";
import { resetSession } from "../api";

export default function Sidebar({ onShowHelp }) {
  const history = useSelector((state) => state.chat.history);
  const dispatch = useDispatch();
  const userQueries = history.filter((m) => m.role === "user");

  const handleNewAnalysis = () => {
    dispatch(resetChat());
    resetSession(); // clear backend session memory
  };

  return (
    <aside className="w-72 hidden md:flex flex-col bg-white dark:bg-[#0B0E14] border-r border-slate-200 dark:border-slate-800 transition-colors duration-500">
      {/* Logo */}
      <div className="p-6 flex items-center gap-3">
        <span className="font-bold text-xl dark:text-white tracking-tight">
        AI Analytics
        </span>
      </div>

      {/* New Analysis */}
    <div className="px-4 mb-2">
  <button
    onClick={handleNewAnalysis}
    className="w-full flex items-center justify-center gap-2 p-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-sm font-semibold transition-all shadow-md shadow-indigo-500/20"
  >
    <RotateCw size={18} /> New Analysis
  </button>
</div>
      {/* Help documentation */}
      <div className="px-4 mb-4">
        <button
          onClick={() => onShowHelp && onShowHelp()}
          className="w-full flex items-center justify-center gap-2 p-3 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 rounded-xl text-sm font-semibold transition-all"
        >
          Help
        </button>
      </div>

      {/* Recent Queries */}
      <div className="flex-1 overflow-y-auto px-4 custom-scrollbar">
        <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest px-2 mb-4">
          Recent Analytics
        </p>
        <div className="space-y-1">
          {userQueries.map((m, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              className="p-3 text-sm truncate hover:bg-slate-50 dark:hover:bg-slate-900 rounded-xl cursor-pointer text-slate-600 dark:text-slate-400 transition-all"
            >
              {m.content}
            </motion.div>
          ))}
        </div>
      </div>
    </aside>
  );
}