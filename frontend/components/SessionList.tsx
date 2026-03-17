"use client";

import { useState } from "react";
import type { SessionEntry } from "@/lib/types";

interface SessionListProps {
  sessions: SessionEntry[];
  selectedId: string | null;
  onSelect: (session: SessionEntry) => void;
}

function formatSessionName(s: SessionEntry): string {
  const agent = s.keywords ?? "agent";
  if (s.topic) return `${agent} — ${s.topic}`;
  return agent;
}

function formatDate(created_at: string): string {
  return created_at?.slice(0, 10) ?? "unknown";
}

export default function SessionList({ sessions, selectedId, onSelect }: SessionListProps) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  if (sessions.length === 0) {
    return <p className="text-xs text-gray-500 p-2">No sessions yet</p>;
  }

  // Group by date (newest first)
  const byDate = new Map<string, SessionEntry[]>();
  for (const s of sessions) {
    const date = formatDate(s.created_at);
    if (!byDate.has(date)) byDate.set(date, []);
    byDate.get(date)!.push(s);
  }
  const dates = [...byDate.keys()].sort().reverse();

  function toggleDate(date: string) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(date)) next.delete(date);
      else next.add(date);
      return next;
    });
  }

  return (
    <div className="text-sm">
      {dates.map((date) => (
        <div key={date} className="mb-1">
          <button
            onClick={() => toggleDate(date)}
            className="w-full text-left px-2 py-1 text-xs font-medium text-gray-500 hover:text-gray-300 flex items-center gap-1"
          >
            <span className={`transition-transform ${collapsed.has(date) ? "" : "rotate-90"}`}>
              ▸
            </span>
            {date}
            <span className="text-gray-600 ml-1">({byDate.get(date)!.length})</span>
          </button>
          {!collapsed.has(date) &&
            byDate.get(date)!
              .sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""))
              .map((s) => (
                <button
                  key={s.id}
                  onClick={() => onSelect(s)}
                  className={`w-full text-left px-3 pl-5 py-1 text-xs rounded transition-colors truncate ${
                    selectedId === s.id
                      ? "bg-gray-800 text-gray-100"
                      : "text-gray-400 hover:bg-gray-800/50"
                  }`}
                >
                  {formatSessionName(s)}
                </button>
              ))}
        </div>
      ))}
    </div>
  );
}
