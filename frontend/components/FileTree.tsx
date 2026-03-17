"use client";

import { useState } from "react";
import type { FileEntry } from "@/lib/types";

interface FileTreeProps {
  files: FileEntry[];
  selectedPath: string | null;
  onSelect: (path: string) => void;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}K`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}M`;
}

function formatDate(mtime: number): string {
  return new Date(mtime * 1000).toISOString().slice(0, 10);
}

function fileName(path: string): string {
  return path.split("/").pop() ?? path;
}

export default function FileTree({ files, selectedPath, onSelect }: FileTreeProps) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  // Filter to .wls files only
  const wlsFiles = files.filter((f) => f.path.endsWith(".wls"));

  if (wlsFiles.length === 0) {
    return <p className="text-xs text-gray-500 p-2">No .wls files yet</p>;
  }

  // Group by date (newest first)
  const byDate = new Map<string, FileEntry[]>();
  for (const f of wlsFiles) {
    const date = formatDate(f.modified);
    if (!byDate.has(date)) byDate.set(date, []);
    byDate.get(date)!.push(f);
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
              .sort((a, b) => b.modified - a.modified)
              .map((f) => (
                <button
                  key={f.path}
                  onClick={() => onSelect(f.path)}
                  className={`w-full text-left px-3 pl-5 py-1 text-xs flex justify-between rounded transition-colors ${
                    selectedPath === f.path
                      ? "bg-gray-800 text-gray-100"
                      : "text-gray-400 hover:bg-gray-800/50"
                  }`}
                >
                  <span className="truncate">{fileName(f.path)}</span>
                  <span className="text-gray-600 ml-2 flex-shrink-0">
                    {formatSize(f.size)}
                  </span>
                </button>
              ))}
        </div>
      ))}
    </div>
  );
}
