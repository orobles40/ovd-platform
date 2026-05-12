import { invoke } from "@tauri-apps/api/core";

// ── Tipos compartidos ─────────────────────────────────────────────────────────

export interface LoginResult {
  access_token: string;
  org_id: string;
  user_id: string;
  email: string;
  role: string;
}

export interface UserProfile {
  user_id: string;
  org_id: string;
  role: string;
  email: string;
}

export interface Config {
  engine_url: string;
  engine_secret: string;
}

export interface WriteResult {
  files_written: number;
  paths: string[];
}

export interface TestResult {
  passed: boolean;
  exit_code: number;
  summary: string;
  output: string;
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export const authLogin = (email: string, password: string) =>
  invoke<LoginResult>("auth_login", { email, password });

export const authLogout = () => invoke<void>("auth_logout");

export const authIsAuthenticated = () =>
  invoke<boolean>("auth_is_authenticated");

export const authGetCurrentUser = () =>
  invoke<UserProfile>("auth_get_current_user");

export const authRefreshToken = () => invoke<string>("auth_refresh_token");

// ── Config ────────────────────────────────────────────────────────────────────

export const configGet = () => invoke<Config>("config_get");

export const configSave = (engineUrl: string, engineSecret: string) =>
  invoke<void>("config_save", { engineUrl, engineSecret });

// ── Workspace ─────────────────────────────────────────────────────────────────

export const workspacePickFolder = () =>
  invoke<string | null>("workspace_pick_folder");

export const workspaceReadContext = (folder: string) =>
  invoke<string>("workspace_read_context", { folder });

export const workspaceWriteArtifacts = (sessionId: string, folder: string) =>
  invoke<WriteResult>("workspace_write_artifacts", {
    sessionId,
    folder,
  });

export const workspaceRunTests = (
  folder: string,
  command: string,
  timeoutSecs?: number
) =>
  invoke<TestResult>("workspace_run_tests", {
    folder,
    command,
    timeoutSecs: timeoutSecs ?? null,
  });

// S125: abre la carpeta en el explorador del sistema operativo
export const workspaceOpenFolder = (folder: string) =>
  invoke<void>("workspace_open_folder", { folder });

// ── DB — historial SQLite (T3) + error log (T6) ───────────────────────────────

export interface CycleEntry {
  thread_id: string;
  project_directory: string;
  fr_text: string;
  qa_score: number | null;
  security_score: number | null;
  tokens_in: number | null;
  tokens_out: number | null;
  elapsed_secs: number | null;
  files_written: number | null;
  output_dir: string | null;
  status: string;
  created_at: string | null;
}

export interface ErrorLogEntry {
  id: number;
  level: string;
  message: string;
  context: string;
  created_at: string;
}

export const dbSaveCycle = (entry: Omit<CycleEntry, "created_at">) =>
  invoke<void>("db_save_cycle", { entry });

export const dbListProjectCycles = (projectDirectory: string, limit = 20) =>
  invoke<CycleEntry[]>("db_list_project_cycles", { projectDirectory, limit });

export const dbListErrors = (limit = 50) =>
  invoke<ErrorLogEntry[]>("db_list_errors", { limit });
