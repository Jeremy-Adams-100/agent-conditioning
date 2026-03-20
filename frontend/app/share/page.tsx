"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  getOnboardStatus,
  checkTier,
  getSharePackages,
  installSharePackage,
  resetSharePackage,
  getFiles,
  getShareDocs,
  getShareDoc,
  getShareDocPdfUrl,
  type SharePackage,
} from "@/lib/api";
import NavTabs from "@/components/NavTabs";

type DocFile = { path: string; size: number };

export default function SharePage() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [tier, setTier] = useState("unknown");
  const [packages, setPackages] = useState<SharePackage[]>([]);
  const [installed, setInstalled] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState<string | null>(null);
  const [message, setMessage] = useState<{ text: string; error: boolean } | null>(null);

  // Docs viewer state
  const [docsPackage, setDocsPackage] = useState<SharePackage | null>(null);
  const [docFiles, setDocFiles] = useState<DocFile[]>([]);
  const [viewingDoc, setViewingDoc] = useState<{ path: string; content: string; isPdf: boolean } | null>(null);

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

  // Load packages and check installed status
  useEffect(() => {
    if (!ready) return;
    getSharePackages()
      .then(setPackages)
      .catch(() => setPackages([]));
    refreshInstalled();
  }, [ready]);

  function refreshInstalled() {
    getFiles()
      .then((files) => {
        const dirs = new Set(files.map((f) => f.path.split("/")[0]));
        setInstalled(dirs);
      })
      .catch(() => setInstalled(new Set()));
  }

  async function handleInstall(pkgId: string) {
    setLoading(pkgId);
    setMessage(null);
    try {
      await installSharePackage(pkgId);
      setMessage({ text: "Package installed. Check the Explore tab to see the files.", error: false });
      refreshInstalled();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Install failed";
      setMessage({ text: msg, error: true });
    } finally {
      setLoading(null);
    }
  }

  async function handleReset(pkgId: string) {
    setLoading(pkgId);
    setMessage(null);
    try {
      await resetSharePackage(pkgId);
      setMessage({ text: "Package removed.", error: false });
      refreshInstalled();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Reset failed";
      setMessage({ text: msg, error: true });
    } finally {
      setLoading(null);
    }
  }

  async function handleReadDocs(pkg: SharePackage) {
    setDocsPackage(pkg);
    setViewingDoc(null);
    try {
      const files = await getShareDocs(pkg.id);
      setDocFiles(files);
    } catch {
      setDocFiles([]);
    }
  }

  async function handleViewDoc(path: string) {
    if (!docsPackage) return;
    if (path.endsWith(".pdf")) {
      setViewingDoc({ path, content: "", isPdf: true });
    } else {
      try {
        const doc = await getShareDoc(docsPackage.id, path);
        setViewingDoc({ path, content: doc.content, isPdf: false });
      } catch {
        setViewingDoc({ path, content: "(failed to load)", isPdf: false });
      }
    }
  }

  function closeDocs() {
    setDocsPackage(null);
    setDocFiles([]);
    setViewingDoc(null);
  }

  if (!ready) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-gray-400">Loading...</p>
      </div>
    );
  }

  // Docs viewer mode
  if (docsPackage) {
    const fileName = (p: string) => p.split("/").pop() ?? p;
    const reports = docFiles.filter((f) => f.path.endsWith(".pdf") || f.path.endsWith(".md"));
    const scripts = docFiles.filter((f) => f.path.endsWith(".wls"));

    return (
      <div className="h-screen flex flex-col">
        <header className="flex items-center gap-2 md:gap-4 px-3 md:px-4 py-2 md:py-3 border-b border-gray-800 flex-shrink-0">
          <span className="font-bold text-sm tracking-tight">Q.E.D.</span>
          <NavTabs current="share" />
          <div className="flex-1" />
          <button
            onClick={closeDocs}
            className="text-xs text-gray-400 border border-gray-700 rounded px-2 py-1 hover:text-gray-200 hover:border-gray-500 transition-colors"
          >
            Back to packages
          </button>
        </header>

        <div className="flex flex-1 overflow-hidden">
          {/* File sidebar */}
          <aside className="w-64 border-r border-gray-800 flex flex-col overflow-hidden flex-shrink-0">
            <div className="px-3 py-2 border-b border-gray-800">
              <h2 className="text-xs font-medium text-gray-200">{docsPackage.name}</h2>
              <p className="text-xs text-gray-500 mt-0.5">Read-only preview</p>
            </div>
            <div className="flex-1 overflow-y-auto">
              {reports.length > 0 && (
                <div className="px-2 pt-2">
                  <p className="text-xs font-medium text-gray-500 px-1 mb-1">Reports</p>
                  {reports.map((f) => (
                    <button
                      key={f.path}
                      onClick={() => handleViewDoc(f.path)}
                      className={`w-full text-left px-2 py-1 text-xs rounded transition-colors ${
                        viewingDoc?.path === f.path
                          ? "bg-gray-800 text-gray-100"
                          : "text-gray-400 hover:bg-gray-800/50"
                      }`}
                    >
                      {fileName(f.path)}
                    </button>
                  ))}
                </div>
              )}
              {scripts.length > 0 && (
                <div className="px-2 pt-2">
                  <p className="text-xs font-medium text-gray-500 px-1 mb-1">Scripts</p>
                  {scripts.map((f) => (
                    <button
                      key={f.path}
                      onClick={() => handleViewDoc(f.path)}
                      className={`w-full text-left px-2 py-1 text-xs rounded transition-colors ${
                        viewingDoc?.path === f.path
                          ? "bg-gray-800 text-gray-100"
                          : "text-gray-400 hover:bg-gray-800/50"
                      }`}
                    >
                      {fileName(f.path)}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </aside>

          {/* Content viewer */}
          <main className="flex-1 flex flex-col overflow-hidden">
            {viewingDoc ? (
              <>
                <div className="px-4 py-2 border-b border-gray-800">
                  <span className="text-xs text-gray-400">{viewingDoc.path}</span>
                </div>
                {viewingDoc.isPdf ? (
                  <embed
                    src={getShareDocPdfUrl(docsPackage.id, viewingDoc.path)}
                    type="application/pdf"
                    className="flex-1 w-full"
                  />
                ) : (
                  <pre className="flex-1 overflow-auto p-4 text-sm text-gray-300 font-mono whitespace-pre-wrap">
                    {viewingDoc.content}
                  </pre>
                )}
              </>
            ) : (
              <div className="flex-1 flex items-center justify-center text-gray-500 text-sm">
                Select a file to preview
              </div>
            )}
          </main>
        </div>
      </div>
    );
  }

  // Package list mode
  return (
    <div className="h-screen flex flex-col">
      <header className="flex items-center gap-2 md:gap-4 px-3 md:px-4 py-2 md:py-3 border-b border-gray-800 flex-shrink-0">
        <span className="font-bold text-sm tracking-tight">Q.E.D.</span>
        <NavTabs current="share" />
        <div className="flex-1" />
        <div className="hidden md:flex items-center gap-2">
          <span className="text-xs text-gray-500 border border-gray-700 rounded px-2 py-0.5">
            {tier === "max" ? "Max" : "Free"}
          </span>
        </div>
      </header>

      {message && (
        <div className={`px-4 py-2 text-xs flex-shrink-0 ${
          message.error
            ? "bg-red-950 border-b border-red-800 text-red-300"
            : "bg-emerald-950 border-b border-emerald-800 text-emerald-300"
        }`}>
          {message.text}
        </div>
      )}

      <main className="flex-1 overflow-y-auto p-6 md:p-8">
        <div className="max-w-2xl mx-auto">
          <h1 className="text-lg font-medium text-gray-100 mb-1">Shared Packages</h1>
          <p className="text-xs text-gray-500 mb-6">
            Pre-built exploration results you can install into your workspace and build on.
          </p>

          {packages.length === 0 && (
            <p className="text-sm text-gray-500">No packages available yet.</p>
          )}

          <div className="space-y-4">
            {packages.map((pkg) => {
              const isInstalled = installed.has(pkg.topic_dir);
              const isLoading = loading === pkg.id;

              return (
                <div
                  key={pkg.id}
                  className="border border-gray-800 rounded-lg p-4"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <h2 className="text-sm font-medium text-gray-100">{pkg.name}</h2>
                        {isInstalled && (
                          <span className="text-xs bg-emerald-900 text-emerald-300 px-1.5 py-0.5 rounded">
                            Installed
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-gray-400 mt-1">{pkg.description}</p>
                      <div className="flex gap-4 mt-2 text-xs text-gray-500">
                        <span>{pkg.size_mb} MB</span>
                        <span>{pkg.cycles} cycles</span>
                        <span>{pkg.created}</span>
                        <button
                          onClick={() => handleReadDocs(pkg)}
                          className="text-gray-400 hover:text-gray-200 underline"
                        >
                          Read the docs
                        </button>
                      </div>
                    </div>
                    <div className="flex gap-2 flex-shrink-0">
                      {!isInstalled ? (
                        <button
                          onClick={() => handleInstall(pkg.id)}
                          disabled={isLoading}
                          className="px-3 py-1.5 bg-white text-gray-900 text-xs rounded-lg font-medium hover:bg-gray-200 disabled:opacity-50 transition-colors"
                        >
                          {isLoading ? "..." : "Install"}
                        </button>
                      ) : (
                        <button
                          onClick={() => handleReset(pkg.id)}
                          disabled={isLoading}
                          className="px-3 py-1.5 border border-red-700 text-red-400 text-xs rounded-lg hover:bg-red-950 disabled:opacity-50 transition-colors"
                        >
                          {isLoading ? "..." : "Reset"}
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </main>
    </div>
  );
}
