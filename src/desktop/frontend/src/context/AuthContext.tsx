import React, {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
} from "react";
import {
  authIsAuthenticated,
  authGetCurrentUser,
  authLogin,
  authLogout,
  authRefreshToken,
  type LoginResult,
  type UserProfile,
} from "@/lib/tauri";

interface AuthState {
  user: UserProfile | null;
  token: string | null;
  isLoading: boolean;
}

interface AuthContextValue extends AuthState {
  login: (email: string, password: string) => Promise<LoginResult>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    token: null,
    isLoading: true,
  });

  const restore = useCallback(async () => {
    try {
      const authenticated = await authIsAuthenticated();
      if (!authenticated) {
        setState({ user: null, token: null, isLoading: false });
        return;
      }
      // Token está en Rust AppState — obtenemos el perfil
      const user = await authGetCurrentUser();
      setState({ user, token: "__stored__", isLoading: false });
    } catch {
      setState({ user: null, token: null, isLoading: false });
    }
  }, []);

  useEffect(() => {
    restore();
  }, [restore]);

  const login = useCallback(async (email: string, password: string) => {
    const result = await authLogin(email, password);
    const user = await authGetCurrentUser();
    setState({ user, token: result.access_token, isLoading: false });
    return result;
  }, []);

  const logout = useCallback(async () => {
    await authLogout();
    setState({ user: null, token: null, isLoading: false });
  }, []);

  const refresh = useCallback(async () => {
    const newToken = await authRefreshToken();
    setState((s) => ({ ...s, token: newToken }));
  }, []);

  return (
    <AuthContext.Provider value={{ ...state, login, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
