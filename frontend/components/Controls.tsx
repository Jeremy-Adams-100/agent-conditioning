"use client";

import { useState, useRef, useEffect } from "react";
import {
  startExploration,
  stopExploration,
  clearExploration,
  resumeExploration,
  guideExploration,
} from "@/lib/api";

interface ControlsProps {
  isRunning: boolean;
  hasCycles: boolean;
  currentCycle: number;
  onAction: () => void;
}

const MAX_TOPIC_LENGTH = 10000;

export default function Controls({ isRunning, hasCycles, currentCycle, onAction }: ControlsProps) {
  const [topic, setTopic] = useState("");
  const [loading, setLoading] = useState("");
  const [message, setMessage] = useState("");
  const [guideSentAtCycle, setGuideSentAtCycle] = useState<number | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Re-enable guidance input when cycle advances past the one we sent at
  const guideDisabled = guideSentAtCycle !== null && currentCycle <= guideSentAtCycle;

  // Auto-resize textarea: 1 line default, snap to 4 lines when content
  // wraps past 1 line, internal scroll beyond 4 lines
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    const lineHeight = 20; // ~text-sm line height
    const oneLine = lineHeight + 12; // + vertical padding
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
  }, [topic]);

  async function handleAction(action: string) {
    setLoading(action);
    setMessage("");
    try {
      if (action === "start") {
        await startExploration(topic);
        setTopic("");
        setMessage("Exploration started. Results will appear as cycles complete.");
      } else if (action === "guide") {
        await guideExploration(topic);
        setTopic("");
        setGuideSentAtCycle(currentCycle);
        setMessage("Guidance queued for next cycle.");
      } else if (action === "stop") {
        await stopExploration();
        setMessage("Stopping after current cycle...");
      } else if (action === "clear") {
        await clearExploration();
        setGuideSentAtCycle(null);
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
      <div className="flex items-start gap-2">
        {!isRunning && (
          <>
            <textarea
              ref={textareaRef}
              placeholder="explore [topic]"
              value={topic}
              maxLength={MAX_TOPIC_LENGTH}
              rows={1}
              onChange={(e) => setTopic(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && topic.trim()) {
                  e.preventDefault();
                  handleAction("start");
                }
              }}
              className="flex-1 px-3 py-1.5 bg-gray-900 border border-gray-700 rounded-lg text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-gray-400 resize-none leading-5"
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
          <>
            <textarea
              ref={textareaRef}
              placeholder="guide next cycle..."
              value={topic}
              maxLength={MAX_TOPIC_LENGTH}
              rows={1}
              disabled={guideDisabled}
              onChange={(e) => setTopic(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && topic.trim() && !guideDisabled) {
                  e.preventDefault();
                  handleAction("guide");
                }
              }}
              className="flex-1 px-3 py-1.5 bg-gray-900 border border-gray-700 rounded-lg text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-gray-400 resize-none leading-5 disabled:opacity-40"
            />
            <button
              onClick={() => handleAction("guide")}
              disabled={!topic.trim() || guideDisabled || loading === "guide"}
              className="px-4 py-1.5 bg-white text-gray-900 text-sm rounded-lg font-medium hover:bg-gray-200 disabled:opacity-50 transition-colors"
            >
              {loading === "guide" ? "..." : "Go"}
            </button>
            <button
              onClick={() => handleAction("stop")}
              disabled={loading === "stop"}
              className="px-4 py-1.5 border border-red-700 text-red-400 text-sm rounded-lg hover:bg-red-950 transition-colors"
            >
              Stop
            </button>
          </>
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
