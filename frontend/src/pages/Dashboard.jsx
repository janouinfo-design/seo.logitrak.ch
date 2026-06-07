import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { useSites } from "@/contexts/SiteContext";
import PageHeader from "@/components/PageHeader";
import { ArrowUpRight, FileText, Search, CheckCircle2, AlertTriangle, Sparkles } from "lucide-react";

function StatCard({ overline, value, hint, tone = "default", testid }) {
  const accent = tone === "accent" ? "text-[#002FA7]" : tone === "success" ? "text-[#16A34A]" : "text-slate-950";
  return (
    <div className="border border-slate-200 rounded-md bg-white p-5 hover:border-slate-300 transition-colors" data-testid={testid}>
      <div className="overline mb-3">{overline}</div>
      <div className={`font-mono text-3xl font-semibold tracking-tight ${accent}`}>{value}</div>
      {hint && <div className="text-xs text-slate-500 mt-2">{hint}</div>}
    </div>
  );
}

export default function Dashboard() {
  const { activeSite, sites } = useSites();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.get("/dashboard/stats", { params: activeSite ? { site_id: activeSite.id } : {} })
      .then(({ data }) => setStats(data))
      .finally(() => setLoading(false));
  }, [activeSite]);

  return (
    <div className="p-6 md:p-8 max-w-7xl">
      <PageHeader
        overline={activeSite ? `Contexte · ${activeSite.label}` : "Aperçu"}
        title="Vue d'ensemble"
        description="Synthèse de votre activité SEO sur l'ensemble de vos sites Wix connectés."
      />

      {sites.length === 0 ? (
        <div className="border border-slate-200 bg-white rounded-md p-8 text-center" data-testid="dashboard-empty-state">
          <div className="w-12 h-12 rounded-md bg-slate-100 flex items-center justify-center mx-auto mb-4">
            <Sparkles className="w-6 h-6 text-[#002FA7]" />
          </div>
          <h2 className="font-display text-xl font-semibold text-slate-950 mb-2">Connectez votre premier site Wix</h2>
          <p className="text-sm text-slate-600 max-w-md mx-auto mb-5">
            Reliez Logirent ou Logitime via leur clé API Wix pour démarrer l&apos;audit SEO et la génération de contenu IA.
          </p>
          <Link
            to="/sites"
            data-testid="dashboard-connect-site-cta"
            className="inline-flex items-center gap-2 bg-[#002FA7] hover:bg-[#001D6B] text-white px-4 py-2.5 rounded-md text-sm font-medium transition-colors shadow-sm"
          >
            Connecter un site Wix <ArrowUpRight className="w-4 h-4" />
          </Link>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard overline="Sites connectés" value={loading ? "—" : stats?.sites ?? 0} hint="Wix" testid="stat-sites" />
            <StatCard overline="Brouillons" value={loading ? "—" : stats?.drafts ?? 0} hint="En attente de validation" testid="stat-drafts" />
            <StatCard overline="Publiés" value={loading ? "—" : stats?.published ?? 0} tone="success" hint="Envoyés vers Wix" testid="stat-published" />
            <StatCard
              overline="Dernier audit"
              value={stats?.last_audit ? `${stats.last_audit.score}/100` : "—"}
              tone="accent"
              hint={stats?.last_audit ? `${stats.last_audit.total_pages} pages` : "Aucun audit"}
              testid="stat-audit-score"
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mt-6">
            <Link
              to="/audit"
              data-testid="quick-action-audit"
              className="group border border-slate-200 bg-white rounded-md p-5 hover:border-[#002FA7] hover:shadow-sm transition-all"
            >
              <Search className="w-5 h-5 text-[#002FA7] mb-3" />
              <div className="font-display font-semibold text-slate-950 mb-1">Lancer un audit SEO</div>
              <p className="text-xs text-slate-600 leading-relaxed">
                Détectez automatiquement titres manquants, méta trop courtes, H1 absents et alt manquants.
              </p>
              <div className="mt-3 text-xs font-medium text-[#002FA7] flex items-center gap-1 group-hover:gap-2 transition-all">
                Auditer maintenant <ArrowUpRight className="w-3 h-3" />
              </div>
            </Link>

            <Link
              to="/generator"
              data-testid="quick-action-generate"
              className="group border border-slate-200 bg-white rounded-md p-5 hover:border-[#002FA7] hover:shadow-sm transition-all"
            >
              <Sparkles className="w-5 h-5 text-[#002FA7] mb-3" />
              <div className="font-display font-semibold text-slate-950 mb-1">Générer du contenu IA</div>
              <p className="text-xs text-slate-600 leading-relaxed">
                Articles, pages locales, FAQ optimisés Google + AI Overviews via Claude Sonnet 4.5.
              </p>
              <div className="mt-3 text-xs font-medium text-[#002FA7] flex items-center gap-1 group-hover:gap-2 transition-all">
                Créer du contenu <ArrowUpRight className="w-3 h-3" />
              </div>
            </Link>

            <Link
              to="/drafts"
              data-testid="quick-action-drafts"
              className="group border border-slate-200 bg-white rounded-md p-5 hover:border-[#002FA7] hover:shadow-sm transition-all"
            >
              <FileText className="w-5 h-5 text-[#002FA7] mb-3" />
              <div className="font-display font-semibold text-slate-950 mb-1">Brouillons & publication</div>
              <p className="text-xs text-slate-600 leading-relaxed">
                Relisez, éditez et publiez vos contenus sur Wix après validation manuelle.
              </p>
              <div className="mt-3 text-xs font-medium text-[#002FA7] flex items-center gap-1 group-hover:gap-2 transition-all">
                Voir les brouillons <ArrowUpRight className="w-3 h-3" />
              </div>
            </Link>
          </div>

          <div className="border border-slate-200 bg-white rounded-md p-5 mt-6" data-testid="dashboard-checklist">
            <div className="overline mb-3">Recommandations IA</div>
            <ul className="space-y-2.5">
              {[
                "Audit complet sur les pages les plus visitées en priorité.",
                "Générer une page locale pour chaque grande ville cible (densité de mots-clés locaux).",
                "Ajouter une FAQ structurée par article pour maximiser la présence dans AI Overviews.",
                "Vérifier la cohérence des H1 sur Logirent et Logitime (un H1 unique par page).",
              ].map((tip) => (
                <li key={tip} className="flex items-start gap-2 text-sm text-slate-700">
                  <CheckCircle2 className="w-4 h-4 text-[#16A34A] flex-shrink-0 mt-0.5" />
                  <span>{tip}</span>
                </li>
              ))}
            </ul>
          </div>
        </>
      )}
    </div>
  );
}
