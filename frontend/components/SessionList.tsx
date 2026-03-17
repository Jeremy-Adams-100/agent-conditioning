"use client";

import type { SessionEntry } from "@/lib/types";

interface SessionListProps {
  sessions: SessionEntry[];
  selectedId: string | null;
  onSelect: (session: SessionEntry) => void;
}

function formatSessionName(s: SessionEntry): string {
  // Format: "19:34 researcher — Topic Name" or "19:34 researcher" if no topic
  const time = s.created_at?.slice(11, 16) ?? "";
  const agent = s.keywords ?? "";  // agent name stored as keyword
  const label = agent ? `${time} ${agent}` : time;
  if (s.topic) return `${label} — ${s.topic}`;
  return label || (s.created_at?.slice(0, 16).replace("T", " ") ?? "session");
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
