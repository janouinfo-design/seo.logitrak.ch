import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { useSites } from "@/contexts/SiteContext";
import PageHeader from "@/components/PageHeader";
import {
  ArrowUpRight, Sparkles, BookOpen, Search, Bot, PenLine, Share2,
  TrendingDown, CheckCircle2, AlertTriangle, Zap, Linkedin, Facebook, Instagram, MapPin,
} from "lucide-react";

const STATUS = {
  active: { label: "Actif", cls: "bg-green-50 text-green-700 border-green-200" },
  action: { label: "Action requise", cls: "bg-amber-50 text-amber-700 border-amber-200" },
  setup: { label: "À configurer", cls: "bg-slate-100 text-slate-600 border-slate-200" },
};

function StatusBadge({ status }) {
  const s = STATUS[status] || STATUS.setup;
  return (
    <span className={`text-[11px] font-medium border px-2 py-0.5 rounded-full ${s.cls}`}>
      {status === "active" && <span className="inline-block w-1.5 h-1.5 rounded-full bg-green-500 mr-1.5 align-middle animate-pulse" />}
      {s.label}
    </span>
  );
}

function Metric({ label, value, tone }) {
  const cls = tone === "accent" ? "text-[#002FA7]" : tone === "warn" ? "text-amber-600" : "text-slate-950";
  return (
    <div>
      <div className={`font-mono text-2xl font-semibold tracking-tight ${cls}`}>{value}</div>
      <div className="text-[11px] text-slate-500 mt-0.5">{label}</div>
    </div>
  );
}

function AgentCard({ testid, icon: Icon, color, name, role, status, metrics, children, cta, ctaTo }) {
  return (
    <div className="border border-slate-200 bg-white rounded-md p-5 hover:border-slate-300 hover:shadow-sm transition-all flex flex-col" data-testid={testid}>
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-md flex items-center justify-center" style={{ backgroundColor: `${color}14` }}>
            <Icon className="w-5 h-5" style={{ color }} />
          </div>
          <div>
            <div className="font-display font-semibold text-slate-950 leading-tight">{name}</div>
            <div className="text-[11px] text-slate-500">{role}</div>
          </div>
        </div>
        <StatusBadge status={status} />
      </div>
      <div className="grid grid-cols-3 gap-3 mb-4">{metrics}</div>
      <div className="flex-1">{children}</div>
      <Link
        to={ctaTo}
        data-testid={`${testid}-cta`}
        className="mt-4 inline-flex items-center gap-1 text-xs font-medium text-[#002FA7] hover:gap-2 transition-all"
      >
        {cta} <ArrowUpRight className="w-3 h-3" />
      </Link>
    </div>
  );
}

function InsightLine({ icon: Icon, tone = "default", children }) {
  const cls = tone === "warn" ? "text-amber-700" : tone === "ok" ? "text-green-700" : "text-slate-600";
  const iconCls = tone === "warn" ? "text-amber-500" : tone === "ok" ? "text-green-600" : "text-slate-400";
  return (
    <div className={`flex items-start gap-2 text-xs ${cls} leading-relaxed`}>
      <Icon className={`w-3.5 h-3.5 flex-shrink-0 mt-0.5 ${iconCls}`} />
      <span>{children}</span>
    </div>
  );
}

const fmtDate = (d) => (d ? new Date(d).toLocaleDateString("fr-FR") : null);

