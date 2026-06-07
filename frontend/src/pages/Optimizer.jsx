import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useSites } from "@/contexts/SiteContext";
import PageHeader from "@/components/PageHeader";
import { toast } from "sonner";
import { Wand2, ArrowRight, CheckCircle2, Loader2, FileEdit, Sparkles } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";

export default function Optimizer() {
  const { activeSite } = useSites();
  const navigate = useNavigate();
  const [pages, setPages] = useState([]);
  const [pageId, setPageId] = useState("");
  const [focus, setFocus] = useState("");
  const [city, setCity] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);

  const loadPages = async () => {
    if (!activeSite) return;
    const { data } = await api.get(`/sites/${activeSite.id}/pages`);
    setPages(data.pages);
    if (data.pages.length) setPageId((p) => p || data.pages[0].id);
  };
  const loadHistory = async () => {
    if (!activeSite) return;
    const { data } = await api.get(`/pages/optimizations`, { params: { site_id: activeSite.id } });
    setHistory(data);
  };
  useEffect(() => {
    setResult(null);
    setPages([]);
    setPageId("");
    setHistory([]);
    if (activeSite) {
      loadPages();
      loadHistory();
    }
  }, [activeSite?.id]);

  const onOptimize = async (e) => {
    e.preventDefault();
    if (!activeSite || !pageId) return;
    setLoading(true);
    try {
      const { data } = await api.post("/pages/optimize", {
        site_id: activeSite.id,
        page_id: pageId,
        focus_keyword: focus.trim() || null,
        city: city.trim() || null,
      });
      setResult(data);
      toast.success("Optimisation générée");
      loadHistory();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Erreur optimisation");
    } finally {
      setLoading(false);
    }
  };

  const onApply = async () => {
    if (!result) return;
    try {
      const { data } = await api.post(`/pages/optimizations/${result.id}/apply`);
      setResult(data);
      toast.success("Brouillon créé · prêt à publier");
      if (data.draft_id) navigate(`/drafts/${data.draft_id}`);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Échec");
    }
  };

  if (!activeSite) {
    return (
      <div className="p-6 md:p-8 max-w-7xl">
        <PageHeader overline="Optimiseur" title="Optimiseur de pages Wix" />
        <div className="border border-dashed border-slate-300 bg-white rounded-md p-10 text-center text-sm text-slate-600">
          Sélectionnez un site pour démarrer.
        </div>
      </div>
    );
  }

  const selectedPage = pages.find((p) => p.id === pageId);

  return (
    <div className="p-6 md:p-8 max-w-7xl">
      <PageHeader
        overline={`Optimiseur · ${activeSite.label}`}
        title="Optimiseur de pages Wix"
        description="Sélectionnez une page existante, fournissez un mot-clé focus, et obtenez une version optimisée (titre, méta, H1, plan, FAQ) prête à publier."
      />

      <form onSubmit={onOptimize} className="border border-slate-200 bg-white rounded-md p-5 mb-6 grid grid-cols-1 md:grid-cols-4 gap-3" data-testid="optimizer-form">
        <div className="md:col-span-2">
          <label className="text-xs font-medium text-slate-700 mb-1.5 block">Page à optimiser *</label>
          <Select value={pageId} onValueChange={setPageId}>
            <SelectTrigger data-testid="opt-page-select"><SelectValue placeholder="Choisissez une page…" /></SelectTrigger>
            <SelectContent>
              {pages.map((p) => (
                <SelectItem key={p.id} value={p.id}>{p.title}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="text-xs font-medium text-slate-700 mb-1.5 block">Mot-clé focus</label>
          <input
            data-testid="opt-focus-input"
            value={focus}
            onChange={(e) => setFocus(e.target.value)}
            placeholder="Ex : location meublée Lyon"
            className="w-full border border-slate-300 rounded-md px-3 py-2 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7]"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-slate-700 mb-1.5 block">Ville / zone</label>
          <input
            data-testid="opt-city-input"
            value={city}
            onChange={(e) => setCity(e.target.value)}
            placeholder="Lyon, Paris…"
            className="w-full border border-slate-300 rounded-md px-3 py-2 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7]"
          />
        </div>
        <div className="md:col-span-4 flex justify-end">
          <button
            type="submit"
            disabled={loading || !pageId}
            data-testid="opt-submit-button"
            className="inline-flex items-center gap-2 bg-[#002FA7] hover:bg-[#001D6B] disabled:opacity-60 text-white px-5 py-2.5 rounded-md text-sm font-medium transition-colors shadow-sm"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Wand2 className="w-4 h-4" />}
            {loading ? "Analyse en cours…" : "Optimiser cette page"}
          </button>
        </div>
      </form>

      {selectedPage && !result && (
        <div className="border border-slate-200 bg-white rounded-md p-5 mb-6" data-testid="opt-page-preview">
          <div className="overline mb-3">Page sélectionnée — état actuel</div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <div>
              <div className="text-xs text-slate-500 mb-1">Titre page</div>
              <div className="text-slate-900">{selectedPage.title}</div>
            </div>
            <div>
              <div className="text-xs text-slate-500 mb-1">URL</div>
              <div className="text-slate-900 font-mono text-xs truncate">{selectedPage.url}</div>
            </div>
            <div>
              <div className="text-xs text-slate-500 mb-1">Meta title</div>
              <div className="text-slate-900">{selectedPage.meta_title || <span className="text-red-600">— Manquant</span>}</div>
            </div>
            <div>
              <div className="text-xs text-slate-500 mb-1">Meta description</div>
              <div className="text-slate-900">{selectedPage.meta_description || <span className="text-red-600">— Manquante</span>}</div>
            </div>
          </div>
        </div>
      )}

      {result && (
        <Tabs defaultValue="compare">
          <TabsList className="bg-transparent border-b border-slate-200 rounded-none p-0 h-auto w-full justify-start gap-6 mb-5">
            <TabsTrigger value="compare" className="rounded-none border-b-2 border-transparent data-[state=active]:border-[#002FA7] data-[state=active]:bg-transparent px-0 py-3 text-sm" data-testid="opt-tab-compare">
              Comparaison avant / après
            </TabsTrigger>
            <TabsTrigger value="content" className="rounded-none border-b-2 border-transparent data-[state=active]:border-[#002FA7] data-[state=active]:bg-transparent px-0 py-3 text-sm" data-testid="opt-tab-content">
              Plan & FAQ
            </TabsTrigger>
            <TabsTrigger value="improvements" className="rounded-none border-b-2 border-transparent data-[state=active]:border-[#002FA7] data-[state=active]:bg-transparent px-0 py-3 text-sm" data-testid="opt-tab-improvements">
              Améliorations ({result.improvements?.length || 0})
            </TabsTrigger>
          </TabsList>

          <TabsContent value="compare" className="mt-0 space-y-4">
            {result.diff_summary && (
              <div className="border-l-4 border-[#16A34A] bg-green-50/50 rounded-r-md p-4 text-sm text-slate-800" data-testid="opt-diff-summary">
                <div className="overline mb-1 text-[#16A34A]">Gain SEO attendu</div>
                {result.diff_summary}
              </div>
            )}

            {[
              { k: "title", label: "Titre H1" },
              { k: "meta_title", label: "Meta title" },
              { k: "meta_description", label: "Meta description" },
            ].map((row) => (
              <div key={row.k} className="border border-slate-200 bg-white rounded-md overflow-hidden">
                <div className="px-4 py-2.5 border-b border-slate-200 bg-slate-50">
                  <div className="overline">{row.label}</div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-slate-100">
                  <div className="p-4">
                    <div className="text-[10px] font-semibold uppercase tracking-wider text-red-700 mb-1.5">AVANT</div>
                    <div className="text-sm text-slate-700 line-through decoration-red-300">
                      {result.current?.[row.k === "title" ? "title" : row.k] || <em className="not-italic text-slate-400">Absent</em>}
                    </div>
                  </div>
                  <div className="p-4 bg-green-50/30">
                    <div className="text-[10px] font-semibold uppercase tracking-wider text-green-700 mb-1.5">APRÈS</div>
                    <div className="text-sm text-slate-900 font-medium">
                      {result.suggested?.[row.k === "title" ? "h1" : row.k] || <em className="not-italic text-slate-400">—</em>}
                    </div>
                  </div>
                </div>
              </div>
            ))}

            <div className="border border-slate-200 bg-white rounded-md overflow-hidden">
              <div className="px-4 py-2.5 border-b border-slate-200 bg-slate-50">
                <div className="overline">Plan H2</div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-slate-100">
                <div className="p-4">
                  <div className="text-[10px] font-semibold uppercase tracking-wider text-red-700 mb-1.5">AVANT ({result.current?.h2?.length || 0})</div>
                  <ul className="text-sm text-slate-700 space-y-1">
                    {(result.current?.h2 || []).length === 0 ? (
                      <li className="text-slate-400 italic">Aucun H2</li>
                    ) : (
                      result.current.h2.map((h, i) => <li key={i}>• {h}</li>)
                    )}
                  </ul>
                </div>
                <div className="p-4 bg-green-50/30">
                  <div className="text-[10px] font-semibold uppercase tracking-wider text-green-700 mb-1.5">
                    APRÈS ({result.suggested?.h2_plan?.length || 0})
                  </div>
                  <ul className="text-sm text-slate-900 space-y-1">
                    {(result.suggested?.h2_plan || []).map((h, i) => <li key={i}>• {h}</li>)}
                  </ul>
                </div>
              </div>
            </div>

            <div className="flex justify-end mt-4 gap-2">
              <button
                onClick={onApply}
                disabled={result.applied}
                data-testid="opt-apply-button"
                className="inline-flex items-center gap-2 bg-[#002FA7] hover:bg-[#001D6B] disabled:opacity-60 text-white px-5 py-2.5 rounded-md text-sm font-medium transition-colors shadow-sm"
              >
                {result.applied ? <CheckCircle2 className="w-4 h-4" /> : <FileEdit className="w-4 h-4" />}
                {result.applied ? "Brouillon déjà créé" : "Créer un brouillon prêt à publier"}
                {!result.applied && <ArrowRight className="w-4 h-4" />}
              </button>
            </div>
          </TabsContent>

          <TabsContent value="content" className="mt-0 space-y-4">
            {result.suggested?.intro_short_answer && (
              <div className="border border-slate-200 bg-white rounded-md p-5">
                <div className="overline mb-2">Réponse courte (intro · optimisée AI Overviews)</div>
                <p className="text-sm text-slate-800 leading-relaxed">{result.suggested.intro_short_answer}</p>
              </div>
            )}
            {result.suggested?.content_outline && (
              <div className="border border-slate-200 bg-white rounded-md p-5">
                <div className="overline mb-3">Plan de contenu suggéré</div>
                <pre className="text-xs text-slate-800 whitespace-pre-wrap font-mono leading-relaxed">{result.suggested.content_outline}</pre>
              </div>
            )}
            {result.suggested?.faq_suggested?.length > 0 && (
              <div className="border border-slate-200 bg-white rounded-md p-5">
                <div className="overline mb-3">FAQ suggérée ({result.suggested.faq_suggested.length})</div>
                <div className="space-y-2.5">
                  {result.suggested.faq_suggested.map((q, i) => (
                    <details key={i} className="border border-slate-100 rounded-md p-3" open={i === 0}>
                      <summary className="text-sm font-medium text-slate-900 cursor-pointer">{q.question}</summary>
                      <p className="text-sm text-slate-600 mt-2 leading-relaxed">{q.answer}</p>
                    </details>
                  ))}
                </div>
              </div>
            )}
          </TabsContent>

          <TabsContent value="improvements" className="mt-0">
            <div className="border border-slate-200 bg-white rounded-md p-5">
              <ul className="space-y-3">
                {(result.improvements || []).map((imp, i) => (
                  <li key={i} className="flex items-start gap-2.5 text-sm text-slate-800 pb-3 border-b border-slate-100 last:border-0 last:pb-0">
                    <div className="w-5 h-5 rounded-full bg-[#002FA7]/10 text-[#002FA7] text-xs font-mono font-bold flex items-center justify-center flex-shrink-0 mt-0.5">{i + 1}</div>
                    <span>{imp}</span>
                  </li>
                ))}
              </ul>
            </div>
          </TabsContent>
        </Tabs>
      )}

      {!result && history.length > 0 && (
        <div className="mt-8">
          <div className="overline mb-3">Optimisations précédentes</div>
          <div className="border border-slate-200 bg-white rounded-md divide-y divide-slate-100">
            {history.slice(0, 10).map((h) => (
              <div
                key={h.id}
                onClick={() => setResult(h)}
                className="p-4 hover:bg-slate-50 cursor-pointer flex items-center justify-between"
                data-testid={`opt-history-${h.id}`}
              >
                <div>
                  <div className="text-sm font-medium text-slate-900">{h.suggested?.h1 || h.page_url}</div>
                  <div className="text-xs text-slate-500 mt-0.5">
                    Focus: {h.focus_keyword || "—"} · {new Date(h.created_at).toLocaleString("fr-FR")}
                  </div>
                </div>
                {h.applied ? (
                  <span className="text-xs text-[#16A34A] inline-flex items-center gap-1"><CheckCircle2 className="w-3.5 h-3.5" /> Brouillon créé</span>
                ) : (
                  <Sparkles className="w-4 h-4 text-slate-400" />
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
