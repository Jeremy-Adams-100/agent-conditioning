"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { getOnboardStatus, getSession, getFile, getFileDownloadUrl, checkTier } from "@/lib/api";
import { useExplorationStatus, useSessions, useFiles, usePrintOutput } from "@/lib/hooks";
import StatusBar from "@/components/StatusBar";
import Controls from "@/components/Controls";
import SessionList from "@/components/SessionList";
import FileTree from "@/components/FileTree";
import ContentViewer from "@/components/ContentViewer";
import NavTabs from "@/components/NavTabs";
import type { SessionEntry } from "@/lib/types";

type ViewItem =
  | { type: "session"; id: string; title: string; content: string }
  | { type: "file"; path: string; title: string; content: string; downloadUrl?: string }
  | null;

export default function ExplorePage() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [tier, setTier] = useState("unknown");
  const [viewing, setViewing] = useState<ViewItem>(null);
  const [sidebarTab, setSidebarTab] = useState<"logs" | "files" | "reports">("logs");
  const [mobilePanel, setMobilePanel] = useState<"content" | "sidebar">("content");
  const [logsCollapsed, setLogsCollapsed] = useState<Set<string>>(new Set());
  const [filesCollapsed, setFilesCollapsed] = useState<Set<string>>(new Set());
  const [reportsCollapsed, setReportsCollapsed] = useState<Set<string>>(new Set());

  // Check auth + onboarding, detect tier if unknown
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

  const { data: status, mutate: refreshStatus } = useExplorationStatus(ready);
  const { data: sessions = [], mutate: refreshSessions } = useSessions();
  const { data: files = [], mutate: refreshFiles } = useFiles();
  const { data: printData } = usePrintOutput(ready);

  const isRunning = status?.exploration_running ?? false;
  const hasCycles = (status?.state?.cycle ?? 0) > 0;

  // Print panel state
  const [printHeight, setPrintHeight] = useState(33); // percentage
  const printRef = useRef<HTMLPreElement>(null);
  const dragging = useRef(false);
  const mainRef = useRef<HTMLDivElement>(null);

  // Auto-scroll print panel only if user is at (or near) the bottom
  useEffect(() => {
    const el = printRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    if (atBottom) {
      el.scrollTop = el.scrollHeight;
    }
  }, [printData?.lines]);

  const handleDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragging.current = true;
    const onMove = (ev: MouseEvent) => {
      if (!dragging.current || !mainRef.current) return;
      const rect = mainRef.current.getBoundingClientRect();
      const pct = ((rect.bottom - ev.clientY) / rect.height) * 100;
      setPrintHeight(Math.max(10, Math.min(80, pct)));
    };
    const onUp = () => {
      dragging.current = false;
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }, []);
  const currentCycle = status?.state?.cycle ?? 0;

  async function handleSelectSession(session: SessionEntry) {
    try {
      const full = await getSession(session.id);
      setViewing({
        type: "session",
        id: session.id,
        title: `${session.created_at?.slice(0, 16).replace("T", " ") ?? ""}${session.topic ? "_" + session.topic : ""}`,
        content: full.summary_xml ?? "(empty)",
      });
    } catch {
      setViewing({
        type: "session",
        id: session.id,
        title: session.id,
        content: "(failed to load)",
      });
    }
  }

  async function handleSelectFile(path: string) {
    if (path.endsWith(".pdf")) {
      setViewing({
        type: "file", path, title: path, content: "",
        downloadUrl: getFileDownloadUrl(path),
      });
      return;
    }
    try {
      const f = await getFile(path);
      setViewing({ type: "file", path, title: path, content: f.content });
    } catch {
      setViewing({ type: "file", path, title: path, content: "(failed to load)" });
    }
  }

  const makeToggle = useCallback(
    (setter: React.Dispatch<React.SetStateAction<Set<string>>>) => (date: string) => {
      setter((prev) => {
        const next = new Set(prev);
        if (next.has(date)) next.delete(date);
        else next.add(date);
        return next;
      });
    },
    []
  );

  function handleAction() {
    refreshStatus();
    refreshSessions();
    refreshFiles();
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
      {/* Top bar */}
      <header className="flex items-center gap-2 md:gap-4 px-3 md:px-4 py-2 md:py-3 border-b border-gray-800 flex-shrink-0">
        <span className="font-bold text-sm tracking-tight">Q.E.D.</span>
        <NavTabs current="explore" />
        <div className="flex-1 min-w-0">
          <Controls
            isRunning={isRunning}
            hasCycles={hasCycles}
            currentCycle={currentCycle}
            onAction={handleAction}
          />
        </div>
        <div className="hidden md:flex items-center gap-2">
          <StatusBar status={status} />
          <span className="text-xs text-gray-500 border border-gray-700 rounded px-2 py-0.5">
            {tier === "max" ? "Max" : "Free"}
          </span>
          {tier !== "max" && (
            <a
              href="https://claude.com/pricing/max"
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-emerald-400 hover:underline"
            >
              Upgrade
            </a>
          )}
        </div>
      </header>

      {/* Main content */}
      <div className="flex flex-col md:flex-row flex-1 overflow-hidden">
        {/* Sidebar — hidden on mobile unless toggled */}
        <aside className={`${mobilePanel === "sidebar" ? "flex" : "hidden"} md:flex w-full md:w-64 border-r border-gray-800 flex-col flex-shrink-0 overflow-hidden`}>
          <div className="flex border-b border-gray-800">
            <button
              onClick={() => setSidebarTab("logs")}
              className={`flex-1 px-3 py-2 text-xs font-medium transition-colors ${
                sidebarTab === "logs"
                  ? "text-gray-100 border-b-2 border-gray-100"
                  : "text-gray-400 hover:text-gray-300"
              }`}
            >
              Logs
            </button>
            <button
              onClick={() => {
                setSidebarTab("files");
                refreshFiles();
              }}
              className={`flex-1 px-3 py-2 text-xs font-medium transition-colors ${
                sidebarTab === "files"
                  ? "text-gray-100 border-b-2 border-gray-100"
                  : "text-gray-400 hover:text-gray-300"
              }`}
            >
              Scripts
            </button>
            <button
              onClick={() => {
                setSidebarTab("reports");
                refreshFiles();
              }}
              className={`flex-1 px-3 py-2 text-xs font-medium transition-colors ${
                sidebarTab === "reports"
                  ? "text-gray-100 border-b-2 border-gray-100"
                  : "text-gray-400 hover:text-gray-300"
              }`}
            >
              Reports
            </button>
          </div>
          <div className="flex-1 overflow-y-auto">
            {sidebarTab === "logs" && (
              <SessionList
                sessions={sessions}
                selectedId={viewing?.type === "session" ? viewing.id : null}
                onSelect={handleSelectSession}
              />
            )}
            {sidebarTab === "files" && (
              <FileTree
                files={files}
                selectedPath={viewing?.type === "file" ? viewing.path : null}
                onSelect={handleSelectFile}
                extensions={[".wls"]}
                emptyMessage="No .wls files yet"
                collapsed={filesCollapsed}
                onToggleCollapsed={makeToggle(setFilesCollapsed)}
              />
            )}
            {sidebarTab === "reports" && (
              <FileTree
                files={files}
                selectedPath={viewing?.type === "file" ? viewing.path : null}
                onSelect={handleSelectFile}
                extensions={[".pdf"]}
                emptyMessage="No reports yet"
                collapsed={reportsCollapsed}
                onToggleCollapsed={makeToggle(setReportsCollapsed)}
              />
            )}
          </div>
        </aside>

        {/* Content + Print split — hidden on mobile when sidebar is shown */}
        <main ref={mainRef} className={`${mobilePanel === "content" ? "flex" : "hidden"} md:flex flex-1 flex-col overflow-hidden`}>
          {/* Content viewer (top) */}
          <div className="overflow-hidden" style={{ flex: `0 0 ${100 - printHeight}%` }}>
            {viewing ? (
              <ContentViewer
                title={viewing.title}
                content={viewing.content}
                type={viewing.type}
                downloadUrl={viewing.type === "file" ? viewing.downloadUrl : undefined}
                renderMarkdown
              />
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-gray-400 text-sm gap-2">
                {isRunning ? (
                  <>
                    <div className="inline-block w-5 h-5 border-2 border-gray-700 border-t-gray-300 rounded-full animate-spin" />
                    <p className="text-gray-300 font-medium">Exploring...</p>
                    {(status?.state?.cycle ?? 0) > 0 ? (
                      <p className="text-xs text-gray-500">
                        Cycle {status?.state?.cycle} in progress — select a session to view previous results
                      </p>
                    ) : (
                      <p className="text-xs text-gray-500 text-center max-w-xs">
                        Your research agents are working. First results appear in ~5-10 minutes.
                        This page updates automatically.
                      </p>
                    )}
                  </>
                ) : hasCycles ? (
                  "Select a log, file, or report to view"
                ) : (
                  "Type a topic and click Go to start exploring"
                )}
              </div>
            )}
          </div>

          {/* Drag bar */}
          <div
            onMouseDown={handleDragStart}
            className="h-1.5 bg-gray-800 hover:bg-gray-600 cursor-row-resize flex-shrink-0 flex items-center justify-center"
          >
            <div className="w-8 h-0.5 bg-gray-600 rounded" />
          </div>

          {/* Print panel (bottom) */}
          <div className="flex flex-col overflow-hidden" style={{ flex: `0 0 ${printHeight}%` }}>
            <div className="px-3 py-1 border-b border-gray-800 flex items-center gap-2 flex-shrink-0">
              <span className="text-xs font-medium text-gray-500">Print</span>
              {printData?.running && (
                <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse" />
              )}
            </div>
            <pre
              ref={printRef}
              className="flex-1 overflow-auto px-3 py-2 text-xs text-gray-400 font-mono whitespace-pre-wrap bg-gray-950 leading-relaxed"
            >
              {printData?.lines && printData.lines.length > 0
                ? printData.lines.join("\n")
                : "No exploration output."}
            </pre>
          </div>
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
          Content
        </button>
        <button
          onClick={() => { setMobilePanel("sidebar"); setSidebarTab("logs"); }}
          className={`flex-1 py-2 text-xs font-medium ${
            mobilePanel === "sidebar" && sidebarTab === "logs" ? "text-gray-100" : "text-gray-400"
          }`}
        >
          Logs
        </button>
        <button
          onClick={() => { setMobilePanel("sidebar"); setSidebarTab("files"); refreshFiles(); }}
          className={`flex-1 py-2 text-xs font-medium ${
            mobilePanel === "sidebar" && sidebarTab === "files" ? "text-gray-100" : "text-gray-400"
          }`}
        >
          Scripts
        </button>
        <button
          onClick={() => { setMobilePanel("sidebar"); setSidebarTab("reports"); refreshFiles(); }}
          className={`flex-1 py-2 text-xs font-medium ${
            mobilePanel === "sidebar" && sidebarTab === "reports" ? "text-gray-100" : "text-gray-400"
          }`}
        >
          Reports
        </button>
      </nav>
    </div>
  );
}
