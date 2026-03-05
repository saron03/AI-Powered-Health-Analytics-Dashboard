import React, { useState } from "react";
import {
  Info,
  BookOpen,
  HelpCircle,
  ArrowLeftCircle,
  ChevronDown,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

function AccordionItem({ question, answer }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-5 py-4 text-left font-medium text-gray-800 dark:text-gray-100 hover:bg-gray-50 dark:hover:bg-gray-700 transition"
      >
        <span>{question}</span>
        <ChevronDown
          size={18}
          className={`transition-transform duration-300 ${open ? "rotate-180" : ""
            }`}
        />
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="px-5 pb-4 text-gray-600 dark:text-gray-300"
          >
            {answer}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function HelpPage({ onClose }) {
  return (
    <div className="h-screen bg-gradient-to-br from-indigo-50 to-purple-50 dark:from-gray-900 dark:to-gray-950 flex items-center justify-center px-4">

      {/* Scrollable Card */}
      <div className="max-w-4xl w-full max-h-[90vh] overflow-y-auto scrollbar-thin scrollbar-thumb-indigo-400 dark:scrollbar-thumb-gray-700 scrollbar-track-transparent backdrop-blur-xl bg-white/80 dark:bg-gray-900/80 rounded-2xl shadow-2xl p-8">

        {/* Back Button */}
        <button
          onClick={onClose}
          className="mb-6 inline-flex items-center gap-2 text-sm text-indigo-600 dark:text-indigo-400 hover:underline"
        >
          <ArrowLeftCircle size={18} /> Back to analysis
        </button>

        {/* Header */}
        <div className="text-center mb-10">
          <h1 className="text-4xl font-extrabold text-gray-900 dark:text-white">
            AI Health Analytics Help
          </h1>
          <p className="mt-3 text-gray-600 dark:text-gray-400">
            Everything you need to understand, use, and troubleshoot.
          </p>
        </div>

        {/* Getting Started */}
        <section className="mb-10">
          <h2 className="flex items-center gap-2 text-2xl font-semibold mb-4 text-indigo-600 dark:text-indigo-400">
            <Info /> Getting Started
          </h2>

          <ul className="list-disc list-inside space-y-2 text-gray-700 dark:text-gray-300">
            <li>Type a health-related query in the input field.</li>
            <li>Press <strong>Enter</strong> or click send.</li>
            <li>Charts appear automatically if data exists.</li>
            <li>Use <em>New Analysis</em> to reset the session.</li>
          </ul>
        </section>

        {/* Exporting */}
        <section className="mb-10">
          <h2 className="flex items-center gap-2 text-2xl font-semibold mb-4 text-indigo-600 dark:text-indigo-400">
            <BookOpen /> Exporting Results
          </h2>

          <p className="text-gray-700 dark:text-gray-300">
            Download charts as <strong>PNG</strong> and export tables as{" "}
            <strong>CSV</strong> for external analysis.
          </p>
        </section>

        {/* FAQ */}
        <section className="mb-10">
          <h2 className="flex items-center gap-2 text-2xl font-semibold mb-6 text-indigo-600 dark:text-indigo-400">
            <HelpCircle /> Frequently Asked Questions
          </h2>

          <div className="space-y-4">
            <AccordionItem
              question="What kind of questions can I ask?"
              answer="You can ask natural language questions about health statistics, trends, and comparisons."
            />

            <AccordionItem
              question="Why is my chart empty?"
              answer="This usually means there is no data. Try refining your query."
            />

            <AccordionItem
              question="Can I save my analysis?"
              answer="Currently, analyses are session-based only. Saving will be added in future versions."
            />

            <AccordionItem
              question="Does it  work offline?"
              answer="No. An internet connection is required to fetch and analyze data."
            />
          </div>
        </section>

      </div>
    </div>
  );
}