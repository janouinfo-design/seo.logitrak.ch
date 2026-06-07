import { useEffect, useState, useCallback } from "react";
import { useSites } from "@/contexts/SiteContext";
import { api } from "@/lib/api";
import PageHeader from "@/components/PageHeader";
import { toast } from "sonner";
import { Sparkles, Calendar, Loader2, CheckCircle2, AlertCircle, Trash2, Github, Linkedin, Rocket, Clock } from "lucide-react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";

const EXAMPLE_BATCH = `Location voitures Genève | Genève | location voiture genève, rent a car genève
Location voitures Lausanne | Lausanne | location voiture lausanne, rent a car lausanne
Location voitures Zurich | Zurich | location voiture zurich, rent a car zurich`;

function parseBatchInput(text) {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith("#"))
    .map((line) => {
      const parts = line.split("|").map((p) => p.trim());
      const [topic, city, keywords, extra] = parts;
      return {
        topic: topic || "",
        city: city || null,
        keywords: keywords ? keywords.split(",").map((k) => k.trim()).filter(Boolean) : [],
        extra_instructions: extra || null,
      };
    })
    .filter((it) => it.topic);
}

export default function Automation() {
  const { activeSite } = useSites();
  return (
    <div className="p-6 md:p-8 max-w-7xl">
      <PageHeader
        overline="Automatisation"
        title="Génération en lot & Calendrier éditorial"
        description="Générez 10 articles d'un coup ou programmez la publication automatique sur des semaines/mois."
      />
      {!activeSite ? (
        <div className="border border-dashed border-slate-300 bg-white rounded-md p-10 text-center text-sm text-slate-600">
          Sélectionnez un site dans le menu de gauche pour démarrer.
        </div>
      ) : (
        <Tabs defaultValue="batch" className="w-full">
          <TabsList className="mb-6">
            <TabsTrigger value="batch" data-testid="tab-batch"><Rocket className="w-4 h-4 mr-1.5" />Génération en lot</TabsTrigger>
            <TabsTrigger value="calendar" data-testid="tab-calendar"><Calendar className="w-4 h-4 mr-1.5" />Calendrier éditorial</TabsTrigger>
          </TabsList>
          <TabsContent value="batch"><BatchPanel site={activeSite} /></TabsContent>
          <TabsContent value="calendar"><CalendarPanel site={activeSite} /></TabsContent>
        </Tabs>
      )}
    </div>
  );
}

