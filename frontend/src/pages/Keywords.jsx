import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useSites } from "@/contexts/SiteContext";
import PageHeader from "@/components/PageHeader";
import { toast } from "sonner";
import { Search, Star, Trash2, Loader2, MapPin, Compass, ShoppingBag, Tag, CheckSquare } from "lucide-react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Checkbox } from "@/components/ui/checkbox";

const intentMeta = {
  locale: { Icon: MapPin, color: "#002FA7", bg: "#EFF6FF", label: "Locale" },
  informationnelle: { Icon: Compass, color: "#0F766E", bg: "#ECFDF5", label: "Informationnelle" },
  transactionnelle: { Icon: ShoppingBag, color: "#9333EA", bg: "#FAF5FF", label: "Transactionnelle" },
  navigationnelle: { Icon: Tag, color: "#64748B", bg: "#F1F5F9", label: "Marque / Nav." },
};
const priorityColor = {
  high: { color: "#DC2626", bg: "#FEE2E2", label: "Élevée" },
  medium: { color: "#D97706", bg: "#FEF3C7", label: "Moyenne" },
  low: { color: "#0EA5E9", bg: "#E0F2FE", label: "Basse" },
};
const diffColor = {
  low: "text-[#16A34A]",
  medium: "text-[#D97706]",
  high: "text-[#DC2626]",
};

