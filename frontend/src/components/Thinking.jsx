import { motion } from 'framer-motion';

export default function Thinking() {
  return (
    <div className="flex gap-2 items-center px-6 py-4 bg-white dark:bg-slate-900 rounded-[22px] border border-slate-100 dark:border-slate-800 w-fit">
      {[0, 0.2, 0.4].map((delay) => (
        <motion.div
          key={delay}
          animate={{ opacity: [0.3, 1, 0.3], y: [0, -3, 0] }}
          transition={{ duration: 1.5, repeat: Infinity, delay }}
          className="h-2 w-2 bg-indigo-500 rounded-full"
        />
      ))}
      <span className="ml-2 text-xs font-medium text-slate-400">Analyzig...</span>
    </div>
  );
}