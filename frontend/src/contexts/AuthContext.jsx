import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const raw = localStorage.getItem("logi_user");
    return raw ? JSON.parse(raw) : null;
  });
  const [loading, setLoading] = useState(true);

  const persist = useCallback((token, u) => {
    localStorage.setItem("logi_token", token);
    localStorage.setItem("logi_user", JSON.stringify(u));
    setUser(u);
  }, []);

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    persist(data.token, data.user);
    return data.user;
  };

  const register = async (email, password, full_name) => {
    const { data } = await api.post("/auth/register", { email, password, full_name });
    persist(data.token, data.user);
    return data.user;
  };

  const logout = () => {
    localStorage.removeItem("logi_token");
    localStorage.removeItem("logi_user");
    setUser(null);
    window.location.href = "/login";
  };

  useEffect(() => {
    const token = localStorage.getItem("logi_token");
    if (!token) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    api.get("/auth/me")
      .then(({ data }) => { if (!cancelled) setUser(data); })
      .catch(() => {
        if (cancelled) return;
        localStorage.removeItem("logi_token");
        localStorage.removeItem("logi_user");
        setUser(null);
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
