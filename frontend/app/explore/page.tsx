"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { getOnboardStatus, getSession, getFile } from "@/lib/api";
import { useExplorationStatus, useSessions, useFiles } from "@/lib/hooks";
import StatusBar from "@/components/StatusBar";
import Controls from "@/components/Controls";
import SessionList from "@/components/SessionList";
import FileTree from "@/components/FileTree";
import ContentViewer from "@/components/ContentViewer";
import type { SessionEntry } from "@/lib/types";

type ViewItem =
  | { type: "session"; id: string; title: string; content: string }
  | { type: "file"; path: string; title: string; content: string }
  | null;

export default function ExplorePage() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [viewing, setViewing] = useState<ViewItem>(null);
  const [sidebarTab, setSidebarTab] = useState<"sessions" | "files">("sessions");

  // Check auth + onboarding
  useEffect(() => {
    getOnboardStatus()
      .then((s) => {
        if (!s.onboarding_complete) router.push("/onboard");
        else setReady(true);
      })
      .catch(() => router.push("/login"));
  }, [router]);

  const { data: status, mutate: refreshStatus } = useExplorationStatus(ready);
  const { data: sessions = [], mutate: refreshSessions } = useSessions();
  const { data: files = [], mutate: refreshFiles } = useFiles();

  const isRunning = status?.exploration_running ?? false;
  const hasCycles = (status?.state?.cycle ?? 0) > 0;

  async function handleSelectSession(session: SessionEntry) {
    try {
      const full = await getSession(session.id);
      setViewing({
        type: "session",
        id: session.id,
        title: `Cycle ${session.depth ?? "?"} — ${session.philosophy ?? "agent"}`,
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
      <header className="flex items-center gap-4 px-4 py-3 border-b border-gray-200 flex-shrink-0">
        <span className="font-bold text-sm tracking-tight">Q.E.D.</span>
        <div className="flex-1">
          <Controls
            isRunning={isRunning}
            hasCycles={hasCycles}
            onAction={handleAction}
          />
        </div>
        <StatusBar status={status} />
      </header>

      {/* Main content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left sidebar */}
        <aside className="w-64 border-r border-gray-200 flex flex-col flex-shrink-0 overflow-hidden">
          <div className="flex border-b border-gray-200">
            <button
              onClick={() => setSidebarTab("sessions")}
              className={`flex-1 px-3 py-2 text-xs font-medium transition-colors ${
                sidebarTab === "sessions"
                  ? "text-gray-900 border-b-2 border-gray-900"
                  : "text-gray-400 hover:text-gray-600"
              }`}
            >
              Sessions
            </button>
            <button
              onClick={() => {
                setSidebarTab("files");
                refreshFiles();
              }}
              className={`flex-1 px-3 py-2 text-xs font-medium transition-colors ${
                sidebarTab === "files"
                  ? "text-gray-900 border-b-2 border-gray-900"
                  : "text-gray-400 hover:text-gray-600"
              }`}
            >
              Files
            </button>
          </div>
          <div className="flex-1 overflow-y-auto">
            {sidebarTab === "sessions" && (
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
              />
            )}
          </div>
        </aside>

        {/* Right content */}
        <main className="flex-1 overflow-hidden">
          {viewing ? (
            <ContentViewer
              title={viewing.title}
              content={viewing.content}
              type={viewing.type}
            />
          ) : (
            <div className="h-full flex items-center justify-center text-gray-400 text-sm">
              {hasCycles
                ? "Select a session or file to view"
                : "Type a topic and click Go to start exploring"}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
