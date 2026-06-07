import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useSites } from "@/contexts/SiteContext";
import PageHeader from "@/components/PageHeader";
import { toast } from "sonner";
import { Sparkles, Loader2, X } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const types = [
  { v: "article", label: "Article de blog" },
  { v: "page_locale", label: "Page locale SEO" },
  { v: "faq", label: "Page FAQ" },
  { v: "service_description", label: "Description de service" },
];
const tones = [
  { v: "professionnel", label: "Professionnel" },
  { v: "amical", label: "Amical" },
  { v: "expert", label: "Expert" },
  { v: "pedagogique", label: "Pédagogique" },
];
const lengths = [
  { v: "court", label: "Court (500-700 mots)" },
  { v: "moyen", label: "Moyen (900-1200 mots)" },
  { v: "long", label: "Long (1500-2000 mots)" },
];

export default function Generator() {
  const { activeSite } = useSites();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    content_type: "article",
    topic: "",
    keywords: [],
    keywordInput: "",
    city: "",
    tone: "professionnel",
    target_length: "moyen",
    extra_instructions: "",
  });
  const [loading, setLoading] = useState(false);

  const set = (k) => (v) => setForm((f) => ({ ...f, [k]: v?.target ? v.target.value : v }));

  const addKeyword = (e) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      const raw = form.keywordInput.trim().replace(/,$/, "");
      if (!raw) return;
      // Auto-split if the user pasted multiple keywords separated by commas, semicolons or newlines
      const parts = raw.split(/[,;\n]+/).map((p) => p.trim()).filter(Boolean);
      const toAdd = parts.filter((p) => !form.keywords.includes(p));
      if (toAdd.length > 0) {
        setForm((f) => ({ ...f, keywords: [...f.keywords, ...toAdd], keywordInput: "" }));
      }
    }
  };

  // Handle paste event — auto-split pasted text into multiple tags
  const handlePaste = (e) => {
    const pasted = (e.clipboardData || window.clipboardData).getData("text");
    if (!pasted) return;
    const parts = pasted.split(/[,;\n]+/).map((p) => p.trim()).filter(Boolean);
    if (parts.length > 1) {
      e.preventDefault();
      const toAdd = parts.filter((p) => !form.keywords.includes(p));
      if (toAdd.length > 0) {
        setForm((f) => ({ ...f, keywords: [...f.keywords, ...toAdd], keywordInput: "" }));
      }
    }
  };
  const removeKeyword = (k) => setForm((f) => ({ ...f, keywords: f.keywords.filter((x) => x !== k) }));

  const onSubmit = async (e) => {
    e.preventDefault();
    if (!activeSite) return toast.error("Sélectionnez d'abord un site");
    if (!form.topic.trim()) return toast.error("Indiquez un sujet");
    setLoading(true);
    try {
      // Start async job
      const { data: job } = await api.post("/content/generate-async", {
        site_id: activeSite.id,
        content_type: form.content_type,
        topic: form.topic.trim(),
        keywords: form.keywords,
        city: form.city.trim() || null,
        tone: form.tone,
        target_length: form.target_length,
        extra_instructions: form.extra_instructions.trim() || null,
      });
      const jobId = job.job_id;
      toast.info("Génération en cours… (peut prendre 1-3 minutes)");

      // Poll every 3 seconds for up to 5 minutes
      const maxAttempts = 100;
      let attempts = 0;
      while (attempts < maxAttempts) {
        await new Promise((r) => setTimeout(r, 3000));
        attempts++;
        const { data: status } = await api.get(`/content/jobs/${jobId}`);
        if (status.status === "completed") {
          toast.success("Contenu généré ✨");
          navigate(`/drafts/${status.result.id}`);
          return;
        }
        if (status.status === "failed") {
          throw new Error(status.error || "Erreur de génération");
        }
        // still pending → continue
      }
      throw new Error("Génération trop longue (>5 min). Réessayez avec un sujet plus court.");
    } catch (err) {
      toast.error(err?.response?.data?.detail || err?.message || "Erreur de génération");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 md:p-8 max-w-4xl">
      <PageHeader
        overline={activeSite ? `Génération IA · ${activeSite.label}` : "Génération IA"}
        title="Créer du contenu SEO optimisé IA"
        description="Génère un contenu structuré pour Google ET les moteurs IA : réponse courte, paragraphes, FAQ, tableau comparatif, données locales. Modèle : Claude Sonnet 4.5."
      />

      {!activeSite ? (
        <div className="border border-dashed border-slate-300 bg-white rounded-md p-10 text-center">
          <p className="text-sm text-slate-600">Sélectionnez un site Wix actif pour générer du contenu.</p>
        </div>
      ) : (
        <form onSubmit={onSubmit} className="border border-slate-200 bg-white rounded-md p-6 space-y-5" data-testid="generator-form">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-medium text-slate-700 mb-1.5 block">Type de contenu</label>
              <Select value={form.content_type} onValueChange={set("content_type")}>
                <SelectTrigger data-testid="gen-content-type-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {types.map((t) => (
                    <SelectItem key={t.v} value={t.v}>{t.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-xs font-medium text-slate-700 mb-1.5 block">Longueur</label>
              <Select value={form.target_length} onValueChange={set("target_length")}>
                <SelectTrigger data-testid="gen-length-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {lengths.map((t) => (
                    <SelectItem key={t.v} value={t.v}>{t.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div>
            <label className="text-xs font-medium text-slate-700 mb-1.5 block">Sujet principal *</label>
            <input
              required
              data-testid="gen-topic-input"
              value={form.topic}
              onChange={set("topic")}
              placeholder="Ex : Location meublée courte durée à Lyon"
              className="w-full border border-slate-300 rounded-md px-3 py-2 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7]"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-medium text-slate-700 mb-1.5 block">Ville / zone ciblée</label>
              <input
                data-testid="gen-city-input"
                value={form.city}
                onChange={set("city")}
                placeholder="Lyon, Paris, Marseille…"
                className="w-full border border-slate-300 rounded-md px-3 py-2 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7]"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-700 mb-1.5 block">Ton</label>
              <Select value={form.tone} onValueChange={set("tone")}>
                <SelectTrigger data-testid="gen-tone-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {tones.map((t) => (
                    <SelectItem key={t.v} value={t.v}>{t.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div>
            <label className="text-xs font-medium text-slate-700 mb-1.5 block">Mots-clés (Entrée pour ajouter)</label>
            <div className="flex flex-wrap items-center gap-1.5 border border-slate-300 rounded-md px-2 py-1.5 bg-white focus-within:ring-2 focus-within:ring-[#002FA7]/30 focus-within:border-[#002FA7]">
              {form.keywords.map((k) => (
                <span key={k} className="inline-flex items-center gap-1 bg-slate-100 text-slate-800 text-xs px-2 py-1 rounded">
                  {k}
                  <button type="button" onClick={() => removeKeyword(k)} className="hover:text-red-600">
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
              <input
                data-testid="gen-keywords-input"
                value={form.keywordInput}
                onChange={(e) => setForm((f) => ({ ...f, keywordInput: e.target.value }))}
                onKeyDown={addKeyword}
                onPaste={handlePaste}
                placeholder={form.keywords.length === 0 ? "Tapez un mot-clé puis Entrée (vous pouvez aussi coller une liste séparée par virgules)" : ""}
                className="flex-1 min-w-[150px] py-1 text-sm outline-none bg-transparent"
              />
            </div>
            {form.keywords.length === 0 && (
              <p className="text-[10px] text-slate-500 mt-1">💡 Astuce : 3 à 7 mots-clés max, séparés par Entrée. Au-delà, la génération devient lente.</p>
            )}
            {form.keywords.length > 8 && (
              <p className="text-[11px] text-amber-700 mt-1">⚠️ {form.keywords.length} mots-clés — la génération peut prendre 2-3 minutes.</p>
            )}
          </div>

          <div>
            <label className="text-xs font-medium text-slate-700 mb-1.5 block">Instructions complémentaires</label>
            <textarea
              data-testid="gen-extra-input"
              rows={3}
              value={form.extra_instructions}
              onChange={set("extra_instructions")}
              placeholder="Ex : Mettre en avant la flexibilité contractuelle, citer la loi Alur, inclure tableau comparatif location nue vs meublée…"
              className="w-full border border-slate-300 rounded-md px-3 py-2 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7] resize-none"
            />
          </div>

          <div className="flex items-center justify-between pt-2 border-t border-slate-100">
            <div className="text-xs text-slate-500 flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-[#002FA7]" />
              Optimisé pour Google AI Overviews, ChatGPT, Gemini, Perplexity.
            </div>
            <button
              type="submit"
              disabled={loading}
              data-testid="gen-submit-button"
              className="inline-flex items-center gap-2 bg-[#002FA7] hover:bg-[#001D6B] disabled:opacity-60 text-white px-5 py-2.5 rounded-md text-sm font-medium transition-colors shadow-sm"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
              {loading ? "Génération en cours…" : "Générer le contenu"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
