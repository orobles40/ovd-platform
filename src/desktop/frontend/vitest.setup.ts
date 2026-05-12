import "@testing-library/jest-dom";

// Mock completo de @tauri-apps — no disponible en jsdom
vi.mock("@tauri-apps/api/core", () => ({
  invoke: vi.fn(),
}));

vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn(() => Promise.resolve(() => {})),
  emit: vi.fn(),
}));

// Mock de los comandos Tauri usados por la app
vi.mock("@/lib/tauri", () => ({
  workspacePickFolder: vi.fn(),
  workspaceReadContext: vi.fn(() => Promise.resolve("")),
  workspaceWriteArtifacts: vi.fn(),
  workspaceRunTests: vi.fn(),
  workspaceOpenFolder: vi.fn(),
  configGet: vi.fn(() => Promise.resolve({ engine_url: "http://localhost:8001", engine_secret: "" })),
  configSave: vi.fn(() => Promise.resolve()),
  authLogin: vi.fn(),
  authLogout: vi.fn(),
  authRefreshToken: vi.fn(() => Promise.resolve("mock-token")),
  authGetCurrentUser: vi.fn(() => Promise.resolve({ email: "test@test.com", org_id: "org1" })),
  // DB — T3/T6
  dbSaveCycle: vi.fn(() => Promise.resolve()),
  dbListProjectCycles: vi.fn(() => Promise.resolve([])),
  dbListErrors: vi.fn(() => Promise.resolve([])),
}));

// localStorage limpio entre tests
beforeEach(() => {
  localStorage.clear();
});
