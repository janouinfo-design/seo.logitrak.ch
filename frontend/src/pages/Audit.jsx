import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useSites } from "@/contexts/SiteContext";
import PageHeader from "@/components/PageHeader";
import { Search, AlertTriangle, Info, AlertCircle, RefreshCcw, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";

const sevConf = {
  high: { color: "#DC2626", bg: "#FEE2E2", icon: AlertCircle, label: "Critique" },
  medium: { color: "#D97706", bg: "#FEF3C7", icon: AlertTriangle, label: "Important" },
  low: { color: "#0EA5E9", bg: "#E0F2FE", icon: Info, label: "Mineur" },
};

function NoSite() {
  return (
    <div className="border border-dashed border-slate-300 bg-white rounded-md p-10 text-center">
      <p className="text-sm text-slate-600">Sélectionnez ou connectez un site Wix pour lancer un audit.</p>
    </div>
  );
}

export default function Audit() {
  const { activeSite } = useSites();
  const [report, setReport] = useState(null);
  const [running, setRunning] = useState(false);
  const [history, setHistory] = useState([]);

  const loadHistory = async (siteId) => {
    if (!siteId) return;
    const { data } = await api.get(`/sites/${siteId}/audits`);
    setHistory(data);
    if (data.length && !report) setReport(data[0]);
  };

  useEffect(() => {
    setReport(null);
    setHistory([]);
    if (activeSite) loadHistory(activeSite.id);
     
  }, [activeSite?.id]);

  const runAudit = async () => {
    if (!activeSite) return;
    setRunning(true);
    try {
      const { data } = await api.post(`/sites/${activeSite.id}/audit`);
      setReport(data);
      toast.success(`Audit terminé · score ${data.score}/100`);
      loadHistory(activeSite.id);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Échec de l'audit");
    } finally {
      setRunning(false);
    }
  };

  if (!activeSite) {
    return (
      <div className="p-6 md:p-8 max-w-7xl">
        <PageHeader overline="Audit SEO" title="Analyse technique de votre site" />
        <NoSite />
      </div>
    );
  }

  return (
    <div className="p-6 md:p-8 max-w-7xl">
      <PageHeader
        overline={`Audit · ${activeSite.label}`}
        title="Audit SEO automatique"
        description="Analyse de toutes les pages Wix : titres, méta, H1/H2, alt images, longueur de contenu, structure d'URL."
        action={
          <button
            onClick={runAudit}
            disabled={running}
            data-testid="run-audit-button"
            className="inline-flex items-center gap-2 bg-[#002FA7] hover:bg-[#001D6B] disabled:opacity-60 text-white px-4 py-2 rounded-md text-sm font-medium transition-colors shadow-sm"
          >
            {running ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCcw className="w-4 h-4" />}
            {running ? "Audit en cours…" : "Lancer un audit"}
          </button>
        }
      />

      {!report ? (
        <div className="border border-dashed border-slate-300 bg-white rounded-md p-10 text-center" data-testid="audit-empty">
          <Search className="w-8 h-8 text-slate-400 mx-auto mb-3" />
          <p className="text-sm text-slate-600">Lancez votre premier audit pour {activeSite.name}.</p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="border border-slate-200 bg-white rounded-md p-5" data-testid="audit-score">
              <div className="overline mb-3">Score SEO</div>
              <div className={`font-mono text-4xl font-semibold ${report.score >= 75 ? "text-[#16A34A]" : report.score >= 50 ? "text-[#D97706]" : "text-[#DC2626]"}`}>
                {report.score}<span className="text-xl text-slate-400">/100</span>
              </div>
              <div className="mt-3 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                <div
                  className="h-full transition-all"
                  style={{
                    width: `${report.score}%`,
                    background: report.score >= 75 ? "#16A34A" : report.score >= 50 ? "#D97706" : "#DC2626",
                  }}
                />
              </div>
            </div>
            <div className="border border-slate-200 bg-white rounded-md p-5">
              <div className="overline mb-3">Pages analysées</div>
              <div className="font-mono text-4xl font-semibold text-slate-950">{report.total_pages}</div>
            </div>
            <div className="border border-slate-200 bg-white rounded-md p-5">
              <div className="overline mb-3">Critiques</div>
              <div className="font-mono text-4xl font-semibold text-[#DC2626]">{report.summary.high}</div>
            </div>
            <div className="border border-slate-200 bg-white rounded-md p-5">
              <div className="overline mb-3">Importants / mineurs</div>
              <div className="font-mono text-4xl font-semibold text-[#D97706]">
                {report.summary.medium}
                <span className="text-xl text-slate-400"> / {report.summary.low}</span>
              </div>
            </div>
          </div>

          <Tabs defaultValue="issues">
            <TabsList className="bg-transparent border-b border-slate-200 rounded-none p-0 h-auto w-full justify-start gap-6">
              <TabsTrigger
                value="issues"
                className="rounded-none border-b-2 border-transparent data-[state=active]:border-[#002FA7] data-[state=active]:bg-transparent data-[state=active]:text-slate-950 px-0 py-3 text-sm"
              >
                Problèmes détectés ({report.issues.length})
              </TabsTrigger>
              <TabsTrigger
                value="history"
                className="rounded-none border-b-2 border-transparent data-[state=active]:border-[#002FA7] data-[state=active]:bg-transparent data-[state=active]:text-slate-950 px-0 py-3 text-sm"
              >
                Historique ({history.length})
              </TabsTrigger>
            </TabsList>

            <TabsContent value="issues" className="mt-5">
              <div className="border border-slate-200 bg-white rounded-md overflow-hidden" data-testid="audit-issues-table">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 border-b border-slate-200">
                    <tr>
                      <th className="text-left px-4 py-2.5 text-xs font-semibold text-slate-500 uppercase tracking-wider">Sévérité</th>
                      <th className="text-left px-4 py-2.5 text-xs font-semibold text-slate-500 uppercase tracking-wider">Page</th>
                      <th className="text-left px-4 py-2.5 text-xs font-semibold text-slate-500 uppercase tracking-wider">Catégorie</th>
                      <th className="text-left px-4 py-2.5 text-xs font-semibold text-slate-500 uppercase tracking-wider">Problème / Recommandation</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.issues.length === 0 ? (
                      <tr>
                        <td colSpan={4} className="px-4 py-8 text-center text-slate-500 text-sm">
                          Aucun problème détecté.
                        </td>
                      </tr>
                    ) : (
                      report.issues.map((iss, i) => {
                        const sv = sevConf[iss.severity];
                        const Ico = sv.icon;
                        return (
                          <tr key={i} className="border-b border-slate-100 hover:bg-slate-50" data-testid={`audit-issue-${i}`}>
                            <td className="px-4 py-3 align-top">
                              <span
                                className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium"
                                style={{ background: sv.bg, color: sv.color }}
                              >
                                <Ico className="w-3 h-3" />
                                {sv.label}
                              </span>
                            </td>
                            <td className="px-4 py-3 align-top">
                              <div className="font-medium text-slate-900 text-sm">{iss.page_title}</div>
                              <div className="text-xs text-slate-500 truncate max-w-[200px]" title={iss.page_url}>{iss.page_url}</div>
                            </td>
                            <td className="px-4 py-3 align-top text-slate-700 text-sm">{iss.category}</td>
                            <td className="px-4 py-3 align-top">
                              <div className="text-slate-900 text-sm font-medium">{iss.message}</div>
                              <div className="text-xs text-slate-600 mt-1">{iss.recommendation}</div>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </TabsContent>

            <TabsContent value="history" className="mt-5">
              <div className="border border-slate-200 bg-white rounded-md">
                {history.length === 0 ? (
                  <div className="p-6 text-center text-sm text-slate-500">Aucun audit antérieur.</div>
                ) : (
                  <ul className="divide-y divide-slate-100">
                    {history.map((a) => (
                      <li
                        key={a.id}
                        onClick={() => setReport(a)}
                        className="p-4 hover:bg-slate-50 cursor-pointer flex items-center justify-between"
                        data-testid={`audit-history-${a.id}`}
                      >
                        <div>
                          <div className="text-sm font-medium text-slate-900">{new Date(a.created_at).toLocaleString("fr-FR")}</div>
                          <div className="text-xs text-slate-500">{a.total_pages} pages · {a.issues.length} problèmes</div>
                        </div>
                        <div className={`font-mono text-lg font-semibold ${a.score >= 75 ? "text-[#16A34A]" : a.score >= 50 ? "text-[#D97706]" : "text-[#DC2626]"}`}>
                          {a.score}/100
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </TabsContent>
          </Tabs>
        </>
      )}
    </div>
  );
}
