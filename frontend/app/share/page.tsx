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
  type SharePackage,
} from "@/lib/api";
import NavTabs from "@/components/NavTabs";

export default function SharePage() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [tier, setTier] = useState("unknown");
  const [packages, setPackages] = useState<SharePackage[]>([]);
  const [installed, setInstalled] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState<string | null>(null);
  const [message, setMessage] = useState<{ text: string; error: boolean } | null>(null);

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
        // A package is installed if its topic_dir appears as a directory prefix in the file list
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
        <NavTabs current="share" />
        <div className="flex-1" />
        <div className="hidden md:flex items-center gap-2">
          <span className="text-xs text-gray-500 border border-gray-700 rounded px-2 py-0.5">
            {tier === "max" ? "Max" : "Free"}
          </span>
        </div>
      </header>

      {/* Message banner */}
      {message && (
        <div className={`px-4 py-2 text-xs flex-shrink-0 ${
          message.error
            ? "bg-red-950 border-b border-red-800 text-red-300"
            : "bg-emerald-950 border-b border-emerald-800 text-emerald-300"
        }`}>
          {message.text}
        </div>
      )}

      {/* Main content */}
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
