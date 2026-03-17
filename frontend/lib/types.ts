// API response types matching the FastAPI backend

export interface AuthResponse {
  user_id: string;
  email: string;
}

export interface OnboardStatus {
  email: string;
  tier: string;
  claude_linked: boolean;
  wolfram_linked: boolean;
  vm_status: string;
  onboarding_complete: boolean;
}

export interface ExplorationStatus {
  exploration_running: boolean;
  status_md?: string;
  state?: {
    cycle: number;
    results: Record<string, string>;
    failures: Record<string, number>;
    timestamp: string;
    agent_sessions: Record<string, string>;
  };
}

export interface SessionEntry {
  id: string;
  created_at: string;
  topic?: string;
  subtopic?: string;
  tools?: string;
  keywords?: string;
  summary_xml?: string;
  philosophy?: string;
  record_type?: string;
  depth?: number;
}

export interface FileEntry {
  path: string;
  size: number;
  modified: number;
}

export interface FileContent {
  path: string;
  content: string;
}
