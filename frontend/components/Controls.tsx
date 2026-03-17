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

  async function handleAction(action: string) {
    setLoading(action);
    try {
      if (action === "start") await startExploration(topic);
      else if (action === "stop") await stopExploration();
      else if (action === "clear") await clearExploration();
      else if (action === "resume") await resumeExploration();
      if (action === "start") setTopic("");
      onAction();
    } catch {
      // errors shown via status polling
    } finally {
      setLoading("");
    }
  }

  return (
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
            className="flex-1 px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
          />
          <button
            onClick={() => handleAction("start")}
            disabled={!topic.trim() || loading === "start"}
            className="px-4 py-1.5 bg-gray-900 text-white text-sm rounded-lg font-medium hover:bg-gray-800 disabled:opacity-50 transition-colors"
          >
            {loading === "start" ? "..." : "Go"}
          </button>
          {hasCycles && (
            <button
              onClick={() => handleAction("resume")}
              disabled={loading === "resume"}
              className="px-3 py-1.5 border border-gray-300 text-sm rounded-lg hover:bg-gray-50 transition-colors"
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
          className="px-4 py-1.5 border border-red-300 text-red-600 text-sm rounded-lg hover:bg-red-50 transition-colors"
        >
          Stop
        </button>
      )}
      <button
        onClick={() => handleAction("clear")}
        disabled={loading === "clear" || isRunning}
        className="px-3 py-1.5 text-gray-400 text-sm hover:text-gray-600 transition-colors disabled:opacity-30"
      >
        Clear
      </button>
    </div>
  );
}
