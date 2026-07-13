import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useSites } from "@/contexts/SiteContext";
import PageHeader from "@/components/PageHeader";
import { toast } from "sonner";
import { Zap, Play, Trash2, Loader2, Plus, TrendingDown, Bot, CalendarClock, Bell, PenLine, Search, CheckCircle2, XCircle } from "lucide-react";
import { Switch } from "@/components/ui/switch";

const TRIGGERS = {
  rank_drop: {
    label: "Chute de position Google",
    icon: TrendingDown,
    paramKey: "threshold",
    paramLabel: "positions perdues (seuil)",
    paramDefault: 5,
    describe: (p) => `SI un mot-clé suivi chute de ≥ ${p.threshold ?? 5} positions`,
    hint: "Nécessite Google Search Console connecté (snapshots quotidiens).",
  },
  ai_visibility_drop: {
    label: "Baisse du score AI Visibility",
    icon: Bot,
    paramKey: "threshold",
    paramLabel: "points perdus (seuil)",
    paramDefault: 5,
    describe: (p) => `SI le score AI Visibility baisse de ≥ ${p.threshold ?? 5} points`,
    hint: "Compare les 2 dernières analyses AI Visibility.",
  },
  no_publication: {
    label: "Aucune publication récente",
    icon: CalendarClock,
    paramKey: "days",
    paramLabel: "jours sans publication",
    paramDefault: 7,
    describe: (p) => `SI aucune publication depuis ${p.days ?? 7} jours`,
    hint: "Vérifie les publications (statut publié ou push GitHub).",
  },
};

const ACTIONS = {
  notify: { label: "Me notifier", icon: Bell, desc: "Notification in-app sur le Dashboard" },
  generate_draft: { label: "Générer un brouillon IA", icon: PenLine, desc: "Claude rédige un article ciblé (compte dans le quota)" },
  run_audit: { label: "Relancer un audit SEO", icon: Search, desc: "Nouveau diagnostic technique du site" },
};

