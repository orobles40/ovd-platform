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

export const configSave = (engineUrl: string) =>
  invoke<void>("config_save", { engineUrl: engineUrl });

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
