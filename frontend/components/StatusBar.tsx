"use client";

import type { ExplorationStatus } from "@/lib/types";

export default function StatusBar({ status }: { status?: ExplorationStatus }) {
  const state = status?.state;
  const cycle = state?.cycle ?? 0;
  const running = status?.exploration_running ?? false;

  return (
    <div className="flex items-center gap-3 text-sm">
      <span
        className={`inline-block w-2 h-2 rounded-full ${
          running ? "bg-emerald-400 animate-pulse" : "bg-gray-600"
        }`}
      />
      <span className="text-gray-400">
        {running ? "Running" : cycle > 0 ? "Stopped" : "Idle"}
      </span>
      {cycle > 0 && (
        <span className="text-gray-500">Cycle {cycle}</span>
      )}
    </div>
  );
}
