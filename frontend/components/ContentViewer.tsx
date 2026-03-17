"use client";

interface ContentViewerProps {
  title: string;
  content: string;
  type: "session" | "file";
}

function downloadFile(filename: string, content: string) {
  const blob = new Blob([content], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function ContentViewer({ title, content, type }: ContentViewerProps) {
  const filename = title.split("/").pop() ?? title;

  return (
    <div className="h-full flex flex-col">
      <div className="px-4 py-2 border-b border-gray-800 flex-shrink-0 flex items-center justify-between">
        <div>
          <span className="text-xs text-gray-500 uppercase tracking-wide">{type}</span>
          <h2 className="text-sm font-medium text-gray-200 truncate">{title}</h2>
        </div>
        {type === "file" && (
          <button
            onClick={() => downloadFile(filename, content)}
            className="text-xs text-gray-400 border border-gray-700 rounded px-2 py-1 hover:text-gray-200 hover:border-gray-500 transition-colors"
          >
            Download
          </button>
        )}
      </div>
      <pre className="flex-1 overflow-auto p-4 text-sm text-gray-300 font-mono whitespace-pre-wrap">
        {content}
      </pre>
    </div>
  );
}
