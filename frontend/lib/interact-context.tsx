"use client";

import { createContext, useContext, useState, useCallback } from "react";
import { interactQuery, interactClear } from "./api";

type Message = { role: "user" | "assistant"; content: string };

interface InteractState {
  messages: Message[];
  loading: boolean;
  error: string | null;
  contextWarning: string | null;
  submitQuery: (prompt: string) => void;
  clearSession: () => Promise<void>;
}

const InteractContext = createContext<InteractState | null>(null);

export function InteractProvider({ children }: { children: React.ReactNode }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [contextWarning, setContextWarning] = useState<string | null>(null);

  const submitQuery = useCallback((prompt: string) => {
    if (!prompt.trim() || loading) return;
    setLoading(true);
    setError(null);
    setMessages((prev) => [...prev, { role: "user", content: prompt }]);

    interactQuery(prompt)
      .then((res) => {
        if (res.error) {
          setError(res.message || "An error occurred.");
          setMessages((prev) => [
            ...prev,
            { role: "assistant", content: `Error: ${res.message || res.error}` },
          ]);
        } else {
          setMessages((prev) => [
            ...prev,
            { role: "assistant", content: res.result || "(empty response)" },
          ]);
        }
        setContextWarning(res.context_warning ?? null);
      })
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : "Query failed";
        setError(msg);
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: `Error: ${msg}` },
        ]);
      })
      .finally(() => {
        setLoading(false);
      });
  }, [loading]);

  const clearSession = useCallback(async () => {
    try {
      await interactClear();
    } catch {
      // best effort
    }
    setMessages([]);
    setError(null);
    setContextWarning(null);
  }, []);

  return (
    <InteractContext.Provider
      value={{ messages, loading, error, contextWarning, submitQuery, clearSession }}
    >
      {children}
    </InteractContext.Provider>
  );
}

export function useInteract() {
  const ctx = useContext(InteractContext);
  if (!ctx) throw new Error("useInteract must be used within InteractProvider");
  return ctx;
}
