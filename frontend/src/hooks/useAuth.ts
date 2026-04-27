import { useCallback, useEffect, useState } from "react";
import { authApi } from "@/services/api";
import type { User } from "@/types";

interface AuthState {
  user: User | null;
  loading: boolean;
  isAuthenticated: boolean;
}

export function useAuth() {
  const [state, setState] = useState<AuthState>({
    user: null,
    loading: true,
    isAuthenticated: false,
  });

  const loadUser = useCallback(async () => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      setState({ user: null, loading: false, isAuthenticated: false });
      return;
    }
    try {
      const user = await authApi.me();
      setState({ user, loading: false, isAuthenticated: true });
    } catch {
      localStorage.removeItem("access_token");
      setState({ user: null, loading: false, isAuthenticated: false });
    }
  }, []);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  const login = useCallback(async (username: string, password: string) => {
    const { access_token } = await authApi.login(username, password);
    localStorage.setItem("access_token", access_token);
    await loadUser();
  }, [loadUser]);

  const logout = useCallback(() => {
    localStorage.removeItem("access_token");
    setState({ user: null, loading: false, isAuthenticated: false });
  }, []);

  return { ...state, login, logout };
}
