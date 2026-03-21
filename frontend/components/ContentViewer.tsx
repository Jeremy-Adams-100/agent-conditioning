"use client";

import dynamic from "next/dynamic";

// Lazy-load MarkdownViewer only when needed (keeps bundle small for non-markdown pages)
const MarkdownViewer = dynamic(() => import("./MarkdownViewer"), { ssr: false });

interface ContentViewerProps {
  title: string;
  content: string;
  type: "session" | "file";
  downloadUrl?: string;
  renderMarkdown?: boolean;
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

export default function ContentViewer({ title, content, type, downloadUrl, renderMarkdown }: ContentViewerProps) {
  const filename = title.split("/").pop() ?? title;
  const isPdf = filename.endsWith(".pdf");
  const isImage = filename.endsWith(".png") || filename.endsWith(".jpg") || filename.endsWith(".jpeg");
  const isBinary = (isPdf || isImage) && !!downloadUrl;
  const isMd = renderMarkdown && (filename.endsWith(".md") || type === "session");

  return (
    <div className="h-full flex flex-col">
      <div className="px-4 py-2 border-b border-gray-800 flex-shrink-0 flex items-center justify-between">
        <div>
          <span className="text-xs text-gray-500 uppercase tracking-wide">{type}</span>
          <h2 className="text-sm font-medium text-gray-200 truncate">{title}</h2>
        </div>
        {type === "file" && (
          isBinary ? (
            <a
              href={downloadUrl}
              download={filename}
              className="text-xs text-gray-400 border border-gray-700 rounded px-2 py-1 hover:text-gray-200 hover:border-gray-500 transition-colors"
            >
              Download
            </a>
          ) : (
            <button
              onClick={() => downloadFile(filename, content)}
              className="text-xs text-gray-400 border border-gray-700 rounded px-2 py-1 hover:text-gray-200 hover:border-gray-500 transition-colors"
            >
              Download
            </button>
          )
        )}
      </div>
      {isPdf && downloadUrl ? (
        <embed
          src={downloadUrl}
          type="application/pdf"
          className="flex-1 w-full"
        />
      ) : isImage && downloadUrl ? (
        <div className="flex-1 overflow-auto p-4 flex items-start justify-center bg-gray-900">
          <img src={downloadUrl} alt={filename} className="max-w-full" />
        </div>
      ) : isMd ? (
        <MarkdownViewer content={content} />
      ) : (
        <pre className="flex-1 overflow-auto p-4 text-sm text-gray-300 font-mono whitespace-pre-wrap">
          {content}
        </pre>
      )}
    </div>
  );
}
