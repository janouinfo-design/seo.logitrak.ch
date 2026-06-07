import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

const SiteContext = createContext(null);

export function SiteProvider({ children }) {
  const { user } = useAuth();
  const [sites, setSites] = useState([]);
  const [activeSiteId, setActiveSiteId] = useState(() => localStorage.getItem("logi_active_site") || null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    try {
      const { data } = await api.get("/sites");
      setSites(data);
      if (data.length && !data.find((s) => s.id === activeSiteId)) {
        setActiveSiteId(data[0].id);
        localStorage.setItem("logi_active_site", data[0].id);
      } else if (data.length === 0) {
        setActiveSiteId(null);
        localStorage.removeItem("logi_active_site");
      }
    } finally {
      setLoading(false);
    }
  }, [user, activeSiteId]);

  useEffect(() => {
    if (user) refresh();
  }, [user, refresh]);

  const selectSite = (id) => {
    setActiveSiteId(id);
    localStorage.setItem("logi_active_site", id);
  };

  const activeSite = sites.find((s) => s.id === activeSiteId) || null;

  return (
    <SiteContext.Provider value={{ sites, activeSite, activeSiteId, selectSite, refresh, loading }}>
      {children}
    </SiteContext.Provider>
  );
}

export const useSites = () => useContext(SiteContext);
