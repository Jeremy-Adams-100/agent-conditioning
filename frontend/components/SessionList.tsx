"use client";

import type { SessionEntry } from "@/lib/types";

interface SessionListProps {
  sessions: SessionEntry[];
  selectedId: string | null;
  onSelect: (session: SessionEntry) => void;
}

function formatSessionName(s: SessionEntry): string {
  // Format: "2026-03-17 19:34_topic" or "2026-03-17 19:34" if no topic
  const date = s.created_at?.slice(0, 16).replace("T", " ") ?? "unknown";
  if (s.topic) return `${date}_${s.topic}`;
  return date;
}

export default function SessionList({ sessions, selectedId, onSelect }: SessionListProps) {
  if (sessions.length === 0) {
    return <p className="text-xs text-gray-500 p-2">No sessions yet</p>;
  }

  // Sort by created_at descending (newest first)
  const sorted = [...sessions].sort((a, b) =>
    (b.created_at ?? "").localeCompare(a.created_at ?? "")
  );

  return (
    <div className="text-sm">
      {sorted.map((s) => (
        <button
          key={s.id}
          onClick={() => onSelect(s)}
          className={`w-full text-left px-3 py-1.5 text-xs rounded transition-colors truncate ${
            selectedId === s.id
              ? "bg-gray-800 text-gray-100"
              : "text-gray-400 hover:bg-gray-800/50"
          }`}
        >
          {formatSessionName(s)}
        </button>
      ))}
    </div>
  );
}
