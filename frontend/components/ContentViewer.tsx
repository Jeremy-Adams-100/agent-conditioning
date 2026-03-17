"use client";

interface ContentViewerProps {
  title: string;
  content: string;
  type: "session" | "file";
}

export default function ContentViewer({
  title,
  content,
  type,
}: ContentViewerProps) {
  return (
    <div className="h-full flex flex-col">
      <div className="px-4 py-2 border-b border-gray-200 flex-shrink-0">
        <span className="text-xs text-gray-400 uppercase tracking-wide">
          {type}
        </span>
        <h2 className="text-sm font-medium truncate">{title}</h2>
      </div>
      <pre className="flex-1 overflow-auto p-4 text-sm text-gray-700 font-mono whitespace-pre-wrap">
        {content}
      </pre>
    </div>
  );
}
