import { useState, useRef } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, LineChart, Line, PieChart, Pie, Cell, Label
} from "recharts";
import { Download, ChevronDown, Loader2, FileSpreadsheet } from "lucide-react";
import * as htmlToImage from "html-to-image";

const COLORS = ["#06b6d4", "#6366f1", "#ec4899", "#8b5cf6", "#f59e0b", "#10b981"];

/* ---------- Rotated Tick Component ---------- */
const RotatedTick = ({ x, y, payload }) => (
  <g transform={`translate(${x},${y + 12})`}>
    <text
      textAnchor="end"
      transform="rotate(-45)"
      fontSize={11}
      fill="#64748b"
      fontWeight="600"
    >
      {payload.value}
    </text>
  </g>
);

export default function ChartCard({ apiResponse }) {
  const cardRef = useRef(null);
  const [expanded, setExpanded] = useState(false);
  const [isExporting, setIsExporting] = useState(false);

  // Guard: no data → render nothing
  if (!apiResponse?.data?.length) return null;

  //  Prevents API URLs from showing as the title
  const rawTitle = apiResponse.title || "";
  const cleanTitle = (rawTitle.includes("http") || rawTitle.includes("localhost") || rawTitle.includes("/api/"))
    ? "AI Analytics"
    : rawTitle;

  const { chart_type, data } = apiResponse;
  const chartType = chart_type?.toLowerCase() || "bar";
  const numericKeys = Object.keys(data[0]).filter((k) => typeof data[0][k] === "number");
  const xKey = Object.keys(data[0]).find((k) => typeof data[0][k] !== "number") || "";
  const displayedData = expanded ? data : data.slice(0, 5);

  /* ================= IMAGE EXPORT ================= */
  const downloadImage = async () => {
    if (!cardRef.current || isExporting) return;
    setIsExporting(true);
    try {
      await new Promise((r) => setTimeout(r, 150));
      const dataUrl = await htmlToImage.toPng(cardRef.current, {
        cacheBust: true,
        backgroundColor: "#ffffff",
        pixelRatio: 2,
        filter: (node) => node.tagName !== 'BUTTON' && !node.classList?.contains('no-export'),
      });
      const link = document.createElement("a");
      link.download = `${cleanTitle.replace(/\s+/g, "_")}.png`;
      link.href = dataUrl;
      link.click();
    } catch (err) {
      console.error("Export Error:", err);
    } finally {
      setIsExporting(false);
    }
  };

  /* ================= DATA EXPORT ================= */
  const downloadCSV = () => {
    const headers = Object.keys(data[0]);
    const csvContent = [
      headers.join(","),
      ...data.map(row => headers.map(header => JSON.stringify(row[header] ?? "")).join(","))
    ].join("\n");

    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", `${cleanTitle.replace(/\s+/g, "_")}_data.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  /* ================= CHART CONFIG ================= */
  const axisStyle = { stroke: "#475569", strokeWidth: 2.5 };
  const chartSettings = { isAnimationActive: false };
  const marginConfig = { top: 10, right: 30, left: 60, bottom: 100 };

  const renderChart = () => {
    // If chart_type is "table" or there are no numeric keys, skip chart rendering
    if (chartType === "table" || numericKeys.length === 0) return null;

    const RightLegend = (
      <Legend
        verticalAlign="top"
        align="right"
        iconType="circle"
        wrapperStyle={{ paddingBottom: "25px", fontSize: "12px", fontWeight: "600" }}
      />
    );

    switch (chartType) {
      case "line":
        return (
          <LineChart data={data} margin={marginConfig}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
            <XAxis dataKey={xKey} interval={0} tick={<RotatedTick />} axisLine={axisStyle} tickLine={false}>
              <Label value={xKey.toUpperCase()} offset={-85} position="insideBottom" fill="#94a3b8" fontSize={11} fontWeight="800" />
            </XAxis>
            <YAxis axisLine={axisStyle} tickLine={false} tick={{ fill: '#64748b', fontSize: 11, fontWeight: '700' }}>
              <Label value="VALUE" angle={-90} position="insideLeft" offset={-20} style={{ textAnchor: 'middle', fill: '#94a3b8', fontWeight: '800', fontSize: 11 }} />
            </YAxis>
            <Tooltip contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px rgba(0,0,0,0.1)' }} />
            {RightLegend}
            {numericKeys.map((k, i) => (
              <Line key={k} dataKey={k} stroke={COLORS[i % COLORS.length]} strokeWidth={4} dot={{ r: 5 }} {...chartSettings} />
            ))}
          </LineChart>
        );

      case "pie":
        return (
          <PieChart>
            <Pie data={data} dataKey={numericKeys[0]} nameKey={xKey} innerRadius={75} outerRadius={115} paddingAngle={5} {...chartSettings}>
              {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
            </Pie>
            <Tooltip />
            <Legend verticalAlign="top" align="right" iconType="circle" />
          </PieChart>
        );

      case "stacked_bar":
        return (
          <BarChart data={data} margin={marginConfig}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
            <XAxis dataKey={xKey} interval={0} tick={<RotatedTick />} axisLine={axisStyle} tickLine={false}>
              <Label value={xKey.toUpperCase()} offset={-85} position="insideBottom" fill="#94a3b8" fontSize={11} fontWeight="800" />
            </XAxis>
            <YAxis axisLine={axisStyle} tickLine={false} tick={{ fill: '#64748b', fontSize: 11, fontWeight: '700' }}>
              <Label value="VALUE" angle={-90} position="insideLeft" offset={-20} style={{ textAnchor: 'middle', fill: '#94a3b8', fontWeight: '800', fontSize: 11 }} />
            </YAxis>
            <Tooltip cursor={{ fill: '#f8fafc' }} contentStyle={{ borderRadius: '12px', border: 'none' }} />
            {RightLegend}
            {numericKeys.map((k, i) => (
              <Bar key={k} dataKey={k} stackId="a" fill={COLORS[i % COLORS.length]} radius={[6, 6, 0, 0]} barSize={35} {...chartSettings} />
            ))}
          </BarChart>
        );

      default: // "bar" and any unknown types
        return (
          <BarChart data={data} margin={marginConfig}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
            <XAxis dataKey={xKey} interval={0} tick={<RotatedTick />} axisLine={axisStyle} tickLine={false}>
              <Label value={xKey.toUpperCase()} offset={-85} position="insideBottom" fill="#94a3b8" fontSize={11} fontWeight="800" />
            </XAxis>
            <YAxis axisLine={axisStyle} tickLine={false} tick={{ fill: '#64748b', fontSize: 11, fontWeight: '700' }}>
              <Label value="VALUE" angle={-90} position="insideLeft" offset={-20} style={{ textAnchor: 'middle', fill: '#94a3b8', fontWeight: '800', fontSize: 11 }} />
            </YAxis>
            <Tooltip cursor={{ fill: '#f8fafc' }} contentStyle={{ borderRadius: '12px', border: 'none' }} />
            {RightLegend}
            {numericKeys.map((k, i) => (
              <Bar key={k} dataKey={k} fill={COLORS[i % COLORS.length]} radius={[6, 6, 0, 0]} barSize={35} {...chartSettings} />
            ))}
          </BarChart>
        );
    }
  };

  const chart = renderChart();

  return (
    <div className="flex flex-col gap-6 w-full max-w-6xl mx-auto p-4 font-sans text-slate-900 dark:text-slate-100">
      {/* ===== CHART AREA (only if a visual chart type was selected) ===== */}
      {chart && (
        <div ref={cardRef} className="bg-white dark:bg-slate-900 p-10 md:p-14 rounded-[32px] border border-slate-200 dark:border-slate-800 shadow-sm relative overflow-hidden">
          <div className="flex justify-between items-start mb-6">
            <div>
              <span className="text-[11px] font-bold uppercase tracking-widest text-indigo-500 bg-indigo-50 dark:bg-indigo-500/10 px-2.5 py-1 rounded">
                Health Analytics
              </span>
              <h2 className="
    mt-3
    font-black
    tracking-tight
    leading-tight
    text-slate-800
    dark:text-slate-100

    sm:text-1xl
    md:text-2xl
    lg:text-3xl
  ">
                {cleanTitle}
              </h2>
            </div>

            <button
              onClick={downloadImage}
              disabled={isExporting}
              className="flex items-center gap-2 px-6 py-2.5 text-sm font-bold text-slate-600 dark:text-slate-300 bg-white dark:bg-slate-800 rounded-xl hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
            >
              {isExporting ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />}
              <span>{isExporting ? "Processing..." : "Download"}</span>
            </button>
          </div>

          <div className="h-[550px] w-full mt-4">
            <ResponsiveContainer width="100%" height="100%">
              {chart}
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* ===== TABLE AREA ===== */}
      <div className="bg-white dark:bg-slate-900 rounded-[28px] border border-slate-200 dark:border-slate-800 overflow-hidden shadow-sm no-export">
        <div className="flex justify-between items-center px-10 py-6 bg-slate-50/50 dark:bg-slate-800/30 border-b border-slate-100 dark:border-slate-800">
          <h4 className="text-xs font-bold uppercase text-slate-400 tracking-widest">Data Details</h4>

          <div className="flex gap-4 items-center">
            {/* CSV Download positioned in the Table UI */}
            <button
              onClick={downloadCSV}
              className="flex items-center gap-2 px-4 py-2 text-xs font-bold text-slate-600 dark:text-slate-300 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors"
            >
              <FileSpreadsheet size={14} />
              <span>Download CSV</span>
            </button>

            <button
              onClick={() => setExpanded(!expanded)}
              className="text-sm font-bold text-slate-600 dark:text-slate-300 hover:text-indigo-600 dark:hover:text-indigo-400 flex items-center gap-2 ml-2 transition-colors"
            >
              {expanded ? "Collapse Table" : "View All Data"}
              <ChevronDown size={18} className={`transition-transform duration-300 ${expanded ? "rotate-180" : ""}`} />
            </button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead className="bg-slate-50/20 dark:bg-slate-800/20">
              <tr>
                {Object.keys(data[0] || {}).map((h) => (
                  <th key={h} className="px-10 py-5 text-[11px] font-bold uppercase text-slate-500 dark:text-slate-400 border-b border-slate-100 dark:border-slate-800">
                    {h.replace(/_/g, " ")}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {displayedData.map((row, i) => (
                <tr key={i} className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors">
                  {Object.values(row).map((v, j) => (
                    <td key={j} className="px-10 py-5 text-sm text-slate-600 dark:text-slate-300 font-bold">
                      {typeof v === "number" ? v.toLocaleString() : (v ?? "—")}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}