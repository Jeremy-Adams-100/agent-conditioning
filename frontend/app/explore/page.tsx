"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { getOnboardStatus, getSession, getFile, getFileDownloadUrl, checkTier } from "@/lib/api";
import { useExplorationStatus, useSessions, useFiles } from "@/lib/hooks";
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

  const isRunning = status?.exploration_running ?? false;
  const hasCycles = (status?.state?.cycle ?? 0) > 0;
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
              Files
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
              />
            )}
            {sidebarTab === "reports" && (
              <FileTree
                files={files}
                selectedPath={viewing?.type === "file" ? viewing.path : null}
                onSelect={handleSelectFile}
                extensions={[".pdf"]}
                emptyMessage="No reports yet"
              />
            )}
          </div>
        </aside>

        {/* Content — hidden on mobile when sidebar is shown */}
        <main className={`${mobilePanel === "content" ? "flex" : "hidden"} md:flex flex-1 flex-col overflow-hidden`}>
          {viewing ? (
            <ContentViewer
              title={viewing.title}
              content={viewing.content}
              type={viewing.type}
              downloadUrl={viewing.type === "file" ? viewing.downloadUrl : undefined}
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
          Files
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
