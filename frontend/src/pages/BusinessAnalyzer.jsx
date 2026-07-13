import { useCallback, useEffect, useRef, useState } from "react";
import { useSites } from "@/contexts/SiteContext";
import { api } from "@/lib/api";
import { toast } from "sonner";
import {
  Building2,
  Loader2,
  Sparkles,
  RefreshCw,
  Users,
  Package,
  MapPin,
  Swords,
  Pencil,
  Save,
  X,
  TrendingUp,
  ShieldCheck,
  ShieldAlert,
  Lightbulb,
  AlertTriangle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const IMPACT_STYLE = {
  "élevé": "bg-red-100 text-red-700",
  moyen: "bg-amber-100 text-amber-700",
  faible: "bg-slate-100 text-slate-600",
};

const SWOT_META = [
  { key: "strengths", label: "Forces", icon: ShieldCheck, cls: "border-green-200 bg-green-50/50", iconCls: "text-green-700" },
  { key: "weaknesses", label: "Faiblesses", icon: ShieldAlert, cls: "border-red-200 bg-red-50/50", iconCls: "text-red-700" },
  { key: "opportunities", label: "Opportunités", icon: Lightbulb, cls: "border-blue-200 bg-blue-50/50", iconCls: "text-[#002FA7]" },
  { key: "threats", label: "Menaces", icon: AlertTriangle, cls: "border-amber-200 bg-amber-50/50", iconCls: "text-amber-700" },
];

function SectionTitle({ icon: Icon, children }) {
  return (
    <div className="flex items-center gap-2 mb-3">
      <Icon className="w-4 h-4 text-[#002FA7]" />
      <h2 className="text-base font-display font-bold text-slate-950">{children}</h2>
    </div>
  );
}

export default function BusinessAnalyzer() {
  const { activeSite } = useSites();
  const [doc, setDoc] = useState(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);
  const pollRef = useRef(null);

  const profile = doc?.profile;

  const load = useCallback(async () => {
    if (!activeSite) { setLoading(false); return; }
    setLoading(true);
    try {
      const { data } = await api.get(`/sites/${activeSite.id}/business-profile`);
      setDoc(data && data.profile ? data : null);
    } catch {
      setDoc(null);
    } finally {
      setLoading(false);
    }
  }, [activeSite]);

  useEffect(() => {
    setEditing(false);
    load();
    return () => clearInterval(pollRef.current);
  }, [load]);

  const launch = async () => {
    if (!activeSite) return;
    setRunning(true);
    try {
      const { data } = await api.post(`/sites/${activeSite.id}/business-analyzer`);
      toast.info("Analyse business lancée — l'IA étudie votre entreprise en profondeur…");
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
            setDoc(job.result);
            setRunning(false);
            toast.success("Profil business complet généré !");
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

  const startEdit = () => {
    setForm({
      activity: profile.activity || "",
      description: profile.description || "",
      positioning: profile.positioning || "",
      cities_zones: (profile.cities_zones || []).join(", "),
      business_model: profile.business_model || "",
      competitors: (profile.competitors || []).map((c) => c.name).filter(Boolean).join("\n"),
    });
    setEditing(true);
  };

  const saveEdit = async () => {
    setSaving(true);
    try {
      const names = form.competitors.split("\n").map((n) => n.trim()).filter(Boolean);
      const existing = profile.competitors || [];
      const mergedCompetitors = names.map((n) => {
        const found = existing.find((c) => (c.name || "").toLowerCase() === n.toLowerCase());
        return found || { name: n };
      });
      const payload = {
        activity: form.activity,
        description: form.description,
        positioning: form.positioning,
        cities_zones: form.cities_zones.split(",").map((c) => c.trim()).filter(Boolean),
        business_model: form.business_model,
        competitors: mergedCompetitors,
      };
      const { data } = await api.put(`/sites/${activeSite.id}/business-profile`, { profile: payload });
      setDoc((d) => ({ ...d, profile: data.profile, edited: true }));
      setEditing(false);
      toast.success("Profil mis à jour — vos corrections alimenteront toutes les analyses IA.");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Erreur lors de la sauvegarde");
    } finally {
      setSaving(false);
    }
  };

  if (!activeSite) {
    return (
      <div className="p-8">
        <div className="text-slate-600" data-testid="bizanalyzer-no-site">Connectez d'abord un site pour lancer l'analyse.</div>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-6xl" data-testid="bizanalyzer-page">
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-2.5 mb-1">
            <div className="w-9 h-9 rounded-md bg-[#002FA7] flex items-center justify-center">
              <Building2 className="w-5 h-5 text-white" />
            </div>
            <h1 className="font-display text-2xl font-bold text-slate-950">Business Analyzer</h1>
          </div>
          <p className="text-sm text-slate-600 max-w-2xl">
            L'IA comprend votre entreprise en profondeur : offres, cibles, zones, concurrents, SWOT.
            Ce profil alimente Keyword Intelligence et les futurs agents IA — corrigez-le si nécessaire.
          </p>
        </div>
        <Button
          onClick={launch}
          disabled={running}
          data-testid="bizanalyzer-launch-button"
          className="bg-[#002FA7] hover:bg-[#00248A] text-white"
        >
          {running ? (
            <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Analyse en cours…</>
          ) : profile ? (
            <><RefreshCw className="w-4 h-4 mr-2" /> Relancer l'analyse</>
          ) : (
            <><Sparkles className="w-4 h-4 mr-2" /> Analyser mon business</>
          )}
        </Button>
      </div>

      {running && (
        <div className="border border-[#002FA7]/20 bg-blue-50/50 rounded-lg p-4 mb-6 flex items-center gap-3" data-testid="bizanalyzer-running-banner">
          <Loader2 className="w-5 h-5 text-[#002FA7] animate-spin flex-shrink-0" />
          <div className="text-sm text-slate-700">
            <span className="font-semibold">Analyse en cours (1-2 min)</span> — crawl de vos pages,
            puis analyse directeur marketing : offres, cibles, concurrents, SWOT, priorités.
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center gap-2 text-slate-500 py-16 justify-center">
          <Loader2 className="w-5 h-5 animate-spin" /> Chargement…
        </div>
      ) : !profile ? (
        !running && (
          <div className="border border-dashed border-slate-300 rounded-lg p-12 text-center" data-testid="bizanalyzer-empty-state">
            <Building2 className="w-10 h-10 text-slate-300 mx-auto mb-3" />
            <div className="font-semibold text-slate-900 mb-1">Aucun profil business pour {activeSite.name}</div>
            <div className="text-sm text-slate-500">
              Lancez l'analyse : sans compréhension du business, les recommandations IA sont moins pertinentes.
            </div>
          </div>
        )
      ) : (
        <div className="space-y-6">
          {/* Identity card */}
          <div className="border border-slate-200 bg-white rounded-lg p-5" data-testid="bizanalyzer-identity">
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-2">
                <h2 className="text-base font-display font-bold text-slate-950">Identité de l'entreprise</h2>
                {doc.edited && <Badge variant="outline" className="text-[9px] border-green-500 text-green-700">Corrigé par vous</Badge>}
              </div>
              {!editing ? (
                <Button size="sm" variant="outline" onClick={startEdit} data-testid="bizanalyzer-edit-button" className="text-slate-600">
                  <Pencil className="w-3.5 h-3.5 mr-1.5" /> Corriger
                </Button>
              ) : (
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={() => setEditing(false)} data-testid="bizanalyzer-cancel-button">
                    <X className="w-3.5 h-3.5 mr-1.5" /> Annuler
                  </Button>
                  <Button size="sm" onClick={saveEdit} disabled={saving} data-testid="bizanalyzer-save-button" className="bg-[#002FA7] text-white">
                    {saving ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Save className="w-3.5 h-3.5 mr-1.5" />} Enregistrer
                  </Button>
                </div>
              )}
            </div>

            {!editing ? (
              <>
                <p className="text-sm text-slate-700 mb-4">{profile.description}</p>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
                  <div>
                    <div className="font-semibold text-slate-500 uppercase tracking-wider text-[10px] mb-1">Activité</div>
                    <div className="text-slate-800">{profile.activity}</div>
                  </div>
                  <div>
                    <div className="font-semibold text-slate-500 uppercase tracking-wider text-[10px] mb-1">Modèle</div>
                    <div className="text-slate-800">{profile.business_model}</div>
                  </div>
                  <div>
                    <div className="font-semibold text-slate-500 uppercase tracking-wider text-[10px] mb-1">Zones</div>
                    <div className="text-slate-800">{(profile.cities_zones || []).join(", ")}</div>
                  </div>
                  <div>
                    <div className="font-semibold text-slate-500 uppercase tracking-wider text-[10px] mb-1">Ton de communication</div>
                    <div className="text-slate-800">{profile.tone_of_voice}</div>
                  </div>
                </div>
                {profile.positioning && (
                  <div className="mt-3 text-xs text-slate-600 border-t border-slate-100 pt-3">
                    <span className="font-semibold">Positionnement :</span> {profile.positioning}
                  </div>
                )}
                {(profile.value_props || []).length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {profile.value_props.map((v, i) => (
                      <span key={i} className="text-[11px] px-2 py-0.5 rounded-full bg-blue-50 text-[#002FA7] font-medium">{v}</span>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <div className="space-y-3" data-testid="bizanalyzer-edit-form">
                <div>
                  <label className="text-xs font-medium text-slate-700 mb-1 block">Activité</label>
                  <input value={form.activity} onChange={(e) => setForm({ ...form, activity: e.target.value })}
                    className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm" data-testid="bizanalyzer-input-activity" />
                </div>
                <div>
                  <label className="text-xs font-medium text-slate-700 mb-1 block">Description</label>
                  <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={3}
                    className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm" data-testid="bizanalyzer-input-description" />
                </div>
                <div>
                  <label className="text-xs font-medium text-slate-700 mb-1 block">Positionnement</label>
                  <textarea value={form.positioning} onChange={(e) => setForm({ ...form, positioning: e.target.value })} rows={2}
                    className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm" data-testid="bizanalyzer-input-positioning" />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-medium text-slate-700 mb-1 block">Zones (séparées par des virgules)</label>
                    <input value={form.cities_zones} onChange={(e) => setForm({ ...form, cities_zones: e.target.value })}
                      className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm" data-testid="bizanalyzer-input-zones" />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-slate-700 mb-1 block">Modèle (B2B, B2C, mixte…)</label>
                    <input value={form.business_model} onChange={(e) => setForm({ ...form, business_model: e.target.value })}
                      className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm" data-testid="bizanalyzer-input-model" />
                  </div>
                </div>
                <div>
                  <label className="text-xs font-medium text-slate-700 mb-1 block">Vos vrais concurrents (un par ligne)</label>
                  <textarea value={form.competitors} onChange={(e) => setForm({ ...form, competitors: e.target.value })} rows={5}
                    placeholder={"Myrentcar\nRenthub\nFleetGuru"}
                    className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm font-mono" data-testid="bizanalyzer-input-competitors" />
                  <p className="text-[11px] text-slate-500 mt-1">Cette liste alimente la recherche de mots-clés, Keyword Intelligence et les futures analyses concurrentielles.</p>
                </div>
              </div>
            )}
          </div>

          {/* Products & services */}
          <div>
            <SectionTitle icon={Package}>Produits & services</SectionTitle>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3" data-testid="bizanalyzer-products">
              {(profile.products_services || []).map((p, i) => (
                <div key={i} className="border border-slate-200 bg-white rounded-lg p-4">
                  <div className="font-semibold text-sm text-slate-900 mb-1">{p.name}</div>
                  <p className="text-xs text-slate-600 mb-1.5">{p.description}</p>
                  {p.target && <div className="text-[11px] text-slate-500"><span className="font-semibold">Pour :</span> {p.target}</div>}
                </div>
              ))}
            </div>
          </div>

          {/* Target segments */}
          <div>
            <SectionTitle icon={Users}>Segments cibles</SectionTitle>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3" data-testid="bizanalyzer-segments">
              {(profile.target_segments || []).map((s, i) => (
                <div key={i} className="border border-slate-200 bg-white rounded-lg p-4">
                  <div className="font-semibold text-sm text-slate-900 mb-1">{s.segment}</div>
                  <div className="text-xs text-slate-600 mb-1.5"><span className="font-semibold">Besoins :</span> {s.needs}</div>
                  {s.message && <div className="text-xs text-[#002FA7] italic">« {s.message} »</div>}
                </div>
              ))}
            </div>
          </div>

          {/* Competitors */}
          <div>
            <SectionTitle icon={Swords}>Concurrents</SectionTitle>
            <div className="space-y-3" data-testid="bizanalyzer-competitors">
              {(profile.competitors || []).map((c, i) => (
                <div key={i} className="border border-slate-200 bg-white rounded-lg p-4">
                  <div className="font-semibold text-sm text-slate-900 mb-1">
                    {c.name}
                    {c.domain && <span className="text-xs text-slate-400 font-normal ml-2">{c.domain}</span>}
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
                    <div><span className="font-semibold text-slate-700">Forces :</span> <span className="text-slate-600">{c.strengths}</span></div>
                    <div><span className="font-semibold text-slate-700">Faiblesses :</span> <span className="text-slate-600">{c.weaknesses}</span></div>
                    <div><span className="font-semibold text-green-700">Comment le dépasser :</span> <span className="text-slate-600">{c.how_to_beat}</span></div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* SWOT */}
          <div>
            <SectionTitle icon={MapPin}>Analyse SWOT</SectionTitle>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3" data-testid="bizanalyzer-swot">
              {SWOT_META.map((s) => {
                const Icon = s.icon;
                return (
                  <div key={s.key} className={`border rounded-lg p-4 ${s.cls}`}>
                    <div className={`flex items-center gap-2 font-semibold text-sm mb-2 ${s.iconCls}`}>
                      <Icon className="w-4 h-4" /> {s.label}
                    </div>
                    <ul className="space-y-1">
                      {((profile.swot || {})[s.key] || []).map((item, i) => (
                        <li key={i} className="text-xs text-slate-700 flex gap-2">
                          <span className="text-slate-400">•</span> {item}
                        </li>
                      ))}
                    </ul>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Marketing priorities */}
          <div>
            <SectionTitle icon={TrendingUp}>Priorités marketing recommandées</SectionTitle>
            <div className="space-y-3" data-testid="bizanalyzer-priorities">
              {(profile.marketing_priorities || []).map((p, i) => (
                <div key={i} className="border border-slate-200 bg-white rounded-lg p-4 flex items-start gap-3">
                  <div className="text-lg font-display font-bold text-[#002FA7] w-6 flex-shrink-0">{i + 1}</div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 flex-wrap mb-0.5">
                      <div className="font-semibold text-sm text-slate-900">{p.priority}</div>
                      <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${IMPACT_STYLE[p.impact] || IMPACT_STYLE.faible}`}>
                        Impact {p.impact}
                      </span>
                    </div>
                    <p className="text-xs text-slate-600">{p.why}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="text-[11px] text-slate-400">
            Dernière mise à jour : {doc.updated_at ? new Date(doc.updated_at).toLocaleString("fr-FR") : "—"}
            {doc.pages_analyzed?.length ? ` — ${doc.pages_analyzed.length} pages analysées` : ""}
          </div>
        </div>
      )}
    </div>
  );
}