export default function Keywords() {
  const { activeSite } = useSites();
  const [theme, setTheme] = useState("");
  const [city, setCity] = useState("");
  const [competitors, setCompetitors] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [saved, setSaved] = useState([]);
  const [history, setHistory] = useState([]);
  // Selection state: key = `${clusterIntent}::${keyword}`
  const [selected, setSelected] = useState(new Set());
  const [selectedSaved, setSelectedSaved] = useState(new Set());

  const loadSaved = async () => {
    if (!activeSite) return;
    const { data } = await api.get("/keywords/saved", { params: { site_id: activeSite.id } });
    setSaved(data);
  };
  const loadHistory = async () => {
    if (!activeSite) return;
    const { data } = await api.get("/keywords/research", { params: { site_id: activeSite.id } });
    setHistory(data.items);
    if (data.items.length && !result) setResult(data.items[0]);
  };
  useEffect(() => {
    setResult(null);
    setSaved([]);
    setHistory([]);
    setSelected(new Set());
    setSelectedSaved(new Set());
    if (activeSite) {
      loadSaved();
      loadHistory();
    }
  }, [activeSite?.id]);

  const onResearch = async (e) => {
    e.preventDefault();
    if (!activeSite || !theme.trim()) return;
    setLoading(true);
    try {
      const { data } = await api.post("/keywords/research", {
        site_id: activeSite.id,
        theme: theme.trim(),
        city: city.trim() || null,
        competitors: competitors.split(",").map((c) => c.trim()).filter(Boolean),
      });
      setResult(data);
      toast.success("Recherche de mots-clés terminée");
      loadHistory();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Erreur recherche IA");
    } finally {
      setLoading(false);
    }
  };

  const onSave = async (kw, intent) => {
    try {
      await api.post("/keywords/saved", {
        site_id: activeSite.id,
        keyword: kw.keyword,
        intent,
        priority: kw.priority || "medium",
        notes: kw.rationale || null,
      });
      toast.success("Mot-clé ajouté à votre liste");
      loadSaved();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Échec");
    }
  };

  // --- Selection helpers ---
  const kwKey = (intent, keyword) => `${intent}::${keyword}`;

  const toggleOne = (intent, keyword) => {
    setSelected((prev) => {
      const next = new Set(prev);
      const k = kwKey(intent, keyword);
      if (next.has(k)) next.delete(k);
      else next.add(k);
      return next;
    });
  };

  const isAllInClusterSelected = (cluster) =>
    (cluster.keywords || []).length > 0 &&
    (cluster.keywords || []).every((kw) => selected.has(kwKey(cluster.intent, kw.keyword)));

  const toggleCluster = (cluster) => {
    setSelected((prev) => {
      const next = new Set(prev);
      const allSelected = isAllInClusterSelected(cluster);
      (cluster.keywords || []).forEach((kw) => {
        const k = kwKey(cluster.intent, kw.keyword);
        if (allSelected) next.delete(k);
        else next.add(k);
      });
      return next;
    });
  };

  const allKwCount = (result?.clusters || []).reduce((acc, c) => acc + (c.keywords?.length || 0), 0);
  const isAllSelected = allKwCount > 0 && selected.size === allKwCount;

  const toggleAll = () => {
    if (isAllSelected) {
      setSelected(new Set());
    } else {
      const next = new Set();
      (result?.clusters || []).forEach((c) => {
        (c.keywords || []).forEach((kw) => next.add(kwKey(c.intent, kw.keyword)));
      });
      setSelected(next);
    }
  };

  const onAddSelected = async () => {
    if (selected.size === 0) return;
    const payload = [];
    (result?.clusters || []).forEach((c) => {
      (c.keywords || []).forEach((kw) => {
        if (selected.has(kwKey(c.intent, kw.keyword))) {
          payload.push({
            site_id: activeSite.id,
            keyword: kw.keyword,
            intent: c.intent,
            priority: kw.priority || "medium",
            notes: kw.rationale || null,
          });
        }
      });
    });
    try {
      const { data } = await api.post("/keywords/saved/batch", { keywords: payload });
      toast.success(`${data.added} mot(s)-clé(s) ajouté(s)${data.skipped ? ` · ${data.skipped} déjà présent(s)` : ""}`);
      setSelected(new Set());
      loadSaved();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Échec de l'ajout en lot");
    }
  };

  // Saved list selection
  const toggleSaved = (id) => {
    setSelectedSaved((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };
  const isAllSavedSelected = saved.length > 0 && selectedSaved.size === saved.length;
  const toggleAllSaved = () => {
    if (isAllSavedSelected) setSelectedSaved(new Set());
    else setSelectedSaved(new Set(saved.map((s) => s.id)));
  };
  const onDeleteSelectedSaved = async () => {
    if (selectedSaved.size === 0) return;
    try {
      const { data } = await api.post("/keywords/saved/batch-delete", { ids: Array.from(selectedSaved) });
      toast.success(`${data.deleted} mot(s)-clé(s) supprimé(s)`);
      setSelectedSaved(new Set());
      loadSaved();
    } catch {
      toast.error("Échec");
    }
  };

  const onDelete = async (id) => {
    try {
      await api.delete(`/keywords/saved/${id}`);
      loadSaved();
    } catch {
      toast.error("Échec");
    }
  };

  if (!activeSite) {
    return (
      <div className="p-6 md:p-8 max-w-7xl">
        <PageHeader overline="Mots-clés" title="Recherche IA de mots-clés" />
        <div className="border border-dashed border-slate-300 bg-white rounded-md p-10 text-center text-sm text-slate-600">
          Sélectionnez un site pour démarrer la recherche.
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 md:p-8 max-w-7xl">
      <PageHeader
        overline={`Stratégie SEO · ${activeSite.label}`}
        title="Recherche IA de mots-clés"
        description="Détecte les mots-clés à fort potentiel pour atteindre la première page Google. Clustering par intention, longue traîne privilégiée."
      />

      <form onSubmit={onResearch} className="border border-slate-200 bg-white rounded-md p-5 mb-6 grid grid-cols-1 md:grid-cols-4 gap-3" data-testid="keywords-form">
        <div className="md:col-span-2">
          <label className="text-xs font-medium text-slate-700 mb-1.5 block">Thématique *</label>
          <input
            required
            data-testid="kw-theme-input"
            value={theme}
            onChange={(e) => setTheme(e.target.value)}
            placeholder="Ex : location meublée courte durée"
            className="w-full border border-slate-300 rounded-md px-3 py-2 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7]"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-slate-700 mb-1.5 block">Ville / zone</label>
          <input
            data-testid="kw-city-input"
            value={city}
            onChange={(e) => setCity(e.target.value)}
            placeholder="Lyon"
            className="w-full border border-slate-300 rounded-md px-3 py-2 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7]"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-slate-700 mb-1.5 block">Concurrents (séparés par virgules)</label>
          <input
            data-testid="kw-competitors-input"
            value={competitors}
            onChange={(e) => setCompetitors(e.target.value)}
            placeholder="airbnb, booking…"
            className="w-full border border-slate-300 rounded-md px-3 py-2 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7]"
          />
        </div>
        <div className="md:col-span-4 flex justify-end">
          <button
            type="submit"
            disabled={loading}
            data-testid="kw-research-button"
            className="inline-flex items-center gap-2 bg-[#002FA7] hover:bg-[#001D6B] disabled:opacity-60 text-white px-5 py-2.5 rounded-md text-sm font-medium transition-colors shadow-sm"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
            {loading ? "Analyse en cours…" : "Lancer la recherche IA"}
          </button>
        </div>
      </form>

      <Tabs defaultValue="research">
        <TabsList className="bg-transparent border-b border-slate-200 rounded-none p-0 h-auto w-full justify-start gap-6 mb-5">
          <TabsTrigger value="research" className="rounded-none border-b-2 border-transparent data-[state=active]:border-[#002FA7] data-[state=active]:bg-transparent px-0 py-3 text-sm" data-testid="tab-research">
            Résultats IA
          </TabsTrigger>
          <TabsTrigger value="saved" className="rounded-none border-b-2 border-transparent data-[state=active]:border-[#002FA7] data-[state=active]:bg-transparent px-0 py-3 text-sm" data-testid="tab-saved">
            Liste cible ({saved.length})
          </TabsTrigger>
          <TabsTrigger value="history" className="rounded-none border-b-2 border-transparent data-[state=active]:border-[#002FA7] data-[state=active]:bg-transparent px-0 py-3 text-sm" data-testid="tab-history">
            Historique ({history.length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="research" className="mt-0">
          {!result ? (
            <div className="border border-dashed border-slate-300 bg-white rounded-md p-10 text-center text-sm text-slate-600" data-testid="kw-empty">
              Aucune recherche pour le moment. Lancez votre première analyse.
            </div>
          ) : (
            <div className="space-y-4">
              {/* Sticky action bar */}
              <div className="sticky top-2 z-10 border border-slate-200 bg-white rounded-md p-3 flex items-center justify-between shadow-sm" data-testid="kw-bulk-actions">
                <label className="flex items-center gap-2.5 cursor-pointer">
                  <Checkbox
                    checked={isAllSelected}
                    onCheckedChange={toggleAll}
                    data-testid="kw-select-all-global"
                  />
                  <span className="text-sm font-medium text-slate-900">
                    Tout sélectionner <span className="text-slate-500 font-normal">({allKwCount})</span>
                  </span>
                  {selected.size > 0 && (
                    <span className="text-xs text-[#002FA7] ml-2">· {selected.size} sélectionné(s)</span>
                  )}
                </label>
                <button
                  onClick={onAddSelected}
                  disabled={selected.size === 0}
                  data-testid="kw-add-selected"
                  className="inline-flex items-center gap-1.5 bg-[#002FA7] hover:bg-[#001D6B] disabled:opacity-40 disabled:cursor-not-allowed text-white px-3.5 py-1.5 rounded-md text-sm font-medium transition-colors shadow-sm"
                >
                  <Star className="w-3.5 h-3.5" />
                  Ajouter {selected.size > 0 ? `${selected.size} mot(s)-clé(s)` : "la sélection"}
                </button>
              </div>

              {result.summary && (
                <div className="border-l-4 border-[#002FA7] bg-blue-50/50 rounded-r-md p-4 text-sm text-slate-800">
                  <div className="overline mb-2 text-[#002FA7]">Synthèse stratégique</div>
                  {result.summary}
                </div>
              )}
              {result.clusters?.map((c) => {
                const meta = intentMeta[c.intent] || intentMeta.informationnelle;
                const Ico = meta.Icon;
                const clusterAllSelected = isAllInClusterSelected(c);
                return (
                  <div key={c.intent} className="border border-slate-200 bg-white rounded-md overflow-hidden">
                    <div className="px-4 py-3 border-b border-slate-200 flex items-center justify-between" style={{ background: meta.bg }}>
                      <label className="flex items-center gap-2.5 cursor-pointer">
                        <Checkbox
                          checked={clusterAllSelected}
                          onCheckedChange={() => toggleCluster(c)}
                          data-testid={`kw-select-cluster-${c.intent}`}
                        />
                        <Ico className="w-4 h-4" style={{ color: meta.color }} />
                        <span className="font-display font-semibold text-slate-900">{c.intent_label}</span>
                      </label>
                      <span className="text-xs text-slate-600">{c.keywords?.length || 0} mots-clés</span>
                    </div>
                    <table className="w-full text-sm">
                      <thead className="bg-slate-50 border-b border-slate-100">
                        <tr>
                          <th className="w-10 px-3 py-2"></th>
                          <th className="text-left px-4 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">Mot-clé</th>
                          <th className="text-left px-4 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">Difficulté</th>
                          <th className="text-left px-4 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">Volume</th>
                          <th className="text-left px-4 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">Priorité</th>
                          <th className="text-left px-4 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">Pourquoi</th>
                          <th className="text-right px-4 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider"></th>
                        </tr>
                      </thead>
                      <tbody>
                        {(c.keywords || []).map((kw, i) => {
                          const pri = priorityColor[kw.priority] || priorityColor.medium;
                          const isChecked = selected.has(kwKey(c.intent, kw.keyword));
                          return (
                            <tr
                              key={i}
                              className={`border-b border-slate-100 ${isChecked ? "bg-blue-50/40" : "hover:bg-slate-50"}`}
                              data-testid={`kw-row-${c.intent}-${i}`}
                            >
                              <td className="px-3 py-2.5 align-middle">
                                <Checkbox
                                  checked={isChecked}
                                  onCheckedChange={() => toggleOne(c.intent, kw.keyword)}
                                  data-testid={`kw-check-${c.intent}-${i}`}
                                />
                              </td>
                              <td className="px-4 py-2.5 font-medium text-slate-900">{kw.keyword}</td>
                              <td className={`px-4 py-2.5 font-mono text-xs ${diffColor[kw.difficulty] || ""}`}>{kw.difficulty}</td>
                              <td className="px-4 py-2.5 font-mono text-xs text-slate-700">{kw.volume_estimate}</td>
                              <td className="px-4 py-2.5">
                                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium" style={{ background: pri.bg, color: pri.color }}>
                                  {pri.label}
                                </span>
                              </td>
                              <td className="px-4 py-2.5 text-xs text-slate-600 max-w-md">{kw.rationale}</td>
                              <td className="px-4 py-2.5 text-right">
                                <button
                                  onClick={() => onSave(kw, c.intent)}
                                  data-testid={`kw-save-${c.intent}-${i}`}
                                  className="inline-flex items-center gap-1 text-xs font-medium text-[#002FA7] hover:underline"
                                >
                                  <Star className="w-3.5 h-3.5" /> Ajouter
                                </button>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                );
              })}
            </div>
          )}
        </TabsContent>

        <TabsContent value="saved" className="mt-0">
          {saved.length === 0 ? (
            <div className="border border-dashed border-slate-300 bg-white rounded-md p-10 text-center text-sm text-slate-600">
              Aucun mot-clé enregistré. Ajoutez vos cibles depuis l&apos;onglet « Résultats IA ».
            </div>
          ) : (
            <>
              <div className="border border-slate-200 bg-white rounded-md p-3 mb-3 flex items-center justify-between" data-testid="kw-saved-bulk-actions">
                <label className="flex items-center gap-2.5 cursor-pointer">
                  <Checkbox
                    checked={isAllSavedSelected}
                    onCheckedChange={toggleAllSaved}
                    data-testid="kw-saved-select-all"
                  />
                  <span className="text-sm font-medium text-slate-900">
                    Tout sélectionner <span className="text-slate-500 font-normal">({saved.length})</span>
                  </span>
                  {selectedSaved.size > 0 && (
                    <span className="text-xs text-[#002FA7] ml-2">· {selectedSaved.size} sélectionné(s)</span>
                  )}
                </label>
                <button
                  onClick={onDeleteSelectedSaved}
                  disabled={selectedSaved.size === 0}
                  data-testid="kw-saved-delete-selected"
                  className="inline-flex items-center gap-1.5 bg-red-600 hover:bg-red-700 disabled:opacity-40 disabled:cursor-not-allowed text-white px-3.5 py-1.5 rounded-md text-sm font-medium transition-colors shadow-sm"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  Supprimer {selectedSaved.size > 0 ? `(${selectedSaved.size})` : "la sélection"}
                </button>
              </div>
              <div className="border border-slate-200 bg-white rounded-md overflow-hidden" data-testid="kw-saved-list">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 border-b border-slate-200">
                    <tr>
                      <th className="w-10 px-3 py-2.5"></th>
                      <th className="text-left px-4 py-2.5 text-xs font-semibold text-slate-500 uppercase tracking-wider">Mot-clé</th>
                      <th className="text-left px-4 py-2.5 text-xs font-semibold text-slate-500 uppercase tracking-wider">Intention</th>
                      <th className="text-left px-4 py-2.5 text-xs font-semibold text-slate-500 uppercase tracking-wider">Priorité</th>
                      <th className="text-left px-4 py-2.5 text-xs font-semibold text-slate-500 uppercase tracking-wider">Notes</th>
                      <th className="text-right px-4 py-2.5 text-xs font-semibold text-slate-500 uppercase tracking-wider"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {saved.map((s) => {
                      const meta = intentMeta[s.intent] || intentMeta.informationnelle;
                      const pri = priorityColor[s.priority] || priorityColor.medium;
                      const isChecked = selectedSaved.has(s.id);
                      return (
                        <tr key={s.id} className={`border-b border-slate-100 ${isChecked ? "bg-blue-50/40" : "hover:bg-slate-50"}`}>
                          <td className="px-3 py-2.5 align-middle">
                            <Checkbox
                              checked={isChecked}
                              onCheckedChange={() => toggleSaved(s.id)}
                              data-testid={`kw-saved-check-${s.id}`}
                            />
                          </td>
                          <td className="px-4 py-2.5 font-medium text-slate-900">{s.keyword}</td>
                          <td className="px-4 py-2.5">
                            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs" style={{ background: meta.bg, color: meta.color }}>
                              {meta.label}
                            </span>
                          </td>
                          <td className="px-4 py-2.5">
                            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium" style={{ background: pri.bg, color: pri.color }}>
                              {pri.label}
                            </span>
                          </td>
                          <td className="px-4 py-2.5 text-xs text-slate-600 max-w-md">{s.notes || "—"}</td>
                          <td className="px-4 py-2.5 text-right">
                            <button
                              onClick={() => onDelete(s.id)}
                              className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded"
                              data-testid={`kw-saved-delete-${s.id}`}
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </TabsContent>

        <TabsContent value="history" className="mt-0">
          <div className="border border-slate-200 bg-white rounded-md">
            {history.length === 0 ? (
              <div className="p-6 text-center text-sm text-slate-500">Aucune recherche enregistrée.</div>
            ) : (
              <ul className="divide-y divide-slate-100">
                {history.map((h) => (
                  <li
                    key={h.id}
                    onClick={() => setResult(h)}
                    className="p-4 hover:bg-slate-50 cursor-pointer flex items-center justify-between"
                  >
                    <div>
                      <div className="text-sm font-medium text-slate-900">{h.theme}</div>
                      <div className="text-xs text-slate-500 mt-0.5">{h.city || "France"} · {new Date(h.created_at).toLocaleString("fr-FR")}</div>
                    </div>
                    <div className="text-xs text-slate-600">{h.clusters?.reduce((acc, c) => acc + (c.keywords?.length || 0), 0)} mots-clés</div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
