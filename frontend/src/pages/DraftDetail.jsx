import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import PageHeader from "@/components/PageHeader";
import { toast } from "sonner";
import { Save, Send, ArrowLeft, History, Eye, Pencil, CheckCircle2, AlertCircle, Loader2, X } from "lucide-react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";

function MarkdownView({ md }) {
  // Very small markdown renderer (headings, paragraphs, lists, tables)
  const html = renderMarkdown(md || "");
  return <div className="prose-logi" dangerouslySetInnerHTML={{ __html: html }} />;
}

function renderMarkdown(src) {
  // Escape HTML
  let s = src.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  // Tables
  s = s.replace(/((?:^\|.*\|\s*\n)+)/gm, (block) => {
    const lines = block.trim().split("\n");
    if (lines.length < 2) return block;
    const cells = (l) => l.split("|").slice(1, -1).map((c) => c.trim());
    const header = cells(lines[0]);
    const rows = lines.slice(2).map(cells);
    return `<table><thead><tr>${header.map((h) => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows
      .map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
  });
  // Headings
  s = s.replace(/^### (.+)$/gm, "<h3>$1</h3>");
  s = s.replace(/^## (.+)$/gm, "<h2>$1</h2>");
  s = s.replace(/^# (.+)$/gm, "<h1>$1</h1>");
  // Bold + italic
  s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/\*([^*]+)\*/g, "<em>$1</em>");
  // Lists
  s = s.replace(/((?:^\s*[-*] .+\n?)+)/gm, (m) => {
    const items = m.trim().split("\n").map((l) => `<li>${l.replace(/^\s*[-*] /, "")}</li>`).join("");
    return `<ul>${items}</ul>`;
  });
  s = s.replace(/((?:^\s*\d+\. .+\n?)+)/gm, (m) => {
    const items = m.trim().split("\n").map((l) => `<li>${l.replace(/^\s*\d+\. /, "")}</li>`).join("");
    return `<ol>${items}</ol>`;
  });
  // Paragraphs (lines not already wrapped)
  s = s.split(/\n{2,}/).map((para) => {
    if (/^<(h\d|ul|ol|table|li|p|blockquote)/.test(para.trim())) return para;
    if (!para.trim()) return "";
    return `<p>${para.replace(/\n/g, "<br/>")}</p>`;
  }).join("\n");
  return s;
}

export default function DraftDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [draft, setDraft] = useState(null);
  const [editing, setEditing] = useState({});
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [versions, setVersions] = useState([]);

  const load = async () => {
    const { data } = await api.get(`/drafts/${id}`);
    setDraft(data);
    setEditing({
      title: data.title,
      meta_title: data.meta_title || "",
      meta_description: data.meta_description || "",
      body_markdown: data.body_markdown,
    });
    const v = await api.get(`/drafts/${id}/versions`);
    setVersions(v.data.versions);
  };

  useEffect(() => { load(); }, [id]);

  const onSave = async () => {
    setSaving(true);
    try {
      await api.patch(`/drafts/${id}`, editing);
      toast.success("Modifications enregistrées");
      load();
    } catch {
      toast.error("Échec de la sauvegarde");
    } finally {
      setSaving(false);
    }
  };

  const onPublish = async () => {
    setPublishing(true);
    try {
      const { data } = await api.post(`/drafts/${id}/publish`, { publish_immediately: false });
      if (data.wix_draft_id) {
        toast.success("Brouillon créé sur Wix avec succès");
      } else if (data.status === "ready") {
        toast.success("Brouillon validé · prêt à exporter ou copier-coller");
      } else {
        toast.warning("Wix indisponible — brouillon marqué prêt à publier");
      }
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Échec de la publication");
    } finally {
      setPublishing(false);
    }
  };

  const onRollback = async (versionId) => {
    try {
      await api.post(`/drafts/${id}/rollback/${versionId}`);
      toast.success("Version restaurée");
      load();
    } catch {
      toast.error("Échec du rollback");
    }
  };

  if (!draft) {
    return (
      <div className="p-6 md:p-8 max-w-5xl">
        <div className="text-sm text-slate-500">Chargement…</div>
      </div>
    );
  }

  const charLen = (s) => (s || "").length;
  const titleLen = charLen(editing.meta_title);
  const descLen = charLen(editing.meta_description);

  return (
    <div className="p-6 md:p-8 max-w-6xl">
      <button
        onClick={() => navigate("/drafts")}
        className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900 mb-4"
        data-testid="draft-back-button"
      >
        <ArrowLeft className="w-4 h-4" /> Retour aux brouillons
      </button>

      <PageHeader
        overline={`${draft.content_type === "article" ? "Article" : draft.content_type === "page_locale" ? "Page locale" : draft.content_type === "faq" ? "FAQ" : "Service"} · Statut ${draft.status}`}
        title={draft.title}
        action={
          <div className="flex items-center gap-2">
            <button
              onClick={onSave}
              disabled={saving}
              data-testid="draft-save-button"
              className="inline-flex items-center gap-2 bg-white border border-slate-300 hover:bg-slate-50 px-4 py-2 rounded-md text-sm font-medium text-slate-700 transition-colors"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              Enregistrer
            </button>
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <button
                  data-testid="draft-publish-button"
                  className="inline-flex items-center gap-2 bg-[#002FA7] hover:bg-[#001D6B] text-white px-4 py-2 rounded-md text-sm font-medium shadow-sm"
                >
                  <Send className="w-4 h-4" /> Publier sur Wix
                </button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Confirmer la publication ?</AlertDialogTitle>
                  <AlertDialogDescription>
                    Un brouillon sera créé sur votre compte Wix. Aucune publication automatique ne sera faite — vous devrez valider depuis Wix.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Annuler</AlertDialogCancel>
                  <AlertDialogAction
                    onClick={onPublish}
                    disabled={publishing}
                    data-testid="draft-publish-confirm"
                    className="bg-[#002FA7] hover:bg-[#001D6B]"
                  >
                    {publishing ? "Publication…" : "Confirmer"}
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        }
      />

      {draft.wix_draft_id && (
        <div className="mb-5 p-3 border border-green-200 bg-green-50 rounded-md flex items-center gap-2 text-sm text-green-800" data-testid="draft-wix-confirmation">
          <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0" />
          Brouillon créé sur Wix · ID <code className="font-mono text-xs">{draft.wix_draft_id}</code>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Main editor */}
        <div className="lg:col-span-2 border border-slate-200 bg-white rounded-md p-5">
          <Tabs defaultValue="edit">
            <TabsList className="bg-transparent border-b border-slate-200 rounded-none p-0 h-auto w-full justify-start gap-6 mb-4">
              <TabsTrigger value="edit" className="rounded-none border-b-2 border-transparent data-[state=active]:border-[#002FA7] data-[state=active]:bg-transparent px-0 py-3 text-sm">
                <Pencil className="w-3.5 h-3.5 mr-1.5" /> Éditeur
              </TabsTrigger>
              <TabsTrigger value="preview" className="rounded-none border-b-2 border-transparent data-[state=active]:border-[#002FA7] data-[state=active]:bg-transparent px-0 py-3 text-sm">
                <Eye className="w-3.5 h-3.5 mr-1.5" /> Aperçu
              </TabsTrigger>
            </TabsList>
            <TabsContent value="edit" className="mt-0 space-y-3">
              <div>
                <label className="text-xs font-medium text-slate-700 mb-1.5 block">Titre H1</label>
                <input
                  data-testid="draft-title-input"
                  value={editing.title}
                  onChange={(e) => setEditing({ ...editing, title: e.target.value })}
                  className="w-full border border-slate-300 rounded-md px-3 py-2 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7]"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-700 mb-1.5 block">Contenu (markdown)</label>
                <textarea
                  data-testid="draft-body-input"
                  rows={22}
                  value={editing.body_markdown}
                  onChange={(e) => setEditing({ ...editing, body_markdown: e.target.value })}
                  className="w-full border border-slate-300 rounded-md px-3 py-2.5 bg-white text-sm font-mono leading-relaxed focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7] resize-y"
                />
              </div>
            </TabsContent>
            <TabsContent value="preview" className="mt-0">
              <div className="max-h-[600px] overflow-y-auto px-2">
                <h1 className="prose-logi"><span style={{ fontFamily: "Cabinet Grotesk", fontSize: "1.875rem", fontWeight: 700 }}>{editing.title}</span></h1>
                <MarkdownView md={editing.body_markdown} />
              </div>
            </TabsContent>
          </Tabs>
        </div>

        {/* Side panel */}
        <div className="space-y-4">
          <div className="border border-slate-200 bg-white rounded-md p-5">
            <div className="overline mb-3">Métadonnées SEO</div>
            <label className="text-xs font-medium text-slate-700 mb-1.5 flex justify-between">
              <span>Meta title</span>
              <span className={titleLen > 65 ? "text-red-600" : titleLen < 30 && titleLen > 0 ? "text-amber-600" : "text-slate-500"}>{titleLen}/60</span>
            </label>
            <input
              data-testid="draft-meta-title-input"
              value={editing.meta_title}
              onChange={(e) => setEditing({ ...editing, meta_title: e.target.value })}
              className="w-full border border-slate-300 rounded-md px-3 py-2 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7] mb-3"
            />
            <label className="text-xs font-medium text-slate-700 mb-1.5 flex justify-between">
              <span>Meta description</span>
              <span className={descLen > 165 ? "text-red-600" : descLen < 80 && descLen > 0 ? "text-amber-600" : "text-slate-500"}>{descLen}/160</span>
            </label>
            <textarea
              data-testid="draft-meta-desc-input"
              rows={3}
              value={editing.meta_description}
              onChange={(e) => setEditing({ ...editing, meta_description: e.target.value })}
              className="w-full border border-slate-300 rounded-md px-3 py-2 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7] resize-none"
            />
          </div>

          {draft.keywords?.length > 0 && (
            <div className="border border-slate-200 bg-white rounded-md p-5">
              <div className="overline mb-3">Mots-clés</div>
              <div className="flex flex-wrap gap-1.5">
                {draft.keywords.map((k) => (
                  <span key={k} className="bg-slate-100 text-slate-800 text-xs px-2 py-1 rounded">{k}</span>
                ))}
              </div>
            </div>
          )}

          {draft.faq?.length > 0 && (
            <div className="border border-slate-200 bg-white rounded-md p-5">
              <div className="overline mb-3">FAQ générée ({draft.faq.length})</div>
              <div className="space-y-2.5">
                {draft.faq.map((q, i) => (
                  <details key={i} className="border border-slate-100 rounded-md p-2.5">
                    <summary className="text-xs font-medium text-slate-900 cursor-pointer">{q.question}</summary>
                    <p className="text-xs text-slate-600 mt-2 leading-relaxed">{q.answer}</p>
                  </details>
                ))}
              </div>
            </div>
          )}

          <div className="border border-slate-200 bg-white rounded-md p-5">
            <div className="overline mb-3 flex items-center gap-1.5">
              <History className="w-3 h-3" /> Versions ({versions.length})
            </div>
            {versions.length === 0 ? (
              <p className="text-xs text-slate-500">Aucune version précédente.</p>
            ) : (
              <ul className="space-y-2">
                {versions.slice(0, 10).map((v) => (
                  <li key={v.id} className="flex items-center justify-between text-xs">
                    <span className="text-slate-600">{new Date(v.created_at).toLocaleString("fr-FR")}</span>
                    <button
                      onClick={() => onRollback(v.id)}
                      data-testid={`rollback-${v.id}`}
                      className="text-[#002FA7] hover:underline font-medium"
                    >
                      Restaurer
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
