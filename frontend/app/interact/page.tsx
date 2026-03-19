"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  getOnboardStatus,
  checkTier,
  interactQuery,
  interactClear,
  getInteractFile,
  getInteractFileDownloadUrl,
} from "@/lib/api";
import { useInteractFiles } from "@/lib/hooks";
import NavTabs from "@/components/NavTabs";
import FileTree from "@/components/FileTree";
import ContentViewer from "@/components/ContentViewer";

type Message = { role: "user" | "assistant"; content: string };

type ViewItem =
  | { type: "file"; path: string; title: string; content: string; downloadUrl?: string }
  | null;

const MAX_PROMPT_LENGTH = 10000;

export default function InteractPage() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [tier, setTier] = useState("unknown");
  const [messages, setMessages] = useState<Message[]>([]);
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [contextWarning, setContextWarning] = useState<string | null>(null);
  const [sidebarTab, setSidebarTab] = useState<"logs" | "files" | "reports">("logs");
  const [mobilePanel, setMobilePanel] = useState<"content" | "sidebar">("content");
  const [viewing, setViewing] = useState<ViewItem>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const { data: files = [], mutate: refreshFiles } = useInteractFiles();

  // Auth + tier check
  useEffect(() => {
    getOnboardStatus()
      .then((s) => {
        if (!s.onboarding_complete) router.push("/onboard");
        else {
          setReady(true);
          if (s.tier === "unknown" || !s.tier) {
            checkTier()
              .then((t) => setTier(t.tier))
              .catch(() => setTier("free"));
          } else {
            setTier(s.tier);
          }
        }
      })
      .catch(() => router.push("/login"));
  }, [router]);

  // Auto-scroll on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    const lineHeight = 20;
    const oneLine = lineHeight + 12;
    const fourLines = lineHeight * 4 + 12;
    const scrollHeight = el.scrollHeight;
    if (scrollHeight <= oneLine) {
      el.style.height = oneLine + "px";
      el.style.overflowY = "hidden";
    } else if (scrollHeight <= fourLines) {
      el.style.height = fourLines + "px";
      el.style.overflowY = "hidden";
    } else {
      el.style.height = fourLines + "px";
      el.style.overflowY = "auto";
    }
  }, [prompt]);

  async function handleQuery() {
    if (!prompt.trim() || loading) return;
    const userPrompt = prompt;
    setPrompt("");
    setLoading(true);
    setError(null);
    setMessages((prev) => [...prev, { role: "user", content: userPrompt }]);

    try {
      const res = await interactQuery(userPrompt);
      if (res.error) {
        setError(res.message || "An error occurred.");
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: `Error: ${res.message || res.error}` },
        ]);
      } else {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: res.result || "(empty response)" },
        ]);
      }
      setContextWarning(res.context_warning ?? null);
      refreshFiles();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Query failed";
      setError(msg);
      setMessages((prev) => [...prev, { role: "assistant", content: `Error: ${msg}` }]);
    } finally {
      setLoading(false);
    }
  }

  async function handleClear() {
    try {
      await interactClear();
    } catch {
      // best effort
    }
    setMessages([]);
    setError(null);
    setContextWarning(null);
    setViewing(null);
    refreshFiles();
  }

  async function handleSelectFile(path: string) {
    if (path.endsWith(".pdf")) {
      setViewing({
        type: "file", path, title: path, content: "",
        downloadUrl: getInteractFileDownloadUrl(path),
      });
      return;
    }
    try {
      const f = await getInteractFile(path);
      setViewing({ type: "file", path, title: path, content: f.content });
    } catch {
      setViewing({ type: "file", path, title: path, content: "(failed to load)" });
    }
  }

  if (!ready) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-gray-400">Loading...</p>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col">
      {/* Top bar — prompt bar in header, matching explore page layout */}
      <header className="flex items-center gap-2 md:gap-4 px-3 md:px-4 py-2 md:py-3 border-b border-gray-800 flex-shrink-0">
        <span className="font-bold text-sm tracking-tight">Q.E.D.</span>
        <NavTabs current="interact" />
        <div className="flex-1 min-w-0 flex items-start gap-2">
          <textarea
            ref={textareaRef}
            placeholder="Ask a question or run a computation..."
            value={prompt}
            maxLength={MAX_PROMPT_LENGTH}
            rows={1}
            disabled={loading}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && prompt.trim() && !loading) {
                e.preventDefault();
                handleQuery();
              }
            }}
            className="flex-1 px-3 py-1.5 bg-gray-900 border border-gray-700 rounded-lg text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-gray-400 resize-none leading-5 disabled:opacity-40"
          />
          <button
            onClick={handleQuery}
            disabled={!prompt.trim() || loading}
            className="px-4 py-1.5 bg-white text-gray-900 text-sm rounded-lg font-medium hover:bg-gray-200 disabled:opacity-50 transition-colors"
          >
            {loading ? "..." : "Go"}
          </button>
          <button
            onClick={handleClear}
            disabled={loading}
            className="px-3 py-1.5 text-gray-500 text-sm hover:text-gray-300 transition-colors disabled:opacity-30"
          >
            Clear
          </button>
        </div>
        <div className="hidden md:flex items-center gap-2">
          <span className="text-xs text-gray-500 border border-gray-700 rounded px-2 py-0.5">
            {tier === "max" ? "Max" : "Free"}
          </span>
        </div>
      </header>

      {/* Context warning banner */}
      {contextWarning && (
        <div className="px-4 py-2 bg-yellow-950 border-b border-yellow-800 text-xs text-yellow-300 flex-shrink-0">
          {contextWarning}
        </div>
      )}

      {/* Error banner */}
      {error && (
        <div className="px-4 py-2 bg-red-950 border-b border-red-800 text-xs text-red-300 flex-shrink-0">
          {error}
        </div>
      )}

      {/* Main content */}
      <div className="flex flex-col md:flex-row flex-1 overflow-hidden">
        {/* Sidebar */}
        <aside className={`${mobilePanel === "sidebar" ? "flex" : "hidden"} md:flex w-full md:w-64 border-r border-gray-800 flex-col flex-shrink-0 overflow-hidden`}>
          <div className="flex border-b border-gray-800">
            {(["logs", "files", "reports"] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => { setSidebarTab(tab); refreshFiles(); }}
                className={`flex-1 px-3 py-2 text-xs font-medium transition-colors ${
                  sidebarTab === tab
                    ? "text-gray-100 border-b-2 border-gray-100"
                    : "text-gray-400 hover:text-gray-300"
                }`}
              >
                {tab === "logs" ? "Logs" : tab === "files" ? "Files" : "Reports"}
              </button>
            ))}
          </div>
          <div className="flex-1 overflow-y-auto">
            {sidebarTab === "logs" && (
              <FileTree
                files={files}
                selectedPath={viewing?.path ?? null}
                onSelect={handleSelectFile}
                extensions={[".md"]}
                emptyMessage="No logs yet"
              />
            )}
            {sidebarTab === "files" && (
              <FileTree
                files={files}
                selectedPath={viewing?.path ?? null}
                onSelect={handleSelectFile}
                extensions={[".wls"]}
                emptyMessage="No .wls files yet"
              />
            )}
            {sidebarTab === "reports" && (
              <FileTree
                files={files}
                selectedPath={viewing?.path ?? null}
                onSelect={handleSelectFile}
                extensions={[".pdf"]}
                emptyMessage="No reports yet"
              />
            )}
          </div>
        </aside>

        {/* Main area */}
        <main className={`${mobilePanel === "content" ? "flex" : "hidden"} md:flex flex-1 flex-col overflow-hidden`}>
          {viewing ? (
            <>
              <div className="px-4 py-2 border-b border-gray-800 flex items-center justify-between">
                <span className="text-xs text-gray-400 truncate">{viewing.title}</span>
                <button
                  onClick={() => setViewing(null)}
                  className="text-xs text-gray-500 hover:text-gray-300 ml-2"
                >
                  Back to chat
                </button>
              </div>
              <ContentViewer
                title={viewing.title}
                content={viewing.content}
                type="file"
                downloadUrl={viewing.downloadUrl}
              />
            </>
          ) : (
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.length === 0 && !loading && (
                <div className="h-full flex items-center justify-center text-gray-500 text-sm">
                  Ask a question or run a computation
                </div>
              )}
              {messages.map((msg, i) => (
                <div key={i} className={`${msg.role === "user" ? "text-gray-300" : "text-gray-100"}`}>
                  <span className="text-xs text-gray-500 font-medium uppercase">
                    {msg.role === "user" ? "You" : "Assistant"}
                  </span>
                  <pre className="mt-1 text-sm whitespace-pre-wrap font-mono leading-relaxed">
                    {msg.content}
                  </pre>
                </div>
              ))}
              {loading && (
                <div className="flex items-center gap-2 text-gray-400 text-sm">
                  <div className="w-4 h-4 border-2 border-gray-700 border-t-gray-300 rounded-full animate-spin" />
                  Working...
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </main>
      </div>

      {/* Mobile bottom tab bar */}
      <nav className="md:hidden flex border-t border-gray-800 flex-shrink-0">
        <button
          onClick={() => setMobilePanel("content")}
          className={`flex-1 py-2 text-xs font-medium ${
            mobilePanel === "content" ? "text-gray-100" : "text-gray-400"
          }`}
        >
          Chat
        </button>
        {(["logs", "files", "reports"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => { setMobilePanel("sidebar"); setSidebarTab(tab); refreshFiles(); }}
            className={`flex-1 py-2 text-xs font-medium ${
              mobilePanel === "sidebar" && sidebarTab === tab ? "text-gray-100" : "text-gray-400"
            }`}
          >
            {tab === "logs" ? "Logs" : tab === "files" ? "Files" : "Reports"}
          </button>
        ))}
      </nav>
    </div>
  );
}
