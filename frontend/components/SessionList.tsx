"use client";

import type { SessionEntry } from "@/lib/types";

interface SessionListProps {
  sessions: SessionEntry[];
  selectedId: string | null;
  onSelect: (session: SessionEntry) => void;
}

const PHILOSOPHY_LABELS: Record<string, string> = {
  research: "researcher",
  efficient: "worker",
  audit: "auditor",
};

export default function SessionList({ sessions, selectedId, onSelect }: SessionListProps) {
  const byCycle = new Map<number, SessionEntry[]>();
  for (const s of sessions) {
    const cycle = s.depth ?? 0;
    if (!byCycle.has(cycle)) byCycle.set(cycle, []);
    byCycle.get(cycle)!.push(s);
  }
  const cycles = [...byCycle.keys()].sort((a, b) => b - a);

  if (cycles.length === 0) {
    return <p className="text-xs text-gray-500 p-2">No sessions yet</p>;
  }

  return (
    <div className="text-sm">
      {cycles.map((cycle) => (
        <div key={cycle} className="mb-1">
          <div className="px-2 py-1 text-xs font-medium text-gray-500">Cycle {cycle}</div>
          {byCycle.get(cycle)!.map((s) => (
            <button
              key={s.id}
              onClick={() => onSelect(s)}
              className={`w-full text-left px-3 py-1 text-xs rounded transition-colors ${
                selectedId === s.id
                  ? "bg-gray-800 text-gray-100"
                  : "text-gray-400 hover:bg-gray-800/50"
              }`}
            >
              {PHILOSOPHY_LABELS[s.philosophy ?? ""] ?? s.philosophy ?? "agent"}
              {s.record_type === "compaction" && (
                <span className="ml-1 text-gray-600">(compacted)</span>
              )}
            </button>
          ))}
        </div>
      ))}
    </div>
  );
}
