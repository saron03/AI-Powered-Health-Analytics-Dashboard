import { useState, useEffect, useRef } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { motion, AnimatePresence } from 'framer-motion';
import { Sidebar, ChatInput, Thinking } from './components';
import HelpPage from './components/HelpPage';
import ChartCard from './features/charts/ChartCard';
import { addMessage, setLoading } from './store/chatSlice';
import { queryHealthData } from './api';

export default function App() {
  const { history, isLoading } = useSelector((state) => state.chat);
  const dispatch = useDispatch();
  const scrollRef = useRef(null);
  const [showHelp, setShowHelp] = useState(false);


  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [history, isLoading]);

  const handleQuery = async (prompt) => {
    if (!prompt.trim()) return;
    dispatch(addMessage({ role: 'user', content: prompt }));
    dispatch(setLoading(true));

    try {
      const res = await queryHealthData(prompt);

      if (res.status === 'clarify') {
        // Backend needs more info
        dispatch(addMessage({
          role: 'assistant',
          content: res.message || 'Could you provide more details?',
        }));
      } else if (res.status === 'error') {
        // Pipeline or network error 
        dispatch(addMessage({
          role: 'assistant',
          content: `${res.message || 'Something went wrong.'}`,
        }));
      } else {
        // Success show explanation text + chart card
        dispatch(addMessage({
          role: 'assistant',
          content: res.explanation || 'No explanation returned',
          apiResponse: res,
        }));
      }
    } catch (err) {
      dispatch(addMessage({
        role: 'assistant',
        content: `${err.message || 'Sorry, An unexpected error occurred.'}`,
      }));
    } finally {
      dispatch(setLoading(false));
    }
  };

  return (
    <div className="flex h-screen bg-[#F8FAFC] dark:bg-[#0B0E14] text-slate-900 dark:text-slate-100 transition-colors duration-500 font-sans overflow-hidden">
      <Sidebar onShowHelp={() => setShowHelp(true)} />
      <main className="flex-1 flex flex-col relative">
        {showHelp ? (
          <HelpPage onClose={() => setShowHelp(false)} />
        ) : (
          <>
            <div className="flex-1 overflow-y-auto px-6 py-12 md:px-32 lg:px-56 space-y-12 pb-60 custom-scrollbar">
              <AnimatePresence mode="popLayout">
                {history.map((msg, i) => (
                  <motion.div key={i} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className={`flex flex-col gap-8 ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                    <div className={`max-w-2xl px-8 py-5 rounded-[30px] text-[16px] leading-relaxed shadow-sm border ${msg.role === 'user' ? 'bg-indigo-600 text-white border-none rounded-tr-none' : 'bg-white dark:bg-slate-900 border-slate-100 dark:border-slate-800 rounded-tl-none'
                      }`}>
                      {msg.content}
                    </div>
                    {msg.apiResponse && msg.apiResponse.data?.length > 0 && (
                      <ChartCard apiResponse={msg.apiResponse} />
                    )}
                  </motion.div>
                ))}
              </AnimatePresence>
              {isLoading && <Thinking />}
              <div ref={scrollRef} className="h-4" />
            </div>

            <div className="absolute bottom-0 w-full p-10 bg-gradient-to-t from-[#F8FAFC] dark:from-[#0B0E14] backdrop-blur-sm">
              <div className="max-w-4xl mx-auto"><ChatInput onSend={handleQuery} isLoading={isLoading} /></div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}