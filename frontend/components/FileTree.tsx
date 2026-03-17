"use client";

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

export default function FileTree({
  files,
  selectedPath,
  onSelect,
}: FileTreeProps) {
  if (files.length === 0) {
    return <p className="text-xs text-gray-400 p-2">No files yet</p>;
  }

  const sorted = [...files].sort((a, b) => a.path.localeCompare(b.path));

  return (
    <div className="text-sm">
      {sorted.map((f) => (
        <button
          key={f.path}
          onClick={() => onSelect(f.path)}
          className={`w-full text-left px-3 py-1 text-xs flex justify-between rounded transition-colors ${
            selectedPath === f.path
              ? "bg-gray-100 text-gray-900"
              : "text-gray-600 hover:bg-gray-50"
          }`}
        >
          <span className="truncate">{f.path}</span>
          <span className="text-gray-400 ml-2 flex-shrink-0">
            {formatSize(f.size)}
          </span>
        </button>
      ))}
    </div>
  );
}
