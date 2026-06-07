import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useSites } from "@/contexts/SiteContext";
import PageHeader from "@/components/PageHeader";
import { Info, TrendingUp, TrendingDown, Minus } from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

const trendIcon = (t) => {
  if (t === "up") return <TrendingUp className="w-3.5 h-3.5 text-[#16A34A]" />;
  if (t === "down") return <TrendingDown className="w-3.5 h-3.5 text-[#DC2626]" />;
  return <Minus className="w-3.5 h-3.5 text-slate-400" />;
};

export default function Performance() {
  const { activeSite } = useSites();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!activeSite) return;
    setLoading(true);
    api.get(`/sites/${activeSite.id}/performance`)
      .then(({ data }) => setData(data))
      .finally(() => setLoading(false));
  }, [activeSite?.id]);

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

  return (
    <div className="p-6 md:p-8 max-w-7xl">
      <PageHeader
        overline={`Performance · ${activeSite.label}`}
        title="Suivi Google Search Console"
        description="Évolution des impressions, clics, position moyenne et CTR sur les 28 derniers jours."
      />

      <div className="mb-5 p-3 border border-amber-200 bg-amber-50 rounded-md flex items-start gap-2 text-sm text-amber-900" data-testid="performance-mocked-banner">
        <Info className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
        <div>
          <span className="font-medium">Données simulées (MOCKED)</span> — la connexion réelle Google Search Console & Google Analytics sera ajoutée en phase 2 (OAuth Google).
        </div>
      </div>

      {loading || !data ? (
        <div className="text-sm text-slate-500">Chargement…</div>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="border border-slate-200 bg-white rounded-md p-5" data-testid="perf-impressions">
              <div className="overline mb-3">Impressions</div>
              <div className="font-mono text-3xl font-semibold text-slate-950">{data.totals.impressions.toLocaleString("fr-FR")}</div>
              <div className="text-xs text-slate-500 mt-2">28 derniers jours</div>
            </div>
            <div className="border border-slate-200 bg-white rounded-md p-5" data-testid="perf-clicks">
              <div className="overline mb-3">Clics</div>
              <div className="font-mono text-3xl font-semibold text-[#16A34A]">{data.totals.clicks.toLocaleString("fr-FR")}</div>
              <div className="text-xs text-slate-500 mt-2">Total</div>
            </div>
            <div className="border border-slate-200 bg-white rounded-md p-5" data-testid="perf-ctr">
              <div className="overline mb-3">CTR moyen</div>
              <div className="font-mono text-3xl font-semibold text-[#002FA7]">{data.totals.avg_ctr}%</div>
            </div>
            <div className="border border-slate-200 bg-white rounded-md p-5" data-testid="perf-position">
              <div className="overline mb-3">Position moyenne</div>
              <div className="font-mono text-3xl font-semibold text-slate-950">{data.totals.avg_position}</div>
            </div>
          </div>

          <div className="border border-slate-200 bg-white rounded-md p-5 mb-6">
            <div className="overline mb-4">Tendance impressions / clics</div>
            <div style={{ width: "100%", height: 320 }}>
              <ResponsiveContainer>
                <LineChart data={data.daily} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                  <CartesianGrid stroke="#f1f5f9" />
                  <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#64748B" }} interval={3} />
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

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="lg:col-span-2 border border-slate-200 bg-white rounded-md overflow-hidden" data-testid="perf-keywords">
              <div className="px-4 py-3 border-b border-slate-200 bg-slate-50">
                <div className="overline">Top mots-clés</div>
              </div>
              <table className="w-full text-sm">
                <thead className="border-b border-slate-100">
                  <tr>
                    <th className="text-left px-4 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">Mot-clé</th>
                    <th className="text-right px-4 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">Clics</th>
                    <th className="text-right px-4 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">Impr.</th>
                    <th className="text-right px-4 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">Pos.</th>
                    <th className="text-right px-4 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">Tend.</th>
                  </tr>
                </thead>
                <tbody>
                  {data.keywords.map((k, i) => (
                    <tr key={i} className="border-b border-slate-100">
                      <td className="px-4 py-2.5 text-slate-900">{k.keyword}</td>
                      <td className="px-4 py-2.5 text-right font-mono text-slate-900">{k.clicks}</td>
                      <td className="px-4 py-2.5 text-right font-mono text-slate-700">{k.impressions.toLocaleString("fr-FR")}</td>
                      <td className="px-4 py-2.5 text-right font-mono text-slate-700">{k.position}</td>
                      <td className="px-4 py-2.5 text-right"><div className="inline-flex">{trendIcon(k.trend)}</div></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="border border-slate-200 bg-white rounded-md p-5" data-testid="perf-recommendations">
              <div className="overline mb-3">Recommandations IA</div>
              <ul className="space-y-3">
                {data.recommendations.map((r, i) => (
                  <li key={i} className="text-sm text-slate-700 pb-3 border-b border-slate-100 last:border-0 last:pb-0">
                    {r}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
