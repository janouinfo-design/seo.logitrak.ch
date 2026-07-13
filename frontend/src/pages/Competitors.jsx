import { useCallback, useEffect, useRef, useState } from "react";
import { useSites } from "@/contexts/SiteContext";
import { api } from "@/lib/api";
import { toast } from "sonner";
import {
  Swords,
  Loader2,
  Sparkles,
  RefreshCw,
  ShieldCheck,
  FileText,
  MapPin,
  Target,
  Flag,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const IMPACT_STYLE = {
  "élevé": "bg-red-100 text-red-700",
  moyen: "bg-amber-100 text-amber-700",
  faible: "bg-slate-100 text-slate-600",
};
const TYPE_LABEL = {
  article: "Article",
  page_locale: "Page locale",
  faq: "FAQ",
  service_description: "Page service",
};

export default function Competitors() {
  const { activeSite } = useSites();
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [generating, setGenerating] = useState(new Set());
  const pollRef = useRef(null);

  const loadLatest = useCallback(async () => {
    if (!activeSite) { setLoading(false); return; }
    setLoading(true);
    try {
      const { data } = await api.get(`/sites/${activeSite.id}/competitor-analysis/latest`);
      setReport(data && data.summary ? data : null);
    } catch {
      setReport(null);
    } finally {
      setLoading(false);
    }
  }, [activeSite]);

  useEffect(() => {
    loadLatest();
    return () => clearInterval(pollRef.current);
  }, [loadLatest]);

  const launch = async () => {
    if (!activeSite) return;
    setRunning(true);
    try {
      const { data } = await api.post(`/sites/${activeSite.id}/competitor-analysis`);
      toast.info("Analyse concurrentielle lancée — l'IA étudie vos concurrents…");
      let attempts = 0;
      pollRef.current = setInterval(async () => {
        attempts += 1;
        if (attempts > 90) {
          clearInterval(pollRef.current);
          setRunning(false);
          toast.error("L'analyse prend trop de temps. Réessayez.");
          return;
        }
        try {
          const { data: job } = await api.get(`/content/jobs/${data.job_id}`);
          if (job.status === "completed") {
            clearInterval(pollRef.current);
            setReport(job.result);
            setRunning(false);
            toast.success("Plan de bataille prêt !");
          } else if (job.status === "failed") {
            clearInterval(pollRef.current);
            setRunning(false);
            toast.error(job.error || "L'analyse a échoué.");
          }
        } catch { /* keep polling */ }
      }, 4000);
    } catch (e) {
      setRunning(false);
      toast.error(e?.response?.data?.detail || "Impossible de lancer l'analyse.");
    }
  };

  const generateContent = async (gap, genKey) => {
    setGenerating((s) => new Set(s).add(genKey));
    try {
      const { data } = await api.post("/content/generate-async", {
        site_id: activeSite.id,
        content_type: gap.type || "article",
        topic: gap.title,
        keywords: gap.target_keywords || [],
        city: gap.city || null,
        tone: "professionnel",
        target_length: "moyen",
      });
      toast.info("Génération lancée — le brouillon arrive dans « Brouillons » (1-2 min).");
      const interval = setInterval(async () => {
        try {
          const { data: job } = await api.get(`/content/jobs/${data.job_id}`);
          if (job.status === "completed") {
            clearInterval(interval);
            setGenerating((s) => { const n = new Set(s); n.delete(genKey); return n; });
            toast.success(`Brouillon « ${job.result?.title || ""} » prêt !`);
          } else if (job.status === "failed") {
            clearInterval(interval);
            setGenerating((s) => { const n = new Set(s); n.delete(genKey); return n; });
            toast.error(job.error || "Génération échouée");
          }
        } catch { /* keep polling */ }
      }, 5000);
    } catch (e) {
      setGenerating((s) => { const n = new Set(s); n.delete(genKey); return n; });
      toast.error(e?.response?.data?.detail || "Impossible de lancer la génération.");
    }
  };

  if (!activeSite) {
    return (
      <div className="p-8">
        <div className="text-slate-600" data-testid="competitors-no-site">Connectez d'abord un site pour lancer l'analyse.</div>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-6xl" data-testid="competitors-page">
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-2.5 mb-1">
            <div className="w-9 h-9 rounded-md bg-[#002FA7] flex items-center justify-center">
              <Swords className="w-5 h-5 text-white" />
            </div>
            <h1 className="font-display text-2xl font-bold text-slate-950">Analyse concurrentielle</h1>
          </div>
          <p className="text-sm text-slate-600 max-w-2xl">
            L'IA compare votre site à vos vrais concurrents (définis dans le Business Analyzer) :
            mots-clés qu'ils dominent, contenus qui vous manquent, et plan de bataille priorisé.
          </p>
        </div>
        <Button
          onClick={launch}
          disabled={running}
          data-testid="competitors-launch-button"
          className="bg-[#002FA7] hover:bg-[#00248A] text-white"
        >
          {running ? (
            <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Analyse en cours…</>
          ) : report ? (
            <><RefreshCw className="w-4 h-4 mr-2" /> Relancer l'analyse</>
          ) : (
            <><Sparkles className="w-4 h-4 mr-2" /> Lancer l'analyse</>
          )}
        </Button>
      </div>

      {running && (
        <div className="border border-[#002FA7]/20 bg-blue-50/50 rounded-lg p-4 mb-6 flex items-center gap-3" data-testid="competitors-running-banner">
          <Loader2 className="w-5 h-5 text-[#002FA7] animate-spin flex-shrink-0" />
          <div className="text-sm text-slate-700">
            <span className="font-semibold">Analyse en cours (1-3 min)</span> — crawl de votre site et des concurrents,
            puis construction du plan de bataille.
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center gap-2 text-slate-500 py-16 justify-center">
          <Loader2 className="w-5 h-5 animate-spin" /> Chargement…
        </div>
      ) : !report ? (
        !running && (
          <div className="border border-dashed border-slate-300 rounded-lg p-12 text-center" data-testid="competitors-empty-state">
            <Swords className="w-10 h-10 text-slate-300 mx-auto mb-3" />
            <div className="font-semibold text-slate-900 mb-1">Aucune analyse pour {activeSite.name}</div>
            <div className="text-sm text-slate-500">
              Prérequis : des concurrents définis dans le Business Analyzer (l'IA les propose, vous pouvez les corriger).
            </div>
          </div>
        )
      ) : (
        <div className="space-y-6">
          {/* Summary */}
          <div className="border border-[#002FA7]/20 bg-blue-50/40 rounded-lg p-5" data-testid="competitors-summary">
            <div className="flex items-center gap-2 mb-2">
              <Flag className="w-4 h-4 text-[#002FA7]" />
              <div className="text-sm font-semibold text-slate-900">Paysage concurrentiel</div>
            </div>
            <p className="text-sm text-slate-700 leading-relaxed">{report.summary}</p>
            <div className="mt-2 text-[11px] text-slate-400">
              Analyse du {new Date(report.created_at).toLocaleString("fr-FR")}
              {report.competitors_crawled?.length ? ` — sites crawlés : ${report.competitors_crawled.join(", ")}` : ""}
            </div>
          </div>

          {/* Your advantages */}
          <div className="border border-green-200 bg-green-50/50 rounded-lg p-5" data-testid="competitors-advantages">
            <div className="flex items-center gap-2 font-semibold text-green-800 text-sm mb-3">
              <ShieldCheck className="w-4 h-4" /> Vos avantages face à eux
            </div>
            <ul className="space-y-2">
              {(report.your_advantages || []).map((a, i) => (
                <li key={i} className="text-sm text-slate-700 flex gap-2">
                  <span className="text-green-600 flex-shrink-0">✓</span> {a}
                </li>
              ))}
            </ul>
          </div>

          {/* Per-competitor */}
          <div>
            <h2 className="text-base font-display font-bold text-slate-950 mb-3">Concurrent par concurrent</h2>
            <div className="space-y-3" data-testid="competitors-list">
              {(report.competitors || []).map((c, i) => (
                <div key={i} className="border border-slate-200 bg-white rounded-lg p-4" data-testid={`competitor-card-${i}`}>
                  <div className="flex items-center justify-between flex-wrap gap-2 mb-2">
                    <div className="font-semibold text-sm text-slate-900">{c.name}</div>
                    <div className="text-xs text-slate-500 italic">{c.positioning}</div>
                  </div>
                  {(c.keywords_they_dominate || []).length > 0 && (
                    <div className="mb-2">
                      <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-1.5">Mots-clés qu'il domine</div>
                      <div className="flex flex-wrap gap-1.5">
                        {c.keywords_they_dominate.map((k, ki) => (
                          <span key={ki} title={k.why} className="text-[11px] px-2 py-0.5 rounded-full bg-red-50 text-red-700 border border-red-200 font-medium cursor-help">
                            {k.keyword}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs mt-2">
                    <div><span className="font-semibold text-slate-700">Forces :</span> <span className="text-slate-600">{c.their_strengths}</span></div>
                    <div><span className="font-semibold text-slate-700">Faiblesses :</span> <span className="text-slate-600">{c.their_weaknesses}</span></div>
                    <div><span className="font-semibold text-green-700">Comment le battre :</span> <span className="text-slate-600">{c.how_to_beat}</span></div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Content gaps */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <FileText className="w-4 h-4 text-[#002FA7]" />
              <h2 className="text-base font-display font-bold text-slate-950">Contenus qu'ils ont — et pas vous</h2>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3" data-testid="competitors-gaps">
              {(report.content_gaps || []).map((g, i) => {
                const genKey = `gap-${i}`;
                return (
                  <div key={i} className="border border-slate-200 bg-white rounded-lg p-4 flex flex-col">
                    <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                      <Badge variant="outline" className="text-[9px] border-[#002FA7] text-[#002FA7]">{TYPE_LABEL[g.type] || g.type}</Badge>
                      {g.inspired_by && <span className="text-[10px] text-red-600 font-medium">chez {g.inspired_by}</span>}
                      {g.city && <span className="text-[10px] text-slate-500 flex items-center gap-0.5"><MapPin className="w-3 h-3" />{g.city}</span>}
                    </div>
                    <div className="font-semibold text-sm text-slate-900 mb-1">{g.title}</div>
                    <p className="text-xs text-slate-600 flex-1">{g.why}</p>
                    <div className="mt-2 text-[11px] text-slate-500">Cibles : {(g.target_keywords || []).join(", ")}</div>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => generateContent(g, genKey)}
                      disabled={generating.has(genKey)}
                      data-testid={`competitors-generate-gap-${i}`}
                      className="mt-3 border-[#002FA7] text-[#002FA7] hover:bg-blue-50 w-fit"
                    >
                      {generating.has(genKey) ? (
                        <><Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> Génération…</>
                      ) : (
                        <><Sparkles className="w-3.5 h-3.5 mr-1.5" /> Combler ce gap</>
                      )}
                    </Button>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Battle plan */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Target className="w-4 h-4 text-[#002FA7]" />
              <h2 className="text-base font-display font-bold text-slate-950">Plan de bataille</h2>
            </div>
            <div className="space-y-3" data-testid="competitors-battle-plan">
              {(report.battle_plan || []).map((a, i) => (
                <div key={i} className="border border-slate-200 bg-white rounded-lg p-4 flex items-start gap-3">
                  <div className="text-lg font-display font-bold text-[#002FA7] w-6 flex-shrink-0">{i + 1}</div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 flex-wrap mb-0.5">
                      <div className="font-semibold text-sm text-slate-900">{a.action}</div>
                      <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${IMPACT_STYLE[a.impact] || IMPACT_STYLE.faible}`}>
                        Impact {a.impact}
                      </span>
                      <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold bg-slate-100 text-slate-600">Effort {a.effort}</span>
                      {a.timeframe && <span className="text-[10px] text-slate-500">{a.timeframe}</span>}
                    </div>
                    <p className="text-xs text-slate-600">{a.details}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
