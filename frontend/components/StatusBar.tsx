"use client";

import type { ExplorationStatus } from "@/lib/types";

export default function StatusBar({ status }: { status?: ExplorationStatus }) {
  if (!status) {
    return (
      <div className="text-sm text-gray-400">Connecting...</div>
    );
  }

  const state = status.state;
  const cycle = state?.cycle ?? 0;
  const running = status.exploration_running;

  return (
    <div className="flex items-center gap-3 text-sm">
      <span
        className={`inline-block w-2 h-2 rounded-full ${
          running ? "bg-green-500 animate-pulse" : "bg-gray-300"
        }`}
      />
      <span className="text-gray-600">
        {running ? "Running" : cycle > 0 ? "Stopped" : "Idle"}
      </span>
      {cycle > 0 && (
        <span className="text-gray-400">Cycle {cycle}</span>
      )}
    </div>
  );
}