function BatchPanel({ site }) {
  const [text, setText] = useState(EXAMPLE_BATCH);
  const [autoGh, setAutoGh] = useState(!!site.has_github_token);
  const [autoLi, setAutoLi] = useState(false);
  const [batchId, setBatchId] = useState(null);
  const [job, setJob] = useState(null);
  const [running, setRunning] = useState(false);
  const items = parseBatchInput(text);

  const launch = async () => {
    if (items.length === 0) return toast.error("Aucun article valide détecté");
    if (items.length > 50) return toast.error("Maximum 50 articles par lot");
    setRunning(true);
    try {
      const { data } = await api.post("/content/batch-generate", {
        site_id: site.id,
        items,
        auto_publish_github: autoGh,
        auto_publish_linkedin: autoLi,
      });
      setBatchId(data.batch_id);
      toast.success(`Lot lancé · ${data.total} articles en cours…`);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Échec");
    } finally {
      setRunning(false);
    }
  };

  // Poll job status
  useEffect(() => {
    if (!batchId) return;
    let cancelled = false;
    const tick = async () => {
      try {
        const { data } = await api.get(`/content/batch-jobs/${batchId}`);
        if (!cancelled) {
          setJob(data);
          if (data.status === "completed") return;
          setTimeout(tick, 4000);
        }
      } catch { /* ignore */ }
    };
    tick();
    return () => { cancelled = true; };
  }, [batchId]);

  return (
    <div className="grid lg:grid-cols-2 gap-6">
      <div className="space-y-4">
        <div>
          <label className="text-xs font-medium text-slate-700 mb-1.5 block">Articles à générer (format : <code className="text-[10px] bg-slate-100 px-1 rounded">titre | ville | mots-clés séparés par virgules | instructions</code>)</label>
          <textarea
            data-testid="batch-input"
            rows={14}
            value={text}
            onChange={(e) => setText(e.target.value)}
            className="w-full border border-slate-300 rounded-md px-3 py-2 bg-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7] resize-none"
          />
          <p className="text-xs text-slate-500 mt-1">{items.length} article(s) détecté(s) · 1 ligne = 1 article · 50 max</p>
        </div>
        <label className={`flex items-start gap-3 p-3 border rounded-md cursor-pointer ${autoGh ? "border-[#002FA7] bg-[#002FA7]/5" : "border-slate-200"}`}>
          <input type="checkbox" checked={autoGh} onChange={(e) => setAutoGh(e.target.checked)} disabled={!site.has_github_token} className="mt-0.5 w-4 h-4 accent-[#002FA7]" data-testid="batch-auto-gh" />
          <div className="flex-1">
            <div className="text-sm font-medium flex items-center gap-1.5"><Github className="w-4 h-4" /> Publier auto sur GitHub</div>
            <div className="text-xs text-slate-500">{site.has_github_token ? `Push vers ${site.github_owner}/${site.github_repo}` : "GitHub non configuré sur ce site"}</div>
          </div>
        </label>
        <label className={`flex items-start gap-3 p-3 border rounded-md cursor-pointer ${autoLi ? "border-[#0A66C2] bg-[#0A66C2]/5" : "border-slate-200"}`}>
          <input type="checkbox" checked={autoLi} onChange={(e) => setAutoLi(e.target.checked)} className="mt-0.5 w-4 h-4 accent-[#0A66C2]" data-testid="batch-auto-li" />
          <div className="flex-1">
            <div className="text-sm font-medium flex items-center gap-1.5"><Linkedin className="w-4 h-4 text-[#0A66C2]" /> Publier auto sur LinkedIn</div>
            <div className="text-xs text-slate-500">Claude génère un post pro pour chaque article. Nécessite LinkedIn connecté.</div>
          </div>
        </label>
        <button
          onClick={launch}
          disabled={running || items.length === 0}
          data-testid="batch-launch-button"
          className="w-full inline-flex items-center justify-center gap-2 bg-[#002FA7] hover:bg-[#001D6B] disabled:opacity-60 text-white px-4 py-3 rounded-md text-sm font-medium shadow-sm"
        >
          {running ? <Loader2 className="w-4 h-4 animate-spin" /> : <Rocket className="w-4 h-4" />}
          Générer {items.length} article{items.length > 1 ? "s" : ""}
        </button>
      </div>
      <div>
        {job ? <BatchProgress job={job} /> : <div className="border border-dashed border-slate-300 rounded-md p-8 text-center text-sm text-slate-500">La progression s'affichera ici</div>}
      </div>
    </div>
  );
}

function BatchProgress({ job }) {
  const pct = job.total > 0 ? Math.round(((job.completed + job.failed) / job.total) * 100) : 0;
  return (
    <div className="border border-slate-200 bg-white rounded-md p-5" data-testid="batch-progress">
      <div className="flex items-center justify-between mb-3">
        <div className="overline">Lot en cours</div>
        <div className="text-xs text-slate-500">{job.completed + job.failed} / {job.total} ({pct}%)</div>
      </div>
      <div className="w-full bg-slate-100 rounded-full h-2 mb-4 overflow-hidden">
        <div className="bg-[#002FA7] h-full transition-all" style={{ width: `${pct}%` }} />
      </div>
      <div className="space-y-1 max-h-96 overflow-auto">
        {job.items.map((it) => (
          <div key={it.index} className="flex items-center gap-2 text-xs py-1.5 border-b border-slate-50">
            {it.status === "completed" && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 flex-shrink-0" />}
            {it.status === "failed" && <AlertCircle className="w-3.5 h-3.5 text-red-600 flex-shrink-0" />}
            {it.status === "pending" && <Clock className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />}
            <span className="flex-1 truncate text-slate-700">{it.topic} {it.city && <span className="text-slate-400">· {it.city}</span>}</span>
            {it.draft_id && <a href={`/drafts/${it.draft_id}`} target="_blank" rel="noreferrer" className="text-[#002FA7] hover:underline">voir</a>}
            {it.error && <span className="text-red-600 truncate max-w-[200px]" title={it.error}>{it.error}</span>}
          </div>
        ))}
      </div>
      {job.status === "completed" && <div className="mt-3 text-sm text-emerald-700 font-medium">✓ Lot terminé · {job.completed} générés, {job.failed} échoués</div>}
    </div>
  );
}

function CalendarPanel({ site }) {
  const [items, setItems] = useState([]);
  const [bulkText, setBulkText] = useState(EXAMPLE_BATCH);
  const [intervalDays, setIntervalDays] = useState(2);
  const [startAt, setStartAt] = useState("");
  const [autoGh, setAutoGh] = useState(!!site.has_github_token);
  const [autoLi, setAutoLi] = useState(false);
  const [scheduling, setScheduling] = useState(false);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get(`/calendar?site_id=${site.id}`);
      setItems(data);
    } catch { /* ignore */ }
  }, [site.id]);

  useEffect(() => { load(); }, [load]);

  const bulkItems = parseBatchInput(bulkText);

  const schedule = async () => {
    if (bulkItems.length === 0) return toast.error("Aucun article valide");
    setScheduling(true);
    try {
      const { data } = await api.post("/calendar/bulk", {
        site_id: site.id,
        items: bulkItems,
        interval_days: intervalDays,
        start_at: startAt || null,
        auto_publish_github: autoGh,
        auto_publish_linkedin: autoLi,
      });
      toast.success(`${data.created} articles programmés`);
      setBulkText("");
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Échec");
    } finally {
      setScheduling(false);
    }
  };

  const remove = async (id) => {
    if (!confirm("Supprimer cet élément du calendrier ?")) return;
    await api.delete(`/calendar/${id}`);
    load();
  };

  const fmt = (iso) => {
    try { return new Date(iso).toLocaleString("fr-FR", { dateStyle: "medium", timeStyle: "short" }); }
    catch { return iso; }
  };

  return (
    <div className="space-y-6">
      <div className="border border-slate-200 bg-white rounded-md p-5">
        <div className="overline mb-3">Programmer une vague d&apos;articles</div>
        <div className="grid lg:grid-cols-2 gap-4">
          <div>
            <label className="text-xs font-medium text-slate-700 mb-1.5 block">Articles (1 ligne = 1 article)</label>
            <textarea
              data-testid="calendar-bulk-input"
              rows={10}
              value={bulkText}
              onChange={(e) => setBulkText(e.target.value)}
              className="w-full border border-slate-300 rounded-md px-3 py-2 bg-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7] resize-none"
            />
            <p className="text-xs text-slate-500 mt-1">{bulkItems.length} article(s) · 100 max</p>
          </div>
          <div className="space-y-3">
            <div>
              <label className="text-xs font-medium text-slate-700 mb-1.5 block">Date/heure de début</label>
              <input
                type="datetime-local"
                value={startAt}
                onChange={(e) => setStartAt(e.target.value)}
                data-testid="calendar-start-input"
                className="w-full border border-slate-300 rounded-md px-3 py-2 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7]"
              />
              <p className="text-xs text-slate-500 mt-1">Vide = demain 10:00 UTC</p>
            </div>
            <div>
              <label className="text-xs font-medium text-slate-700 mb-1.5 block">Intervalle entre publications (jours)</label>
              <input
                type="number"
                min="1"
                max="30"
                value={intervalDays}
                onChange={(e) => setIntervalDays(parseInt(e.target.value) || 1)}
                data-testid="calendar-interval-input"
                className="w-full border border-slate-300 rounded-md px-3 py-2 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7]"
              />
              <p className="text-xs text-slate-500 mt-1">{bulkItems.length} articles × {intervalDays} jours = {bulkItems.length * intervalDays} jours de contenu</p>
            </div>
            <label className={`flex items-center gap-2 p-2 border rounded-md cursor-pointer ${autoGh ? "border-[#002FA7] bg-[#002FA7]/5" : "border-slate-200"}`}>
              <input type="checkbox" checked={autoGh} onChange={(e) => setAutoGh(e.target.checked)} disabled={!site.has_github_token} className="w-4 h-4 accent-[#002FA7]" data-testid="calendar-auto-gh" />
              <Github className="w-4 h-4" /><span className="text-sm">Auto-publish GitHub</span>
            </label>
            <label className={`flex items-center gap-2 p-2 border rounded-md cursor-pointer ${autoLi ? "border-[#0A66C2] bg-[#0A66C2]/5" : "border-slate-200"}`}>
              <input type="checkbox" checked={autoLi} onChange={(e) => setAutoLi(e.target.checked)} className="w-4 h-4 accent-[#0A66C2]" data-testid="calendar-auto-li" />
              <Linkedin className="w-4 h-4 text-[#0A66C2]" /><span className="text-sm">Auto-publish LinkedIn</span>
            </label>
            <button
              onClick={schedule}
              disabled={scheduling || bulkItems.length === 0}
              data-testid="calendar-schedule-button"
              className="w-full inline-flex items-center justify-center gap-2 bg-[#002FA7] hover:bg-[#001D6B] disabled:opacity-60 text-white px-4 py-2.5 rounded-md text-sm font-medium"
            >
              {scheduling ? <Loader2 className="w-4 h-4 animate-spin" /> : <Calendar className="w-4 h-4" />}
              Programmer
            </button>
          </div>
        </div>
      </div>
      <div className="border border-slate-200 bg-white rounded-md overflow-hidden">
        <div className="px-5 py-3 border-b border-slate-200 bg-slate-50">
          <div className="overline">Articles programmés ({items.length})</div>
          <div className="text-xs text-slate-500 mt-0.5">Le scheduler vérifie toutes les 15 min et publie ce qui est dû.</div>
        </div>
        {items.length === 0 ? (
          <div className="p-8 text-center text-sm text-slate-500">Aucun article programmé pour ce site.</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="border-b border-slate-100">
              <tr>
                <th className="text-left px-4 py-2 text-xs font-semibold text-slate-500 uppercase">Sujet</th>
                <th className="text-left px-4 py-2 text-xs font-semibold text-slate-500 uppercase">Ville</th>
                <th className="text-left px-4 py-2 text-xs font-semibold text-slate-500 uppercase">Prévu le</th>
                <th className="text-left px-4 py-2 text-xs font-semibold text-slate-500 uppercase">Status</th>
                <th className="text-right px-4 py-2 text-xs font-semibold text-slate-500 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((it) => (
                <tr key={it.id} className="border-b border-slate-100" data-testid={`calendar-item-${it.id}`}>
                  <td className="px-4 py-2 text-slate-900">{it.topic}</td>
                  <td className="px-4 py-2 text-slate-700">{it.city || "—"}</td>
                  <td className="px-4 py-2 text-slate-600 text-xs font-mono">{fmt(it.scheduled_at)}</td>
                  <td className="px-4 py-2">
                    {it.status === "completed" && <span className="text-emerald-700">✓ publié</span>}
                    {it.status === "failed" && <span className="text-red-700" title={it.error}>✗ échec</span>}
                    {it.status === "processing" && <span className="text-amber-700">⏳ en cours</span>}
                    {it.status === "scheduled" && <span className="text-slate-500">prévu</span>}
                  </td>
                  <td className="px-4 py-2 text-right">
                    {it.draft_id && <a href={`/drafts/${it.draft_id}`} className="text-[#002FA7] hover:underline mr-3 text-xs">voir</a>}
                    {it.status === "scheduled" && (
                      <button onClick={() => remove(it.id)} className="text-slate-400 hover:text-red-600" data-testid={`calendar-delete-${it.id}`}>
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
