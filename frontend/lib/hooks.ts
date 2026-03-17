"use client";

import useSWR from "swr";
import type { ExplorationStatus, SessionEntry, FileEntry } from "./types";

// SWR fetcher that includes credentials for cookie auth
const fetcher = (url: string) =>
  fetch(url, { credentials: "include" }).then((r) => {
    if (!r.ok) throw new Error(`${r.status}`);
    return r.json();
  });

// Poll exploration status every 5 seconds
export function useExplorationStatus(enabled = true) {
  return useSWR<ExplorationStatus>(
    enabled ? "/api/data/status" : null,
    fetcher,
    { refreshInterval: enabled ? 5000 : 0, revalidateOnFocus: false }
  );
}

// Poll sessions (less frequently)
export function useSessions(limit = 20) {
  return useSWR<SessionEntry[]>(
    `/api/data/sessions?limit=${limit}`,
    fetcher,
    { refreshInterval: 10000, revalidateOnFocus: false }
  );
}

// File list (on demand, not polling)
export function useFiles() {
  return useSWR<FileEntry[]>("/api/data/files", fetcher, {
    revalidateOnFocus: false,
  });
}
