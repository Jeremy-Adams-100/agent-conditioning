"use client";

import { useState } from "react";
import {
  startExploration,
  stopExploration,
  clearExploration,
  resumeExploration,
} from "@/lib/api";

interface ControlsProps {
  isRunning: boolean;
  hasCycles: boolean;
  onAction: () => void;
}

export default function Controls({ isRunning, hasCycles, onAction }: ControlsProps) {
  const [topic, setTopic] = useState("");
  const [loading, setLoading] = useState("");
  const [message, setMessage] = useState("");

  async function handleAction(action: string) {
    setLoading(action);
    setMessage("");
    try {
      if (action === "start") {
        await startExploration(topic);
        setTopic("");
        setMessage("Exploration started. Results will appear as cycles complete.");
      } else if (action === "stop") {
        await stopExploration();
        setMessage("Stopping after current cycle...");
      } else if (action === "clear") {
        await clearExploration();
        setMessage("Cleared.");
      } else if (action === "resume") {
        await resumeExploration();
        setMessage("Resumed. Results will appear as cycles complete.");
      }
      onAction();
    } catch (err: unknown) {
      setMessage(err instanceof Error ? err.message : "Action failed — VM may not be ready");
    } finally {
      setLoading("");
    }
  }

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-2">
        {!isRunning && (
          <>
            <input
              type="text"
              placeholder="explore [topic]"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && topic.trim()) handleAction("start");
              }}
              className="flex-1 px-3 py-1.5 bg-gray-900 border border-gray-700 rounded-lg text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-gray-400"
            />
            <button
              onClick={() => handleAction("start")}
              disabled={!topic.trim() || loading === "start"}
              className="px-4 py-1.5 bg-white text-gray-900 text-sm rounded-lg font-medium hover:bg-gray-200 disabled:opacity-50 transition-colors"
            >
              {loading === "start" ? "..." : "Go"}
            </button>
            {hasCycles && (
              <button
                onClick={() => handleAction("resume")}
                disabled={loading === "resume"}
                className="px-3 py-1.5 border border-gray-600 text-sm text-gray-300 rounded-lg hover:bg-gray-800 transition-colors"
              >
                Resume
              </button>
            )}
          </>
        )}
        {isRunning && (
          <button
            onClick={() => handleAction("stop")}
            disabled={loading === "stop"}
            className="px-4 py-1.5 border border-red-700 text-red-400 text-sm rounded-lg hover:bg-red-950 transition-colors"
          >
            Stop
          </button>
        )}
        <button
          onClick={() => handleAction("clear")}
          disabled={loading === "clear" || isRunning}
          className="px-3 py-1.5 text-gray-500 text-sm hover:text-gray-300 transition-colors disabled:opacity-30"
        >
          Clear
        </button>
      </div>
      {message && (
        <p className="text-xs text-gray-400 px-1">{message}</p>
      )}
    </div>
  );
}
