import { useEffect, useState, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "@/lib/api";
import { useSites } from "@/contexts/SiteContext";
import PageHeader from "@/components/PageHeader";
import { Info, Link as LinkIcon, Loader2, CheckCircle2, Settings2, LogOut, ExternalLink } from "lucide-react";
import { toast } from "sonner";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export default function Performance() {
  const { activeSite, sites, refresh: refreshSites } = useSites();
  const [searchParams, setSearchParams] = useSearchParams();
  const [gStatus, setGStatus] = useState(null);
  const [data, setData] = useState(null);
  const [useMock, setUseMock] = useState(false);
  const [loading, setLoading] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [configOpen, setConfigOpen] = useState(false);
  const [gscSites, setGscSites] = useState([]);
  const [gscForm, setGscForm] = useState({ gsc_site_url: "", ga4_property_id: "" });
  const [configSaving, setConfigSaving] = useState(false);

  const loadStatus = useCallback(async () => {
    const { data } = await api.get("/google/status");
    setGStatus(data);
    return data;
  }, []);

  useEffect(() => { loadStatus(); }, [loadStatus]);

  // After OAuth callback redirect
  useEffect(() => {
    if (searchParams.get("google") === "connected") {
      toast.success("Compte Google connecté avec succès");
      loadStatus();
      searchParams.delete("google");
      setSearchParams(searchParams, { replace: true });
    }
  }, [searchParams, setSearchParams, loadStatus]);

  const loadPerformance = useCallback(async () => {
    if (!activeSite) return;
    setLoading(true);
    setData(null);
    try {
      if (useMock || !gStatus?.connected || (!activeSite.gsc_site_url && !activeSite.ga4_property_id)) {
        // fall back to mock
        const { data } = await api.get(`/sites/${activeSite.id}/performance`);
        setData({ ...data, _mode: "mock" });
      } else {
        const { data } = await api.get(`/sites/${activeSite.id}/performance-real?days=28`);
        setData({ ...data, _mode: "real" });
      }
    } catch (err) {
      const detail = err?.response?.data?.detail || "Erreur de chargement";
      toast.error(detail);
      // try mock fallback so the user sees something
      try {
        const { data } = await api.get(`/sites/${activeSite.id}/performance`);
        setData({ ...data, _mode: "mock", _error: detail });
      } catch { /* ignore */ }
    } finally {
      setLoading(false);
    }
  }, [activeSite, gStatus?.connected, useMock]);

  useEffect(() => { loadPerformance(); }, [loadPerformance]);

  const connectGoogle = async () => {
    setConnecting(true);
    try {
      const { data } = await api.get("/google/login");
      window.location.href = data.authorization_url;
    } catch (err) {
      toast.error(err?.response?.data?.detail || "OAuth Google non configuré");
      setConnecting(false);
    }
  };

  const disconnectGoogle = async () => {
    if (!confirm("Déconnecter votre compte Google ?")) return;
    await api.post("/google/disconnect");
    toast.success("Compte Google déconnecté");
    setGStatus(null);
    setData(null);
    loadStatus();
  };

  const openConfig = async () => {
    if (!activeSite) return;
    setGscForm({
      gsc_site_url: activeSite.gsc_site_url || "",
      ga4_property_id: activeSite.ga4_property_id || "",
    });
    setConfigOpen(true);
    try {
      const { data } = await api.get("/google/gsc-sites");
      setGscSites(data.sites || []);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Impossible de lister les sites GSC");
    }
  };

  const saveConfig = async (e) => {
    e?.preventDefault?.();
    setConfigSaving(true);
    try {
      await api.patch(`/sites/${activeSite.id}/google-settings`, {
        gsc_site_url: gscForm.gsc_site_url || null,
        ga4_property_id: gscForm.ga4_property_id || null,
      });
      toast.success("Configuration sauvegardée");
      await refreshSites();
      setConfigOpen(false);
      // refresh data
      setTimeout(loadPerformance, 200);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Échec");
    } finally {
      setConfigSaving(false);
    }
  };

  if (!activeSite) {
    return (
      <div className="p-6 md:p-8 max-w-7xl">
        <PageHeader overline="Performance" title="Suivi SEO" />
        <div className="border border-dashed border-slate-300 bg-white rounded-md p-10 text-center text-sm text-slate-600">
          Sélectionnez un site pour afficher les performances.
        </div>
      </div>
    );
  }

  const serverConfigured = gStatus?.server_configured;
  const isConnected = gStatus?.connected;
  const siteHasGoogleConfig = !!(activeSite.gsc_site_url || activeSite.ga4_property_id);
  const showingMock = data?._mode === "mock";

  return (
    <div className="p-6 md:p-8 max-w-7xl">
      <PageHeader
        overline={`Performance · ${activeSite.label}`}
        title="Suivi Google Search Console + Analytics"
        description="Impressions, clics, position et engagement sur les 28 derniers jours."
        action={
          isConnected ? (
            <div className="flex items-center gap-2">
              <button
                onClick={openConfig}
                data-testid="performance-config-button"
                className="inline-flex items-center gap-2 bg-white border border-slate-300 hover:border-[#002FA7] hover:text-[#002FA7] text-slate-700 px-4 py-2 rounded-md text-sm font-medium transition-colors"
              >
                <Settings2 className="w-4 h-4" /> Configurer Google
              </button>
              <button
                onClick={disconnectGoogle}
                data-testid="performance-disconnect-button"
                className="inline-flex items-center gap-2 bg-white border border-slate-300 hover:border-red-300 hover:text-red-600 text-slate-700 px-3 py-2 rounded-md text-sm font-medium transition-colors"
                title="Déconnecter Google"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          ) : null
        }
      />

      {/* Banner: Google not configured server-side */}
      {gStatus && !serverConfigured && (
        <div className="mb-5 p-4 border border-amber-200 bg-amber-50 rounded-md flex items-start gap-3 text-sm text-amber-900" data-testid="performance-server-not-configured">
          <Info className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <div className="font-medium mb-1">Google OAuth pas encore configuré côté serveur</div>
            <div>L&apos;admin doit renseigner <code className="bg-amber-100 px-1.5 py-0.5 rounded text-xs">GOOGLE_OAUTH_CLIENT_ID</code>, <code className="bg-amber-100 px-1.5 py-0.5 rounded text-xs">GOOGLE_OAUTH_CLIENT_SECRET</code> et <code className="bg-amber-100 px-1.5 py-0.5 rounded text-xs">GOOGLE_OAUTH_REDIRECT_URI</code> dans <code className="text-xs">backend/.env</code>. Données simulées affichées ci-dessous.</div>
          </div>
        </div>
      )}

      {/* Banner: not connected */}
      {gStatus && serverConfigured && !isConnected && (
        <div className="mb-5 p-5 border border-slate-200 bg-white rounded-md" data-testid="performance-connect-card">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-full bg-blue-50 flex items-center justify-center flex-shrink-0">
              <LinkIcon className="w-5 h-5 text-[#002FA7]" />
            </div>
            <div className="flex-1">
              <div className="font-display font-semibold text-slate-950 mb-1">Connectez votre compte Google</div>
              <div className="text-sm text-slate-600 mb-4">
                Pour voir vos vraies données Search Console et Analytics 4, autorisez l&apos;accès en lecture seule à votre compte Google.
                <br />
                Scopes requis : <code className="text-xs bg-slate-100 px-1.5 py-0.5 rounded">webmasters.readonly</code>, <code className="text-xs bg-slate-100 px-1.5 py-0.5 rounded">analytics.readonly</code>.
              </div>
              <button
                onClick={connectGoogle}
                disabled={connecting}
                data-testid="performance-connect-google"
                className="inline-flex items-center gap-2 bg-[#002FA7] hover:bg-[#001D6B] disabled:opacity-60 text-white px-5 py-2.5 rounded-md text-sm font-medium transition-colors shadow-sm"
              >
                {connecting ? <Loader2 className="w-4 h-4 animate-spin" /> : (
                  <svg viewBox="0 0 24 24" className="w-4 h-4" aria-hidden="true">
                    <path fill="#fff" d="M21.35 11.1h-9.17v2.93h6.51c-.31 3.21-2.97 4.6-6.5 4.6-3.92 0-7.13-3.21-7.13-7.14 0-3.94 3.21-7.14 7.13-7.14 1.74 0 3.31.6 4.54 1.78l2.21-2.21C16.66 2.7 14.49 1.7 12.18 1.7 6.96 1.7 2.69 5.97 2.69 11.5s4.27 9.8 9.49 9.8c4.85 0 9.32-3.54 9.32-9.8 0-.57-.05-.96-.15-1.4z"/>
                  </svg>
                )}
                Se connecter avec Google
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Banner: connected but no site config */}
      {gStatus && isConnected && !siteHasGoogleConfig && (
        <div className="mb-5 p-4 border border-blue-200 bg-blue-50 rounded-md flex items-start gap-3 text-sm text-blue-900" data-testid="performance-needs-site-config">
          <Settings2 className="w-5 h-5 text-[#002FA7] flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <div className="font-medium mb-1">Connecté en tant que {gStatus.google_email || "compte Google"}</div>
            <div>Sélectionnez la propriété GSC et le GA4 Property ID pour ce site.</div>
          </div>
          <button
            onClick={openConfig}
            data-testid="performance-configure-now"
            className="inline-flex items-center gap-2 bg-[#002FA7] hover:bg-[#001D6B] text-white px-4 py-2 rounded-md text-sm font-medium"
          >
            Configurer
          </button>
        </div>
      )}

      {/* Banner: connected + configured */}
      {gStatus && isConnected && siteHasGoogleConfig && !showingMock && (
        <div className="mb-5 p-3 border border-emerald-200 bg-emerald-50 rounded-md flex items-center gap-2 text-sm text-emerald-900" data-testid="performance-real-banner">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
          <span>Données réelles · GSC: <code className="text-xs bg-white px-1.5 py-0.5 rounded">{activeSite.gsc_site_url || "—"}</code> · GA4: <code className="text-xs bg-white px-1.5 py-0.5 rounded">{activeSite.ga4_property_id || "—"}</code></span>
        </div>
      )}

      {/* Mock banner (when falling back) */}
      {showingMock && (
        <div className="mb-5 p-3 border border-amber-200 bg-amber-50 rounded-md flex items-start gap-2 text-sm text-amber-900" data-testid="performance-mocked-banner">
          <Info className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <span className="font-medium">Données simulées (MOCKED)</span> — connectez Google pour afficher les vraies métriques. {data?._error && <em className="block mt-1 text-amber-700">{data._error}</em>}
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-sm text-slate-500 flex items-center gap-2"><Loader2 className="w-4 h-4 animate-spin" /> Chargement…</div>
      ) : !data ? null : (
        <PerformanceData data={data} mode={data._mode} />
      )}

      {/* Configuration dialog */}
      <Dialog open={configOpen} onOpenChange={setConfigOpen}>
        <DialogContent className="max-w-lg" data-testid="performance-config-dialog">
          <DialogHeader>
            <DialogTitle>Configurer GSC + GA4</DialogTitle>
            <DialogDescription>Pour {activeSite.name}</DialogDescription>
          </DialogHeader>
          <form onSubmit={saveConfig} className="space-y-4">
            <div>
              <label className="text-xs font-medium text-slate-700 mb-1.5 block">Propriété Search Console</label>
              {gscSites.length > 0 ? (
                <Select value={gscForm.gsc_site_url} onValueChange={(v) => setGscForm((f) => ({ ...f, gsc_site_url: v }))}>
                  <SelectTrigger data-testid="performance-gsc-select"><SelectValue placeholder="Sélectionner une propriété" /></SelectTrigger>
                  <SelectContent>
                    {gscSites.map((s) => (
                      <SelectItem key={s.site_url} value={s.site_url}>
                        {s.site_url} <span className="text-xs text-slate-400">({s.permission})</span>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : (
                <input
                  data-testid="performance-gsc-input"
                  value={gscForm.gsc_site_url}
                  onChange={(e) => setGscForm({ ...gscForm, gsc_site_url: e.target.value })}
                  placeholder="https://www.logirent.ch/ ou sc-domain:logirent.ch"
                  className="w-full border border-slate-300 rounded-md px-3 py-2 bg-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7]"
                />
              )}
              <p className="text-[10px] text-slate-500 mt-1">Doit correspondre EXACTEMENT à la propriété dans Search Console (trailing slash inclus).</p>
            </div>
            <div>
              <label className="text-xs font-medium text-slate-700 mb-1.5 block">GA4 Property ID</label>
              <input
                data-testid="performance-ga4-input"
                value={gscForm.ga4_property_id}
                onChange={(e) => setGscForm({ ...gscForm, ga4_property_id: e.target.value })}
                placeholder="123456789"
                className="w-full border border-slate-300 rounded-md px-3 py-2 bg-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7]"
              />
              <p className="text-[10px] text-slate-500 mt-1">
                <a href="https://analytics.google.com/" target="_blank" rel="noreferrer" className="text-[#002FA7] hover:underline inline-flex items-center gap-1">
                  Trouver mon Property ID <ExternalLink className="w-3 h-3" />
                </a> · Admin → Property settings → Property ID (numérique).
              </p>
            </div>
            <DialogFooter className="pt-2">
              <button type="button" onClick={() => setConfigOpen(false)} className="px-4 py-2 text-sm text-slate-700 border border-slate-300 rounded-md hover:bg-slate-50">Annuler</button>
              <button
                type="submit"
                disabled={configSaving}
                data-testid="performance-config-save"
                className="px-4 py-2 bg-[#002FA7] hover:bg-[#001D6B] text-white text-sm font-medium rounded-md disabled:opacity-60"
              >
                {configSaving ? "Enregistrement…" : "Enregistrer"}
              </button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function PerformanceData({ data, mode }) {
  const isReal = mode === "real";
  // Real GSC structure: { gsc: { daily, keywords, totals }, ga4: {...} }
  // Mock structure: { daily, totals, keywords, recommendations }
  const gscDaily = isReal ? data.gsc?.daily || [] : data.daily || [];
  const gscKeywords = isReal ? data.gsc?.keywords || [] : data.keywords || [];
  const gscTotals = isReal ? data.gsc?.totals : data.totals;
  const ga4Daily = isReal ? data.ga4?.daily || [] : [];
  const ga4Totals = isReal ? data.ga4?.totals : null;

  return (
    <>
      {/* GSC totals */}
      {gscTotals && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <Stat label="Impressions" value={gscTotals.impressions?.toLocaleString("fr-FR") || 0} testId="perf-impressions" />
          <Stat label="Clics" value={gscTotals.clicks?.toLocaleString("fr-FR") || 0} color="text-[#16A34A]" testId="perf-clicks" />
          <Stat label="CTR moyen" value={`${gscTotals.avg_ctr ?? 0}%`} color="text-[#002FA7]" testId="perf-ctr" />
          <Stat label="Position moyenne" value={gscTotals.avg_position ?? 0} testId="perf-position" />
        </div>
      )}

      {/* GA4 totals */}
      {ga4Totals && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <Stat label="Sessions GA4" value={ga4Totals.sessions?.toLocaleString("fr-FR") || 0} testId="perf-ga4-sessions" />
          <Stat label="Utilisateurs" value={ga4Totals.users?.toLocaleString("fr-FR") || 0} color="text-[#0F766E]" testId="perf-ga4-users" />
          <Stat label="Taux de rebond" value={`${ga4Totals.avg_bounce_rate ?? 0}%`} testId="perf-ga4-bounce" />
          <Stat label="Conversions" value={ga4Totals.conversions?.toLocaleString("fr-FR") || 0} color="text-[#DC2626]" testId="perf-ga4-conv" />
        </div>
      )}

      {/* GSC chart */}
      {gscDaily.length > 0 && (
        <div className="border border-slate-200 bg-white rounded-md p-5 mb-6">
          <div className="overline mb-4">GSC — Impressions / Clics par jour</div>
          <div style={{ width: "100%", height: 320 }}>
            <ResponsiveContainer>
              <LineChart data={gscDaily} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                <CartesianGrid stroke="#f1f5f9" />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#64748B" }} interval={Math.max(0, Math.floor(gscDaily.length / 10))} />
                <YAxis yAxisId="l" tick={{ fontSize: 10, fill: "#64748B" }} />
                <YAxis yAxisId="r" orientation="right" tick={{ fontSize: 10, fill: "#64748B" }} />
                <Tooltip contentStyle={{ fontSize: 12, borderRadius: 4, border: "1px solid #e2e8f0" }} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Line yAxisId="l" type="monotone" dataKey="impressions" stroke="#002FA7" strokeWidth={2} dot={false} name="Impressions" />
                <Line yAxisId="r" type="monotone" dataKey="clicks" stroke="#16A34A" strokeWidth={2} dot={false} name="Clics" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* GA4 chart */}
      {ga4Daily.length > 0 && (
        <div className="border border-slate-200 bg-white rounded-md p-5 mb-6">
          <div className="overline mb-4">GA4 — Sessions / Utilisateurs par jour</div>
          <div style={{ width: "100%", height: 320 }}>
            <ResponsiveContainer>
              <LineChart data={ga4Daily} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                <CartesianGrid stroke="#f1f5f9" />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#64748B" }} interval={Math.max(0, Math.floor(ga4Daily.length / 10))} />
                <YAxis tick={{ fontSize: 10, fill: "#64748B" }} />
                <Tooltip contentStyle={{ fontSize: 12, borderRadius: 4, border: "1px solid #e2e8f0" }} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Line type="monotone" dataKey="sessions" stroke="#0F766E" strokeWidth={2} dot={false} name="Sessions" />
                <Line type="monotone" dataKey="users" stroke="#002FA7" strokeWidth={2} dot={false} name="Utilisateurs" />
                <Line type="monotone" dataKey="conversions" stroke="#DC2626" strokeWidth={2} dot={false} name="Conversions" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Top keywords table */}
      {gscKeywords.length > 0 && (
        <div className="border border-slate-200 bg-white rounded-md overflow-hidden" data-testid="perf-keywords">
          <div className="px-4 py-3 border-b border-slate-200 bg-slate-50">
            <div className="overline">Top {gscKeywords.length} requêtes Google</div>
          </div>
          <table className="w-full text-sm">
            <thead className="border-b border-slate-100">
              <tr>
                <th className="text-left px-4 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">Requête</th>
                <th className="text-right px-4 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">Clics</th>
                <th className="text-right px-4 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">Impressions</th>
                <th className="text-right px-4 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">CTR</th>
                <th className="text-right px-4 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">Position</th>
              </tr>
            </thead>
            <tbody>
              {gscKeywords.map((k, i) => (
                <tr key={i} className="border-b border-slate-100">
                  <td className="px-4 py-2.5 text-slate-900">{k.keyword}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-slate-900">{k.clicks}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-slate-700">{k.impressions?.toLocaleString("fr-FR")}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-slate-700">{k.ctr ?? "—"}%</td>
                  <td className="px-4 py-2.5 text-right font-mono text-slate-700">{k.position}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function Stat({ label, value, color = "text-slate-950", testId }) {
  return (
    <div className="border border-slate-200 bg-white rounded-md p-5" data-testid={testId}>
      <div className="overline mb-3">{label}</div>
      <div className={`font-mono text-3xl font-semibold ${color}`}>{value}</div>
      <div className="text-xs text-slate-500 mt-2">28 derniers jours</div>
    </div>
  );
}
