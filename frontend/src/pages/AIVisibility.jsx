import { useCallback, useEffect, useRef, useState } from "react";
import { useSites } from "@/contexts/SiteContext";
import { api } from "@/lib/api";
import { toast } from "sonner";
import {
  Radar,
  Loader2,
  Sparkles,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  TrendingUp,
  Bot,
  RefreshCw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const SCORE_DEFS = [
  { key: "ai_citation_score", label: "AI Citation", desc: "Votre marque est-elle réellement citée par les IA ?" },
  { key: "ai_trust_score", label: "AI Trust", desc: "Confiance accordée par les moteurs de réponse IA" },
  { key: "eeat_score", label: "EEAT", desc: "Expérience, Expertise, Autorité, Fiabilité" },
  { key: "entity_score", label: "Entity SEO", desc: "Clarté de votre entité : marque, activité, zone" },
  { key: "schema_score", label: "Schema.org", desc: "Données structurées JSON-LD" },
  { key: "knowledge_graph_score", label: "Knowledge Graph", desc: "sameAs, Wikidata, profils officiels liés" },
  { key: "semantic_seo_score", label: "SEO Sémantique", desc: "Couverture thématique et réponses aux questions" },
  { key: "ai_readability_score", label: "Lisibilité IA", desc: "Structure exploitable par les LLM (chunking)" },
  { key: "freshness_score", label: "Fraîcheur", desc: "Actualité et datation des contenus" },
];

const MODEL_LOGOS = {
  chatgpt: "🟢",
  claude: "🟠",
  gemini: "🔵",
  perplexity: "🟣",
  copilot: "🟦",
  mistral: "🟧",
  deepseek: "🐳",
};

function scoreColor(v) {
  if (v >= 70) return "#15803D";
  if (v >= 40) return "#B45309";
  return "#B91C1C";
}

function scoreBg(v) {
  if (v >= 70) return "bg-green-50 border-green-200";
  if (v >= 40) return "bg-amber-50 border-amber-200";
  return "bg-red-50 border-red-200";
}

function GlobalScoreRing({ value }) {
  const r = 62;
  const c = 2 * Math.PI * r;
  const offset = c - (value / 100) * c;
  return (
    <div className="relative w-40 h-40" data-testid="aivis-global-score">
      <svg viewBox="0 0 150 150" className="w-40 h-40 -rotate-90">
        <circle cx="75" cy="75" r={r} fill="none" stroke="#E2E8F0" strokeWidth="10" />
        <circle
          cx="75" cy="75" r={r} fill="none"
          stroke={scoreColor(value)} strokeWidth="10" strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={offset}
          style={{ transition: "stroke-dashoffset 1s ease" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <div className="text-4xl font-bold font-display" style={{ color: scoreColor(value) }}>{value}</div>
        <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">/ 100</div>
      </div>
    </div>
  );
}

function ScoreCard({ def, value }) {
  return (
    <div className="border border-slate-200 bg-white rounded-lg p-4" data-testid={`aivis-score-${def.key}`}>
      <div className="flex items-center justify-between mb-1.5">
        <div className="text-sm font-semibold text-slate-900">{def.label}</div>
        <div className="text-sm font-bold" style={{ color: scoreColor(value) }}>{value}</div>
      </div>
      <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden mb-2">
        <div className="h-full rounded-full transition-all duration-700" style={{ width: `${value}%`, background: scoreColor(value) }} />
      </div>
      <div className="text-[11px] text-slate-500 leading-snug">{def.desc}</div>
    </div>
  );
}

function ModelCard({ m }) {
  return (
    <div className={`border rounded-lg p-3.5 ${m.unavailable ? "border-slate-200 bg-slate-50" : scoreBg(m.mention_rate ?? 0)}`} data-testid={`aivis-model-${m.key}`}>
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-1.5 text-sm font-semibold text-slate-900">
          <span>{MODEL_LOGOS[m.key] || "🤖"}</span>
          {m.name}
        </div>
        <Badge variant="outline" className={`text-[9px] px-1.5 py-0 ${m.measured ? "border-[#002FA7] text-[#002FA7]" : "border-slate-300 text-slate-500"}`}>
          {m.measured ? "Mesuré" : "Estimé"}
        </Badge>
      </div>
      {m.unavailable ? (
        <div className="text-xs text-slate-500">Indisponible</div>
      ) : (
        <div className="flex items-center gap-2">
          {m.visible ? (
            <CheckCircle2 className="w-4 h-4 text-green-600" />
          ) : (
            <XCircle className="w-4 h-4 text-red-500" />
          )}
          <span className="text-xs text-slate-700">
            {m.visible ? "Cité" : "Non cité"}
            {m.mention_rate !== null && m.mention_rate !== undefined && ` — ${m.mention_rate}% des tests`}
          </span>
        </div>
      )}
    </div>
  );
}

const IMPACT_STYLE = {
  "élevé": "bg-red-100 text-red-700",
  moyen: "bg-amber-100 text-amber-700",
  faible: "bg-slate-100 text-slate-600",
};

export default function AIVisibility() {
  const { activeSite } = useSites();
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const pollRef = useRef(null);

  const loadLatest = useCallback(async () => {
    if (!activeSite) { setLoading(false); return; }
    setLoading(true);
    try {
      const { data } = await api.get(`/sites/${activeSite.id}/ai-visibility/latest`);
      setReport(data && data.global_score !== undefined ? data : null);
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
      const { data } = await api.post(`/sites/${activeSite.id}/ai-visibility`);
      const jobId = data.job_id;
      toast.info("Analyse AI Visibility lancée — interrogation des moteurs IA en cours…");
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
          const { data: job } = await api.get(`/content/jobs/${jobId}`);
          if (job.status === "completed") {
            clearInterval(pollRef.current);
            setReport(job.result);
            setRunning(false);
            toast.success("Analyse AI Visibility terminée !");
          } else if (job.status === "failed") {
            clearInterval(pollRef.current);
            setRunning(false);
            toast.error(job.error || "L'analyse a échoué.");
          }
        } catch {
          /* keep polling */
        }
      }, 4000);
    } catch (e) {
      setRunning(false);
      toast.error(e?.response?.data?.detail || "Impossible de lancer l'analyse.");
    }
  };

  if (!activeSite) {
    return (
      <div className="p-8">
        <div className="text-slate-600" data-testid="aivis-no-site">Connectez d'abord un site pour lancer une analyse AI Visibility.</div>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-6xl" data-testid="aivis-page">
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-2.5 mb-1">
            <div className="w-9 h-9 rounded-md bg-[#002FA7] flex items-center justify-center">
              <Radar className="w-5 h-5 text-white" />
            </div>
            <h1 className="font-display text-2xl font-bold text-slate-950">AI Visibility Center</h1>
          </div>
          <p className="text-sm text-slate-600 max-w-2xl">
            Mesurez si votre entreprise est citée par ChatGPT, Gemini, Claude, Perplexity & co. —
            et découvrez exactement quoi faire pour devenir la référence recommandée par les IA.
          </p>
        </div>
        <Button
          onClick={launch}
          disabled={running}
          data-testid="aivis-launch-button"
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
        <div className="border border-[#002FA7]/20 bg-blue-50/50 rounded-lg p-4 mb-6 flex items-center gap-3" data-testid="aivis-running-banner">
          <Loader2 className="w-5 h-5 text-[#002FA7] animate-spin flex-shrink-0" />
          <div className="text-sm text-slate-700">
            <span className="font-semibold">Analyse en cours (2-3 min)</span> — crawl du site, audit Schema.org / EEAT / entités,
            puis tests de citation réels sur ChatGPT, Claude et Gemini.
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center gap-2 text-slate-500 py-16 justify-center">
          <Loader2 className="w-5 h-5 animate-spin" /> Chargement…
        </div>
      ) : !report ? (
        !running && (
          <div className="border border-dashed border-slate-300 rounded-lg p-12 text-center" data-testid="aivis-empty-state">
            <Bot className="w-10 h-10 text-slate-300 mx-auto mb-3" />
            <div className="font-semibold text-slate-900 mb-1">Aucune analyse pour {activeSite.name}</div>
            <div className="text-sm text-slate-500 mb-0">
              Lancez votre première analyse pour connaître votre visibilité dans les moteurs de réponse IA.
            </div>
          </div>
        )
      ) : (
        <div className="space-y-6">
          {/* Hero: global score + summary */}
          <div className="border border-slate-200 bg-white rounded-lg p-6 flex flex-col md:flex-row gap-6 items-center">
            <GlobalScoreRing value={report.global_score} />
            <div className="flex-1">
              <div className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 mb-1">AI Visibility Score</div>
              <div className="text-lg font-display font-bold text-slate-950 mb-2">
                {report.global_score >= 70 ? "Bien positionné dans les IA" : report.global_score >= 40 ? "Visibilité IA partielle" : "Quasi invisible pour les IA"}
              </div>
              <p className="text-sm text-slate-600 leading-relaxed" data-testid="aivis-summary">{report.explanations?.summary}</p>
              {report.business?.summary && (
                <div className="mt-3 text-xs text-slate-500">
                  <span className="font-semibold">Activité détectée :</span> {report.business.summary}
                </div>
              )}
              <div className="mt-2 text-[11px] text-slate-400">
                Analyse du {new Date(report.created_at).toLocaleString("fr-FR")} — {report.pages_analyzed?.length || 0} pages analysées
              </div>
            </div>
          </div>

          {/* Per-model visibility */}
          <div>
            <h2 className="text-base font-display font-bold text-slate-950 mb-1">Visibilité par moteur IA</h2>
            <p className="text-xs text-slate-500 mb-3">
              Tests réels effectués sur ChatGPT, Claude et Gemini avec {report.queries_tested?.length || 0} requêtes utilisateur.
              Les autres moteurs sont estimés à partir des résultats mesurés.
            </p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="aivis-models-grid">
              {(report.models || []).map((m) => <ModelCard key={m.key} m={m} />)}
            </div>
            {report.queries_tested?.length > 0 && (
              <details className="mt-3">
                <summary className="text-xs text-slate-500 cursor-pointer hover:text-slate-700">Voir les requêtes testées</summary>
                <ul className="mt-2 space-y-1">
                  {report.queries_tested.map((q, i) => (
                    <li key={i} className="text-xs text-slate-600 pl-3 border-l-2 border-slate-200">« {q} »</li>
                  ))}
                </ul>
              </details>
            )}
          </div>

          {/* Sub-scores */}
          <div>
            <h2 className="text-base font-display font-bold text-slate-950 mb-3">Scores détaillés</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3" data-testid="aivis-scores-grid">
              {SCORE_DEFS.map((def) => (
                <ScoreCard key={def.key} def={def} value={report.scores?.[def.key] ?? 0} />
              ))}
            </div>
          </div>

          {/* Why / Why not */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="border border-green-200 bg-green-50/50 rounded-lg p-5" data-testid="aivis-why-visible">
              <div className="flex items-center gap-2 font-semibold text-green-800 text-sm mb-3">
                <CheckCircle2 className="w-4 h-4" /> Pourquoi les IA peuvent vous citer
              </div>
              <ul className="space-y-2">
                {(report.explanations?.why_visible || []).map((w, i) => (
                  <li key={i} className="text-sm text-slate-700 flex gap-2">
                    <span className="text-green-600 flex-shrink-0">✓</span> {w}
                  </li>
                ))}
              </ul>
            </div>
            <div className="border border-red-200 bg-red-50/50 rounded-lg p-5" data-testid="aivis-why-not-visible">
              <div className="flex items-center gap-2 font-semibold text-red-800 text-sm mb-3">
                <AlertTriangle className="w-4 h-4" /> Ce qui freine votre visibilité IA
              </div>
              <ul className="space-y-2">
                {(report.explanations?.why_not_visible || []).map((w, i) => (
                  <li key={i} className="text-sm text-slate-700 flex gap-2">
                    <span className="text-red-500 flex-shrink-0">✗</span> {w}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Priority actions */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <TrendingUp className="w-4 h-4 text-[#002FA7]" />
              <h2 className="text-base font-display font-bold text-slate-950">Actions prioritaires</h2>
            </div>
            <div className="space-y-3" data-testid="aivis-actions-list">
              {(report.priority_actions || []).map((a, i) => (
                <div key={i} className="border border-slate-200 bg-white rounded-lg p-4" data-testid={`aivis-action-${i}`}>
                  <div className="flex items-start justify-between gap-3 mb-1.5">
                    <div className="font-semibold text-sm text-slate-900">
                      <span className="text-[#002FA7] mr-2">{i + 1}.</span>{a.action}
                    </div>
                    <div className="flex items-center gap-1.5 flex-shrink-0">
                      <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${IMPACT_STYLE[a.impact] || IMPACT_STYLE.faible}`}>
                        Impact {a.impact}
                      </span>
                      <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold bg-slate-100 text-slate-600">
                        Effort {a.effort}
                      </span>
                    </div>
                  </div>
                  <p className="text-sm text-slate-600 leading-relaxed">{a.details}</p>
                  {a.estimated_gain && (
                    <div className="mt-2 text-xs font-semibold text-green-700">Gain estimé : {a.estimated_gain}</div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Technical signals */}
          <details className="border border-slate-200 bg-white rounded-lg p-5" data-testid="aivis-technical-details">
            <summary className="text-sm font-semibold text-slate-900 cursor-pointer">Détails techniques de l'audit</summary>
            <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-5 text-sm">
              <div>
                <div className="font-semibold text-slate-800 mb-2">Schema.org ({report.technical?.schema?.score}/100)</div>
                <ul className="space-y-1">
                  {(report.technical?.schema?.checks || []).map((c, i) => (
                    <li key={i} className="flex items-center gap-2 text-xs text-slate-600">
                      {c.ok ? <CheckCircle2 className="w-3.5 h-3.5 text-green-600" /> : <XCircle className="w-3.5 h-3.5 text-red-400" />}
                      {c.label}
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <div className="font-semibold text-slate-800 mb-2">Signaux EEAT</div>
                <ul className="space-y-1">
                  {(report.technical?.eeat_signals?.signals || []).map((s, i) => (
                    <li key={`s${i}`} className="flex items-center gap-2 text-xs text-slate-600">
                      <CheckCircle2 className="w-3.5 h-3.5 text-green-600 flex-shrink-0" /> {s}
                    </li>
                  ))}
                  {(report.technical?.eeat_signals?.missing || []).map((s, i) => (
                    <li key={`m${i}`} className="flex items-center gap-2 text-xs text-slate-600">
                      <XCircle className="w-3.5 h-3.5 text-red-400 flex-shrink-0" /> {s}
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <div className="font-semibold text-slate-800 mb-2">Knowledge Graph ({report.technical?.knowledge_graph?.score}/100)</div>
                <ul className="space-y-1">
                  {(report.technical?.knowledge_graph?.signals || []).length === 0 && (
                    <li className="text-xs text-slate-500">Aucun signal de graphe de connaissances détecté.</li>
                  )}
                  {(report.technical?.knowledge_graph?.signals || []).map((s, i) => (
                    <li key={i} className="flex items-center gap-2 text-xs text-slate-600">
                      <CheckCircle2 className="w-3.5 h-3.5 text-green-600 flex-shrink-0" /> {s}
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <div className="font-semibold text-slate-800 mb-2">Fraîcheur ({report.technical?.freshness?.score}/100)</div>
                <div className="text-xs text-slate-600">
                  {report.technical?.freshness?.latest_date
                    ? `Dernière date détectée : ${report.technical.freshness.latest_date} (${report.technical.freshness.age_days} jours)`
                    : report.technical?.freshness?.note}
                </div>
                <div className="font-semibold text-slate-800 mb-1 mt-3">Pages analysées</div>
                <ul className="space-y-0.5">
                  {(report.pages_analyzed || []).map((u, i) => (
                    <li key={i} className="text-[11px] text-slate-500 truncate">{u}</li>
                  ))}
                </ul>
              </div>
            </div>
          </details>
        </div>
      )}
    </div>
  );
}