export default function Workflows() {
  const { activeSite } = useSites();
  const [workflows, setWorkflows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [runningId, setRunningId] = useState("");
  const [form, setForm] = useState({
    name: "",
    trigger_type: "rank_drop",
    param: 5,
    actions: ["notify"],
  });

  const load = async () => {
    if (!activeSite) { setWorkflows([]); setLoading(false); return; }
    setLoading(true);
    try {
      const { data } = await api.get("/workflows", { params: { site_id: activeSite.id } });
      setWorkflows(data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [activeSite?.id]);

  const trigger = TRIGGERS[form.trigger_type];

  const toggleAction = (key) => {
    setForm((f) => ({
      ...f,
      actions: f.actions.includes(key) ? f.actions.filter((a) => a !== key) : [...f.actions, key],
    }));
  };

  const onCreate = async () => {
    if (!activeSite) return toast.error("Sélectionnez un site actif d'abord");
    if (!form.name.trim()) return toast.error("Donnez un nom au workflow");
    if (form.actions.length === 0) return toast.error("Sélectionnez au moins une action");
    setCreating(true);
    try {
      await api.post("/workflows", {
        site_id: activeSite.id,
        name: form.name.trim(),
        trigger_type: form.trigger_type,
        trigger_params: { [trigger.paramKey]: Number(form.param) || trigger.paramDefault },
        actions: form.actions,
        enabled: true,
      });
      toast.success("Workflow créé ✓ — il sera évalué automatiquement toutes les heures");
      setForm({ name: "", trigger_type: "rank_drop", param: 5, actions: ["notify"] });
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Échec de la création");
    } finally {
      setCreating(false);
    }
  };

  const onToggle = async (wf) => {
    try {
      await api.patch(`/workflows/${wf.id}`, { enabled: !wf.enabled });
      setWorkflows((ws) => ws.map((w) => (w.id === wf.id ? { ...w, enabled: !wf.enabled } : w)));
    } catch {
      toast.error("Échec de la mise à jour");
    }
  };

  const onDelete = async (wf) => {
    try {
      await api.delete(`/workflows/${wf.id}`);
      toast.success("Workflow supprimé");
      load();
    } catch {
      toast.error("Échec de la suppression");
    }
  };

  const onRun = async (wf) => {
    setRunningId(wf.id);
    try {
      const { data } = await api.post(`/workflows/${wf.id}/run`);
      if (data.fired) {
        toast.success("Déclencheur activé — actions exécutées", { description: data.reason });
      } else {
        toast.info("Condition non remplie (rien à faire)", { description: data.reason });
      }
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Échec du test");
    } finally {
      setRunningId("");
    }
  };

  return (
    <div className="p-6 md:p-8 max-w-5xl">
      <PageHeader
        overline={activeSite ? `Contexte · ${activeSite.label}` : "Automatisation"}
        title="Workflows"
        description="Définissez des règles SI → ALORS : vos agents surveillent et réagissent automatiquement, toutes les heures."
      />

      {/* Builder */}
      <div className="border border-slate-200 bg-white rounded-md p-5 mb-6" data-testid="workflow-builder">
        <div className="overline mb-4 flex items-center gap-1.5"><Plus className="w-3 h-3" /> Nouveau workflow</div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="text-xs font-medium text-slate-700 mb-1.5 block">Nom du workflow</label>
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="Ex. Surveillance des positions Genève"
              data-testid="workflow-name-input"
              className="w-full border border-slate-300 rounded-md px-3 py-2 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7]"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-slate-700 mb-1.5 block">SI (déclencheur)</label>
            <div className="flex gap-2">
              <select
                value={form.trigger_type}
                onChange={(e) => setForm({ ...form, trigger_type: e.target.value, param: TRIGGERS[e.target.value].paramDefault })}
                data-testid="workflow-trigger-select"
                className="flex-1 border border-slate-300 rounded-md px-3 py-2 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30"
              >
                {Object.entries(TRIGGERS).map(([k, t]) => (
                  <option key={k} value={k}>{t.label}</option>
                ))}
              </select>
              <input
                type="number"
                min={1}
                value={form.param}
                onChange={(e) => setForm({ ...form, param: e.target.value })}
                data-testid="workflow-param-input"
                title={trigger.paramLabel}
                className="w-20 border border-slate-300 rounded-md px-2 py-2 bg-white text-sm text-center focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30"
              />
            </div>
            <p className="text-[11px] text-slate-500 mt-1">{trigger.paramLabel} · {trigger.hint}</p>
          </div>
        </div>
        <div className="mt-4">
          <label className="text-xs font-medium text-slate-700 mb-2 block">ALORS (actions)</label>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            {Object.entries(ACTIONS).map(([k, a]) => {
              const Icon = a.icon;
              const active = form.actions.includes(k);
              return (
                <button
                  key={k}
                  type="button"
                  onClick={() => toggleAction(k)}
                  data-testid={`workflow-action-${k}`}
                  className={`text-left border rounded-md p-3 transition-colors ${active ? "border-[#002FA7] bg-[#002FA7]/5" : "border-slate-200 bg-white hover:border-slate-300"}`}
                >
                  <div className={`flex items-center gap-2 text-sm font-medium ${active ? "text-[#002FA7]" : "text-slate-800"}`}>
                    <Icon className="w-4 h-4" /> {a.label}
                    {active && <CheckCircle2 className="w-3.5 h-3.5 ml-auto" />}
                  </div>
                  <p className="text-[11px] text-slate-500 mt-1 leading-relaxed">{a.desc}</p>
                </button>
              );
            })}
          </div>
        </div>
        <div className="mt-4 flex items-center justify-between">
          <p className="text-xs text-slate-500 italic">
            {trigger.describe({ [trigger.paramKey]: Number(form.param) })} → {form.actions.map((a) => ACTIONS[a].label).join(" + ") || "…"}
          </p>
          <button
            onClick={onCreate}
            disabled={creating}
            data-testid="workflow-create-button"
            className="inline-flex items-center gap-2 bg-[#002FA7] hover:bg-[#001D6B] disabled:bg-slate-300 text-white px-4 py-2 rounded-md text-sm font-medium shadow-sm transition-colors"
          >
            {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
            Créer le workflow
          </button>
        </div>
      </div>

      {/* List */}
      {loading ? (
        <div className="text-sm text-slate-500">Chargement…</div>
      ) : workflows.length === 0 ? (
        <div className="border border-dashed border-slate-300 rounded-md p-8 text-center text-sm text-slate-500" data-testid="workflows-empty-state">
          Aucun workflow pour ce site. Créez votre première règle ci-dessus — vos agents surveilleront automatiquement.
        </div>
      ) : (
        <div className="space-y-3">
          {workflows.map((wf) => {
            const t = TRIGGERS[wf.trigger_type];
            const Icon = t?.icon || Zap;
            const lr = wf.last_result;
            return (
              <div key={wf.id} className="border border-slate-200 bg-white rounded-md p-4" data-testid={`workflow-card-${wf.id}`}>
                <div className="flex items-center gap-3">
                  <div className={`w-9 h-9 rounded-md flex items-center justify-center flex-shrink-0 ${wf.enabled ? "bg-[#002FA7]/10" : "bg-slate-100"}`}>
                    <Icon className={`w-4.5 h-4.5 w-4 h-4 ${wf.enabled ? "text-[#002FA7]" : "text-slate-400"}`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-display font-semibold text-sm text-slate-950 truncate">{wf.name}</div>
                    <div className="text-xs text-slate-500 truncate">
                      {t?.describe(wf.trigger_params || {})} → {(wf.actions || []).map((a) => ACTIONS[a]?.label).join(" + ")}
                    </div>
                  </div>
                  <button
                    onClick={() => onRun(wf)}
                    disabled={runningId === wf.id}
                    data-testid={`workflow-run-${wf.id}`}
                    title="Tester maintenant"
                    className="inline-flex items-center gap-1.5 border border-slate-300 hover:border-[#002FA7] hover:text-[#002FA7] text-slate-600 px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors"
                  >
                    {runningId === wf.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
                    Tester
                  </button>
                  <Switch
                    checked={wf.enabled}
                    onCheckedChange={() => onToggle(wf)}
                    data-testid={`workflow-toggle-${wf.id}`}
                  />
                  <button
                    onClick={() => onDelete(wf)}
                    data-testid={`workflow-delete-${wf.id}`}
                    title="Supprimer"
                    className="text-slate-400 hover:text-red-600 transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
                {lr && (
                  <div className={`mt-3 flex items-start gap-2 text-xs rounded-md px-3 py-2 ${lr.fired ? "bg-amber-50 text-amber-800" : "bg-slate-50 text-slate-600"}`}>
                    {lr.fired ? <Zap className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" /> : <CheckCircle2 className="w-3.5 h-3.5 flex-shrink-0 mt-0.5 text-slate-400" />}
                    <div>
                      <span>{lr.reason}</span>
                      {(lr.actions_results || []).map((r, i) => (
                        <div key={i} className="flex items-center gap-1 mt-0.5">
                          {r.ok ? <CheckCircle2 className="w-3 h-3 text-green-600" /> : <XCircle className="w-3 h-3 text-red-500" />}
                          <span>{r.detail}</span>
                        </div>
                      ))}
                      <div className="text-[10px] text-slate-400 mt-1">
                        Dernière évaluation : {wf.last_run_at && new Date(wf.last_run_at).toLocaleString("fr-FR")}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