export default function Dashboard() {
  const { activeSite, sites } = useSites();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [notifications, setNotifications] = useState([]);

  useEffect(() => {
    setLoading(true);
    api.get("/agents/overview", { params: activeSite ? { site_id: activeSite.id } : {} })
      .then(({ data }) => setData(data))
      .finally(() => setLoading(false));
    api.get("/notifications", { params: { unread_only: true } })
      .then(({ data }) => setNotifications(data.notifications || []))
      .catch(() => {});
  }, [activeSite]);

  const dismissNotifications = async () => {
    try {
      await api.post("/notifications/read", { all: true });
      setNotifications([]);
    } catch { /* noop */ }
  };

  const seo = data?.seo;
  const geo = data?.geo;
  const content = data?.content;
  const social = data?.social;

  const seoStatus = !seo?.audit ? "setup" : (seo.rank_drops?.length > 0 || seo.audit.score < 60) ? "action" : "active";
  const geoStatus = !geo?.report ? "setup" : geo.report.global_score < 60 ? "action" : "active";
  const contentStatus = !content ? "setup" : content.quota.used >= content.quota.limit ? "action" : content.pending > 0 ? "action" : "active";
  const socialStatus = !social ? "setup" : social.connected_count === 0 ? "setup" : "active";

  const NETWORKS = [
    { key: "linkedin", label: "LinkedIn", icon: Linkedin, color: "#0A66C2" },
    { key: "facebook", label: "Facebook", icon: Facebook, color: "#1877F2" },
    { key: "instagram", label: "Instagram", icon: Instagram, color: "#E4405F" },
    { key: "gbp", label: "Google Business", icon: MapPin, color: "#34A853" },
  ];

  return (
    <div className="p-6 md:p-8 max-w-7xl">
      <PageHeader
        overline={activeSite ? `Contexte · ${activeSite.label}` : "Votre équipe IA"}
        title="Vos 4 agents marketing IA"
        description="Une équipe d'agents spécialisés qui analyse, rédige et publie pour vous — 24h/24."
        action={
          <a
            href="/guide-logi-seo-booster.pdf"
            target="_blank"
            rel="noopener noreferrer"
            data-testid="download-guide-pdf"
            className="inline-flex items-center gap-2 border border-slate-300 bg-white hover:border-[#002FA7] hover:text-[#002FA7] text-slate-700 px-4 py-2 rounded-md text-sm font-medium transition-colors shadow-sm"
          >
            <BookOpen className="w-4 h-4" /> Guide PDF
          </a>
        }
      />

      {notifications.length > 0 && (
        <div className="mb-5 border border-amber-200 bg-amber-50 rounded-md p-4" data-testid="dashboard-notifications">
          <div className="flex items-center justify-between mb-2">
            <div className="text-xs font-semibold text-amber-800 uppercase tracking-wide flex items-center gap-1.5">
              <Zap className="w-3.5 h-3.5" /> Notifications de vos agents ({notifications.length})
            </div>
            <button
              onClick={dismissNotifications}
              data-testid="dashboard-notifications-dismiss"
              className="text-xs font-medium text-amber-700 hover:text-amber-900 hover:underline"
            >
              Tout marquer comme lu
            </button>
          </div>
          <ul className="space-y-1.5">
            {notifications.slice(0, 5).map((n) => (
              <li key={n.id} className="text-xs text-amber-900 leading-relaxed">
                <span className="font-semibold">{n.title}</span> — {n.message}
                <span className="text-amber-600/70 ml-1">({new Date(n.created_at).toLocaleString("fr-FR")})</span>
              </li>
            ))}
            {notifications.length > 5 && (
              <li className="text-[11px] text-amber-600">+ {notifications.length - 5} autres…</li>
            )}
          </ul>
        </div>
      )}

      {sites.length === 0 ? (
        <div className="border border-slate-200 bg-white rounded-md p-8 text-center" data-testid="dashboard-empty-state">
          <div className="w-12 h-12 rounded-md bg-slate-100 flex items-center justify-center mx-auto mb-4">
            <Sparkles className="w-6 h-6 text-[#002FA7]" />
          </div>
          <h2 className="font-display text-xl font-semibold text-slate-950 mb-2">Connectez votre premier site</h2>
          <p className="text-sm text-slate-600 max-w-md mx-auto mb-5">
            Ajoutez l&apos;URL de votre site pour activer vos 4 agents : audit SEO, visibilité IA, génération de contenu et publication multi-réseaux.
          </p>
          <Link
            to="/sites"
            data-testid="dashboard-connect-site-cta"
            className="inline-flex items-center gap-2 bg-[#002FA7] hover:bg-[#001D6B] text-white px-4 py-2.5 rounded-md text-sm font-medium transition-colors shadow-sm"
          >
            Connecter un site <ArrowUpRight className="w-4 h-4" />
          </Link>
        </div>
      ) : loading ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="border border-slate-200 bg-white rounded-md p-5 h-56 animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Agent SEO */}
          <AgentCard
            testid="agent-seo-card"
            icon={Search}
            color="#002FA7"
            name="Agent SEO"
            role="Audit technique · positions Google"
            status={seoStatus}
            cta={seo?.audit ? "Ouvrir l'audit SEO" : "Lancer le premier audit"}
            ctaTo="/audit"
            metrics={<>
              <Metric label="Score audit" value={seo?.audit ? `${seo.audit.score}` : "—"} tone={seo?.audit?.score < 60 ? "warn" : "accent"} />
              <Metric label="Mots-clés suivis" value={seo?.gsc_connected ? seo.tracked_keywords : seo?.saved_keywords ?? 0} />
              <Metric label="Problèmes détectés" value={seo?.audit?.issues_count ?? "—"} tone={seo?.audit?.issues_count > 0 ? "warn" : "default"} />
            </>}
          >
            {seo?.rank_drops?.length > 0 ? (
              <div className="space-y-1.5">
                {seo.rank_drops.slice(0, 2).map((d) => (
                  <InsightLine key={d.keyword} icon={TrendingDown} tone="warn">
                    « {d.keyword} » : position {d.from} → {d.to}
                  </InsightLine>
                ))}
              </div>
            ) : !seo?.audit ? (
              <InsightLine icon={Zap}>Aucun audit pour l&apos;instant — lancez votre premier diagnostic en 2 minutes.</InsightLine>
            ) : !seo?.gsc_connected ? (
              <InsightLine icon={AlertTriangle} tone="warn">Connectez Google Search Console (page Performance) pour activer la surveillance quotidienne des positions.</InsightLine>
            ) : (
              <InsightLine icon={CheckCircle2} tone="ok">Aucune chute de position détectée. Dernier audit : {fmtDate(seo.audit.created_at)}.</InsightLine>
            )}
          </AgentCard>

          {/* Agent GEO */}
          <AgentCard
            testid="agent-geo-card"
            icon={Bot}
            color="#7C3AED"
            name="Agent GEO"
            role="Visibilité ChatGPT · Claude · Gemini"
            status={geoStatus}
            cta={geo?.report ? "Ouvrir AI Visibility" : "Analyser ma visibilité IA"}
            ctaTo="/ai-visibility"
            metrics={<>
              <Metric label="Score AI Visibility" value={geo?.report ? `${geo.report.global_score}` : "—"} tone={geo?.report?.global_score < 60 ? "warn" : "accent"} />
              <Metric label="Actions prioritaires" value={geo?.actions?.length ?? 0} tone={geo?.actions?.length > 0 ? "warn" : "default"} />
              <Metric label="Dernière analyse" value={geo?.report ? fmtDate(geo.report.created_at) : "—"} />
            </>}
          >
            {geo?.actions?.length > 0 ? (
              <div className="space-y-1.5">
                {geo.actions.slice(0, 2).map((a) => (
                  <InsightLine key={a.action} icon={Zap} tone="warn">
                    {a.action}{a.estimated_gain ? ` (${a.estimated_gain})` : ""}
                  </InsightLine>
                ))}
              </div>
            ) : geo?.report ? (
              <InsightLine icon={CheckCircle2} tone="ok">Votre site est bien positionné pour être cité par les IA.</InsightLine>
            ) : (
              <InsightLine icon={Zap}>Découvrez si ChatGPT et Gemini recommandent votre entreprise — et comment y remédier.</InsightLine>
            )}
          </AgentCard>

          {/* Agent Contenu */}
          <AgentCard
            testid="agent-content-card"
            icon={PenLine}
            color="#0D9488"
            name="Agent Contenu"
            role="Rédaction SEO · pages locales · FAQ"
            status={contentStatus}
            cta={content?.pending > 0 ? "Valider les brouillons" : "Générer du contenu"}
            ctaTo={content?.pending > 0 ? "/drafts" : "/generator"}
            metrics={<>
              <Metric label="À valider" value={content?.pending ?? 0} tone={content?.pending > 0 ? "warn" : "default"} />
              <Metric label="Publiés" value={content?.published ?? 0} tone="accent" />
              <Metric label={`Quota (${content?.quota?.plan || "Free"})`} value={content ? `${content.quota.used}/${content.quota.limit}` : "—"} tone={content && content.quota.used >= content.quota.limit ? "warn" : "default"} />
            </>}
          >
            {content && content.quota.used >= content.quota.limit ? (
              <InsightLine icon={AlertTriangle} tone="warn">Quota mensuel atteint — passez à un plan supérieur (page Facturation) pour continuer à générer.</InsightLine>
            ) : content?.last_draft ? (
              <InsightLine icon={CheckCircle2} tone={content.pending > 0 ? "default" : "ok"}>
                Dernier contenu : « {content.last_draft.title?.slice(0, 60)}{content.last_draft.title?.length > 60 ? "…" : ""} » ({content.last_draft.status}).
              </InsightLine>
            ) : (
              <InsightLine icon={Zap}>Aucun contenu généré — l&apos;agent peut rédiger articles, pages locales et FAQ optimisés IA.</InsightLine>
            )}
          </AgentCard>

          {/* Agent Social */}
          <AgentCard
            testid="agent-social-card"
            icon={Share2}
            color="#EA580C"
            name="Agent Social"
            role="LinkedIn · Facebook · Instagram · Google Business"
            status={socialStatus}
            cta={social?.connected_count === 0 ? "Connecter vos réseaux" : "Publier un contenu"}
            ctaTo="/drafts"
            metrics={<>
              <Metric label="Réseaux connectés" value={`${social?.connected_count ?? 0}/4`} tone={social?.connected_count > 0 ? "accent" : "warn"} />
              <Metric label="Posts publiés" value={social?.total_posts ?? 0} />
              <Metric label="Dernier post" value={
                (() => {
                  const dates = Object.values(social?.networks || {}).map((n) => n.last_posted_at).filter(Boolean).sort();
                  return dates.length ? fmtDate(dates[dates.length - 1]) : "—";
                })()
              } />
            </>}
          >
            <div className="flex flex-wrap gap-2">
              {NETWORKS.map(({ key, label, icon: Icon, color }) => {
                const n = social?.networks?.[key];
                return (
                  <span
                    key={key}
                    data-testid={`social-network-chip-${key}`}
                    className={`inline-flex items-center gap-1.5 text-[11px] border px-2 py-1 rounded-full ${n?.connected ? "border-slate-200 bg-white text-slate-700" : "border-dashed border-slate-200 text-slate-400"}`}
                  >
                    <Icon className="w-3 h-3" style={{ color: n?.connected ? color : "#94A3B8" }} />
                    {label}{n?.connected ? ` · ${n.posts}` : ""}
                  </span>
                );
              })}
            </div>
          </AgentCard>
        </div>
      )}
    </div>
  );
}
