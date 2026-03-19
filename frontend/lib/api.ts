// API client — thin fetch wrappers for all backend endpoints.
// Uses Next.js rewrites to proxy /api/* to the FastAPI backend.

import type {
  AuthResponse,
  OnboardStatus,
  ExplorationStatus,
  SessionEntry,
  FileEntry,
  FileContent,
} from "./types";

async function post<T>(path: string, body?: object): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
    credentials: "include",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `${res.status}`);
  }
  if (res.status === 204) return {} as T;
  return res.json();
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path, { credentials: "include" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `${res.status}`);
  }
  return res.json();
}

// Auth
export const signup = (email: string, password: string, turnstile_token = "") =>
  post<AuthResponse>("/api/auth/signup", { email, password, turnstile_token });

export const login = (email: string, password: string) =>
  post<AuthResponse>("/api/auth/login", { email, password });

export const logout = () => post("/api/auth/logout");

// Onboarding
export const linkClaude = (claude_token: string) =>
  post("/api/onboard/claude", { claude_token });

export const linkWolfram = (wolfram_key: string) =>
  post("/api/onboard/wolfram", { wolfram_key });

export const getOnboardStatus = () =>
  get<OnboardStatus>("/api/onboard/status");

// Exploration control
export const startExploration = (topic: string) =>
  post("/api/explore/start", { topic });

export const stopExploration = () => post("/api/explore/stop");

export const clearExploration = () => post("/api/explore/clear");

export const resumeExploration = () => post("/api/explore/resume");

export const guideExploration = (text: string) =>
  post("/api/explore/guide", { text });

// Tier
export const checkTier = () => post<{ tier: string; config: object }>("/api/tier/check");

// Data proxy
export const getStatus = () => get<ExplorationStatus>("/api/data/status");

export const getSessions = (query?: string, limit = 20) =>
  get<SessionEntry[]>(
    `/api/data/sessions?limit=${limit}${query ? `&query=${encodeURIComponent(query)}` : ""}`
  );

export const getSession = (id: string) =>
  get<SessionEntry>(`/api/data/sessions/${id}`);

export const getFiles = () => get<FileEntry[]>("/api/data/files");

export const getFile = (path: string) =>
  get<FileContent>(`/api/data/files/${path}`);

export const getFileDownloadUrl = (path: string) =>
  `/api/data/files/${path}/download`;

// Interact
export const interactQuery = (prompt: string) =>
  post<{ result?: string; usage?: object; session_id?: string; error?: string; message?: string }>(
    "/api/interact/query", { prompt });

export const interactClear = () => post("/api/interact/clear");

export const getInteractFiles = () => get<FileEntry[]>("/api/interact/files");

export const getInteractFile = (path: string) =>
  get<FileContent>(`/api/interact/files/${path}`);

export const getInteractFileDownloadUrl = (path: string) =>
  `/api/interact/files/${path}/download`;
