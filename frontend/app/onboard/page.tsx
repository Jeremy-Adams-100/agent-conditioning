"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { linkClaude, linkWolfram, getOnboardStatus } from "@/lib/api";

export default function OnboardPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [claudeToken, setClaudeToken] = useState("");
  const [showManualClaude, setShowManualClaude] = useState(false);
  const [detectedSub, setDetectedSub] = useState("");
  const [wolframKey, setWolframKey] = useState("");
  const [agreedPersonal, setAgreedPersonal] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [vmStatus, setVmStatus] = useState("none");

  // Check if already onboarded
  useEffect(() => {
    getOnboardStatus()
      .then((s) => {
        if (s.onboarding_complete) router.push("/explore");
        else if (s.claude_linked) setStep(2);
      })
      .catch(() => router.push("/login"));
  }, [router]);

  // Auto-detect local Claude credentials
  useEffect(() => {
    if (step !== 1) return;
    fetch("/api/auth/detect-claude", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => {
        if (d.found && d.token) {
          setClaudeToken(d.token);
          setDetectedSub(d.subscription || "");
        }
      })
      .catch(() => {});
  }, [step]);

  async function handleClaude(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await linkClaude(claudeToken);
      setStep(2);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to link Claude");
    } finally {
      setLoading(false);
    }
  }

  async function handleWolfram(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await linkWolfram(wolframKey);
      setVmStatus("provisioning");
      const poll = setInterval(async () => {
        try {
          const s = await getOnboardStatus();
          setVmStatus(s.vm_status);
          if (s.vm_status === "ready") {
            clearInterval(poll);
            router.push("/explore");
          }
        } catch {
          // keep polling
        }
      }, 2000);
      setTimeout(() => {
        clearInterval(poll);
        router.push("/explore");
      }, 90000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to link Wolfram");
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <h1 className="text-2xl font-bold mb-1">Connect Your Accounts</h1>
        <p className="text-gray-500 text-sm mb-6">Step {step} of 2</p>

        {step === 1 && (
          <form onSubmit={handleClaude} className="flex flex-col gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">Claude Account</label>

              {claudeToken && !showManualClaude ? (
                /* Auto-detected credentials */
                <div className="border border-green-200 bg-green-50 rounded-lg p-3">
                  <p className="text-sm text-green-800 font-medium">
                    Claude credentials detected
                  </p>
                  <p className="text-xs text-green-600 mt-1">
                    Plan: {detectedSub || "unknown"}
                  </p>
                </div>
              ) : (
                /* Manual paste fallback */
                <>
                  <p className="text-xs text-gray-500 mb-2">
                    Run this in your terminal to get your token:
                  </p>
                  <code className="block bg-gray-50 border border-gray-200 rounded px-3 py-2 text-xs font-mono mb-2 select-all">
                    cat ~/.claude/.credentials.json
                  </code>
                  <p className="text-xs text-gray-500 mb-2">
                    Copy the <code className="bg-gray-100 px-1">accessToken</code> value
                    (starts with <code className="bg-gray-100 px-1">sk-ant-</code>) and
                    paste it below. Need Claude?{" "}
                    <a href="https://claude.ai" target="_blank" rel="noopener noreferrer"
                       className="text-gray-900 underline">Sign up free</a>
                  </p>
                  <input
                    type="text"
                    placeholder="sk-ant-..."
                    value={claudeToken}
                    onChange={(e) => setClaudeToken(e.target.value)}
                    required
                    className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-900 font-mono text-sm"
                  />
                </>
              )}

              {claudeToken && !showManualClaude && (
                <button
                  type="button"
                  onClick={() => setShowManualClaude(true)}
                  className="text-xs text-gray-400 mt-2 hover:text-gray-600"
                >
                  Use a different token
                </button>
              )}
            </div>
            {error && <p className="text-red-600 text-sm">{error}</p>}
            <button
              type="submit"
              disabled={loading || !claudeToken.trim()}
              className="px-6 py-2.5 bg-gray-900 text-white rounded-lg font-medium hover:bg-gray-800 disabled:opacity-50 transition-colors"
            >
              {loading ? "Connecting..." : "Connect Claude"}
            </button>
          </form>
        )}

        {step === 2 && vmStatus === "none" && (
          <form onSubmit={handleWolfram} className="flex flex-col gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">
                Wolfram Engine License Key
              </label>
              <p className="text-xs text-gray-500 mb-2">
                Get a free license at{" "}
                <a href="https://www.wolfram.com/engine/" target="_blank"
                   rel="noopener noreferrer" className="text-gray-900 underline">
                  wolfram.com/engine
                </a>
              </p>
              <input
                type="text"
                placeholder="XXXX-XXXX-XXXXXX"
                value={wolframKey}
                onChange={(e) => setWolframKey(e.target.value)}
                required
                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-900 font-mono text-sm"
              />
            </div>
            <label className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                checked={agreedPersonal}
                onChange={(e) => setAgreedPersonal(e.target.checked)}
                required
                className="mt-0.5"
              />
              <span className="text-gray-600">
                I confirm this is for personal, non-commercial research purposes.
              </span>
            </label>
            {error && <p className="text-red-600 text-sm">{error}</p>}
            <button
              type="submit"
              disabled={loading || !agreedPersonal}
              className="px-6 py-2.5 bg-gray-900 text-white rounded-lg font-medium hover:bg-gray-800 disabled:opacity-50 transition-colors"
            >
              {loading ? "Connecting..." : "Connect Wolfram"}
            </button>
          </form>
        )}

        {vmStatus === "provisioning" && (
          <div className="text-center py-8">
            <div className="inline-block w-6 h-6 border-2 border-gray-300 border-t-gray-900 rounded-full animate-spin mb-4" />
            <p className="text-gray-600">Setting up your research environment...</p>
            <p className="text-xs text-gray-400 mt-1">This takes about 30 seconds</p>
          </div>
        )}

        {vmStatus === "ready" && (
          <div className="text-center py-8">
            <p className="text-green-600 font-medium">Ready!</p>
          </div>
        )}
      </div>
    </div>
  );
}
