"use client";

import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";

interface MarkdownViewerProps {
  content: string;
}

// Escape non-standard XML tags so react-markdown doesn't swallow them.
// Wraps <tag>...</tag> blocks in fenced code blocks for readable display.
const XML_BLOCK_RE = /^(<(?!\/)([\w-]+)[^>]*>)\n([\s\S]*?)^(<\/\2>)/gm;

function escapeXmlBlocks(text: string): string {
  return text.replace(XML_BLOCK_RE, "```xml\n$1\n$3$4\n```");
}

export default function MarkdownViewer({ content }: MarkdownViewerProps) {
  return (
    <div className="p-4 overflow-auto flex-1 text-sm text-gray-300 leading-relaxed [&_h1]:text-lg [&_h1]:font-bold [&_h1]:text-gray-100 [&_h1]:mt-4 [&_h1]:mb-2 [&_h2]:text-base [&_h2]:font-semibold [&_h2]:text-gray-200 [&_h2]:mt-3 [&_h2]:mb-1 [&_h3]:text-sm [&_h3]:font-semibold [&_h3]:text-gray-200 [&_h3]:mt-2 [&_h3]:mb-1 [&_p]:mb-2 [&_code]:bg-gray-800 [&_code]:px-1 [&_code]:rounded [&_code]:text-xs [&_code]:font-mono [&_pre]:bg-gray-900 [&_pre]:p-3 [&_pre]:rounded [&_pre]:overflow-x-auto [&_pre]:mb-2 [&_pre_code]:bg-transparent [&_pre_code]:px-0 [&_hr]:border-gray-700 [&_hr]:my-4 [&_strong]:text-gray-100 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:mb-2 [&_ol]:list-decimal [&_ol]:pl-5 [&_ol]:mb-2 [&_li]:mb-0.5 [&_table]:border-collapse [&_table]:text-xs [&_th]:border [&_th]:border-gray-700 [&_th]:px-2 [&_th]:py-1 [&_th]:text-left [&_td]:border [&_td]:border-gray-700 [&_td]:px-2 [&_td]:py-1 [&_blockquote]:border-l-2 [&_blockquote]:border-gray-600 [&_blockquote]:pl-3 [&_blockquote]:text-gray-400">
      <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
        {escapeXmlBlocks(content)}
      </ReactMarkdown>
    </div>
  );
}
