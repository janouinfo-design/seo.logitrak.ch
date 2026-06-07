import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useSites } from "@/contexts/SiteContext";
import PageHeader from "@/components/PageHeader";
import { CheckCircle2, AlertCircle, History as HistoryIcon } from "lucide-react";

const statusBadge = (s) => {
  if (s === "success") return { color: "#16A34A", bg: "#DCFCE7", label: "Wix · OK", Icon: CheckCircle2 };
  return { color: "#D97706", bg: "#FEF3C7", label: "Wix indisponible", Icon: AlertCircle };
};

export default function HistoryPage() {
  const { activeSite } = useSites();
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.get("/publish-logs", { params: activeSite ? { site_id: activeSite.id } : {} })
      .then(({ data }) => setLogs(data.logs))
      .finally(() => setLoading(false));
  }, [activeSite?.id]);

  return (
    <div className="p-6 md:p-8 max-w-6xl">
      <PageHeader
        overline={activeSite ? `Historique · ${activeSite.label}` : "Historique"}
        title="Publications & journal d'activité"
        description="Toutes les tentatives de publication vers Wix, avec leur statut et l'identifiant du brouillon Wix créé."
      />

      {loading ? (
        <div className="text-sm text-slate-500">Chargement…</div>
      ) : logs.length === 0 ? (
        <div className="border border-dashed border-slate-300 bg-white rounded-md p-10 text-center" data-testid="history-empty">
          <HistoryIcon className="w-8 h-8 text-slate-400 mx-auto mb-3" />
          <p className="text-sm text-slate-600">Aucune publication enregistrée pour le moment.</p>
        </div>
      ) : (
        <div className="border border-slate-200 bg-white rounded-md overflow-hidden" data-testid="history-list">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="text-left px-4 py-2.5 text-xs font-semibold text-slate-500 uppercase tracking-wider">Date</th>
                <th className="text-left px-4 py-2.5 text-xs font-semibold text-slate-500 uppercase tracking-wider">Titre</th>
                <th className="text-left px-4 py-2.5 text-xs font-semibold text-slate-500 uppercase tracking-wider">Statut</th>
                <th className="text-left px-4 py-2.5 text-xs font-semibold text-slate-500 uppercase tracking-wider">Wix Draft ID</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((l) => {
                const b = statusBadge(l.status);
                const Ico = b.Icon;
                return (
                  <tr key={l.id} className="border-b border-slate-100 hover:bg-slate-50" data-testid={`history-row-${l.id}`}>
                    <td className="px-4 py-3 text-slate-700 text-xs">{new Date(l.created_at).toLocaleString("fr-FR")}</td>
                    <td className="px-4 py-3 text-slate-900 font-medium">{l.title}</td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium" style={{ background: b.bg, color: b.color }}>
                        <Ico className="w-3 h-3" /> {b.label}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-slate-700">{l.wix_draft_id || "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
