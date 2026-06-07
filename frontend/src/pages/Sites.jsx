import { useState } from "react";
import { api } from "@/lib/api";
import { useSites } from "@/contexts/SiteContext";
import PageHeader from "@/components/PageHeader";
import { Plus, Trash2, ShieldCheck, KeyRound, Globe2, Zap, Download, Server } from "lucide-react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogTrigger,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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

const empty = {
  site_type: "url_crawl",
  label: "Logirent",
  name: "",
  base_url: "",
  wix_site_id: "",
  wix_account_id: "",
  wix_api_key: "",
  vps_api_url: "",
  vps_api_token: "",
};

export default function Sites() {
  const { sites, refresh, selectSite } = useSites();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(empty);
  const [saving, setSaving] = useState(false);
  const [quickAdding, setQuickAdding] = useState(false);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e?.target ? e.target.value : e }));

  const onSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = {
        site_type: form.site_type,
        label: form.label,
        name: form.name,
        base_url: form.base_url || null,
      };
      if (form.site_type === "wix") {
        payload.wix_site_id = form.wix_site_id;
        payload.wix_account_id = form.wix_account_id;
        payload.wix_api_key = form.wix_api_key;
      }
      if (form.site_type === "vps_api") {
        payload.vps_api_url = form.vps_api_url;
        payload.vps_api_token = form.vps_api_token;
      }
      const { data } = await api.post("/sites", payload);
      toast.success(`${data.name} connecté`);
      setOpen(false);
      setForm(empty);
      await refresh();
      selectSite(data.id);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Échec de la connexion");
    } finally {
      setSaving(false);
    }
  };

  const onDelete = async (id) => {
    try {
      await api.delete(`/sites/${id}`);
      toast.success("Site supprimé");
      refresh();
    } catch {
      toast.error("Échec de la suppression");
    }
  };

  const onQuickAdd = async () => {
    setQuickAdding(true);
    try {
      const { data } = await api.post("/sites/quick-add-emergent");
      const added = data.added?.length || 0;
      const skipped = data.skipped?.length || 0;
      if (added > 0) {
        toast.success(`${added} site(s) connecté(s) instantanément`);
        await refresh();
        if (data.added[0]) selectSite(data.added[0].id);
      } else if (skipped > 0) {
        toast.info("Logirent et Logitime sont déjà connectés");
      }
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Échec");
    } finally {
      setQuickAdding(false);
    }
  };

  const hasEmergentSites = sites.some((s) => s.site_type === "url_crawl" &&
    (s.base_url?.includes("logirent") || s.base_url?.includes("logitime")));

  return (
    <div className="p-6 md:p-8 max-w-6xl">
      <PageHeader
        overline="Connexions"
        title="Vos sites"
        description="Connectez vos sites par URL publique (Emergent, WordPress, autre) ou via l'API Wix. L'app scanne automatiquement vos vraies pages pour l'audit SEO."
        action={
          <div className="flex items-center gap-2">
            {!hasEmergentSites && (
              <button
                onClick={onQuickAdd}
                disabled={quickAdding}
                data-testid="quick-add-emergent-button"
                className="inline-flex items-center gap-2 bg-amber-400 hover:bg-amber-500 disabled:opacity-60 text-amber-950 px-4 py-2 rounded-md text-sm font-medium transition-colors shadow-sm"
              >
                <Zap className="w-4 h-4" />
                {quickAdding ? "Connexion…" : "Ajouter logirent.ch + logitime.ch"}
              </button>
            )}
            <Dialog open={open} onOpenChange={setOpen}>
              <DialogTrigger asChild>
                <button
                  data-testid="open-add-site-dialog"
                  className="inline-flex items-center gap-2 bg-[#002FA7] hover:bg-[#001D6B] text-white px-4 py-2 rounded-md text-sm font-medium transition-colors shadow-sm"
                >
                  <Plus className="w-4 h-4" /> Ajouter un site
                </button>
              </DialogTrigger>
              <DialogContent className="max-w-lg">
                <DialogHeader>
                  <DialogTitle>Connecter un site</DialogTitle>
                  <DialogDescription>
                    Choisissez le mode de connexion adapté à votre plateforme.
                  </DialogDescription>
                </DialogHeader>
                <form onSubmit={onSubmit} className="space-y-3.5" data-testid="add-site-form">
                  {/* Site type selector */}
                  <div className="grid grid-cols-3 gap-2">
                    <button
                      type="button"
                      onClick={() => setForm((f) => ({ ...f, site_type: "url_crawl" }))}
                      data-testid="site-type-url-crawl"
                      className={`p-3 border rounded-md text-left transition-all ${
                        form.site_type === "url_crawl"
                          ? "border-[#002FA7] bg-blue-50/50 ring-2 ring-[#002FA7]/20"
                          : "border-slate-200 hover:border-slate-300"
                      }`}
                    >
                      <Globe2 className="w-4 h-4 text-[#002FA7] mb-1.5" />
                      <div className="text-xs font-semibold text-slate-950">URL publique</div>
                      <div className="text-[10px] text-slate-500 mt-0.5">Lecture seule</div>
                    </button>
                    <button
                      type="button"
                      onClick={() => setForm((f) => ({ ...f, site_type: "vps_api" }))}
                      data-testid="site-type-vps-api"
                      className={`p-3 border rounded-md text-left transition-all ${
                        form.site_type === "vps_api"
                          ? "border-[#002FA7] bg-blue-50/50 ring-2 ring-[#002FA7]/20"
                          : "border-slate-200 hover:border-slate-300"
                      }`}
                    >
                      <Server className="w-4 h-4 text-[#002FA7] mb-1.5" />
                      <div className="text-xs font-semibold text-slate-950">VPS API</div>
                      <div className="text-[10px] text-slate-500 mt-0.5">Logirent / Logitime</div>
                    </button>
                    <button
                      type="button"
                      onClick={() => setForm((f) => ({ ...f, site_type: "wix" }))}
                      data-testid="site-type-wix"
                      className={`p-3 border rounded-md text-left transition-all ${
                        form.site_type === "wix"
                          ? "border-[#002FA7] bg-blue-50/50 ring-2 ring-[#002FA7]/20"
                          : "border-slate-200 hover:border-slate-300"
                      }`}
                    >
                      <KeyRound className="w-4 h-4 text-[#002FA7] mb-1.5" />
                      <div className="text-xs font-semibold text-slate-950">Wix (API)</div>
                      <div className="text-[10px] text-slate-500 mt-0.5">Lecture + publication</div>
                    </button>
                  </div>

                  <div>
                    <label className="text-xs font-medium text-slate-700 mb-1.5 block">Site (label)</label>
                    <Select value={form.label} onValueChange={set("label")}>
                      <SelectTrigger data-testid="site-label-select"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="Logirent">Logirent</SelectItem>
                        <SelectItem value="Logitime">Logitime</SelectItem>
                        <SelectItem value="Autre">Autre</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <label className="text-xs font-medium text-slate-700 mb-1.5 block">Nom interne</label>
                    <input
                      required
                      data-testid="site-name-input"
                      value={form.name}
                      onChange={set("name")}
                      placeholder={form.site_type === "url_crawl" ? "Logirent (logirent.ch)" : "Logirent Wix"}
                      className="w-full border border-slate-300 rounded-md px-3 py-2 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7]"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-slate-700 mb-1.5 block">URL du site {form.site_type === "url_crawl" ? "*" : "(optionnel)"}</label>
                    <input
                      required={form.site_type === "url_crawl"}
                      data-testid="site-base-url-input"
                      value={form.base_url}
                      onChange={set("base_url")}
                      placeholder="https://www.logirent.ch"
                      className="w-full border border-slate-300 rounded-md px-3 py-2 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7]"
                    />
                  </div>

                  {form.site_type === "vps_api" && (
                    <div className="border-t border-slate-100 pt-3.5 space-y-3.5">
                      <div className="text-xs text-slate-600 bg-amber-50 border border-amber-200 rounded p-2.5">
                        <strong>Kit Mini-API à déployer sur votre VPS :</strong>{" "}
                        <a href="/logi-seo-vps-mini-api.zip" download className="text-[#002FA7] underline font-medium" data-testid="download-vps-kit">
                          Télécharger le kit (.zip)
                        </a>
                        {" "}— suivez le README pour l&apos;installer en 5 minutes sur votre VPS.
                      </div>
                      <div>
                        <label className="text-xs font-medium text-slate-700 mb-1.5 block">URL de l&apos;API VPS *</label>
                        <input
                          required={form.site_type === "vps_api"}
                          data-testid="site-vps-api-url-input"
                          value={form.vps_api_url}
                          onChange={set("vps_api_url")}
                          placeholder="https://api.logirent.ch"
                          className="w-full border border-slate-300 rounded-md px-3 py-2 bg-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7]"
                        />
                      </div>
                      <div>
                        <label className="text-xs font-medium text-slate-700 mb-1.5 block">Token API (Bearer) *</label>
                        <input
                          required={form.site_type === "vps_api"}
                          data-testid="site-vps-api-token-input"
                          value={form.vps_api_token}
                          onChange={set("vps_api_token")}
                          type="password"
                          placeholder="Valeur de SEO_API_TOKEN dans .env"
                          className="w-full border border-slate-300 rounded-md px-3 py-2 bg-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7]"
                        />
                      </div>
                    </div>
                  )}

                  {form.site_type === "wix" && (
                    <div className="border-t border-slate-100 pt-3.5 space-y-3.5">
                      <div className="text-xs text-slate-600">
                        Générez une clé depuis Wix → Settings → Headless Settings → API keys (permissions Blog & Site Pages).
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label className="text-xs font-medium text-slate-700 mb-1.5 block">Wix Site ID *</label>
                          <input
                            required={form.site_type === "wix"}
                            data-testid="site-wix-site-id-input"
                            value={form.wix_site_id}
                            onChange={set("wix_site_id")}
                            placeholder="abc-123-…"
                            className="w-full border border-slate-300 rounded-md px-3 py-2 bg-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7]"
                          />
                        </div>
                        <div>
                          <label className="text-xs font-medium text-slate-700 mb-1.5 block">Wix Account ID *</label>
                          <input
                            required={form.site_type === "wix"}
                            data-testid="site-wix-account-id-input"
                            value={form.wix_account_id}
                            onChange={set("wix_account_id")}
                            placeholder="xyz-456-…"
                            className="w-full border border-slate-300 rounded-md px-3 py-2 bg-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7]"
                          />
                        </div>
                      </div>
                      <div>
                        <label className="text-xs font-medium text-slate-700 mb-1.5 block">Wix API Key *</label>
                        <input
                          required={form.site_type === "wix"}
                          data-testid="site-wix-api-key-input"
                          value={form.wix_api_key}
                          onChange={set("wix_api_key")}
                          type="password"
                          placeholder="IST.eyJraWQiOi…"
                          className="w-full border border-slate-300 rounded-md px-3 py-2 bg-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7]"
                        />
                      </div>
                    </div>
                  )}

                  <DialogFooter className="pt-2">
                    <button
                      type="button"
                      onClick={() => setOpen(false)}
                      className="px-4 py-2 text-sm text-slate-700 border border-slate-300 rounded-md hover:bg-slate-50"
                    >
                      Annuler
                    </button>
                    <button
                      type="submit"
                      disabled={saving}
                      data-testid="submit-add-site"
                      className="px-4 py-2 bg-[#002FA7] hover:bg-[#001D6B] text-white text-sm font-medium rounded-md disabled:opacity-60"
                    >
                      {saving ? "Connexion…" : "Connecter"}
                    </button>
                  </DialogFooter>
                </form>
              </DialogContent>
            </Dialog>
          </div>
        }
      />

      {sites.length === 0 ? (
        <div className="border border-dashed border-slate-300 bg-white rounded-md p-10 text-center" data-testid="sites-empty">
          <Globe2 className="w-10 h-10 text-[#002FA7] mx-auto mb-3" />
          <h2 className="font-display text-xl font-semibold text-slate-950 mb-2">Démarrez en 1 clic</h2>
          <p className="text-sm text-slate-600 max-w-md mx-auto mb-5">
            Connectez vos deux sites Emergent <strong>logirent.ch</strong> et <strong>logitime.ch</strong> instantanément, sans aucune clé API.
          </p>
          <button
            onClick={onQuickAdd}
            disabled={quickAdding}
            data-testid="quick-add-emergent-empty-button"
            className="inline-flex items-center gap-2 bg-amber-400 hover:bg-amber-500 disabled:opacity-60 text-amber-950 px-5 py-2.5 rounded-md text-sm font-medium transition-colors shadow-sm"
          >
            <Zap className="w-4 h-4" />
            {quickAdding ? "Connexion…" : "Connecter logirent.ch + logitime.ch"}
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4" data-testid="sites-list">
          {sites.map((s) => (
            <div key={s.id} className="border border-slate-200 bg-white rounded-md p-5" data-testid={`site-card-${s.id}`}>
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div
                    className="w-11 h-11 rounded-md flex items-center justify-center text-white font-bold"
                    style={{ background: s.label === "Logitime" ? "#0F766E" : s.label === "Logirent" ? "#002FA7" : "#64748B" }}
                  >
                    {s.label.slice(0, 2).toUpperCase()}
                  </div>
                  <div>
                    <div className="font-display font-semibold text-slate-950">{s.name}</div>
                    <div className="text-xs text-slate-500 flex items-center gap-1.5">
                      {s.site_type === "vps_api" ? (
                        <>
                          <Server className="w-3 h-3" /> VPS API · {s.label}
                        </>
                      ) : s.site_type === "url_crawl" ? (
                        <>
                          <Globe2 className="w-3 h-3" /> URL publique · {s.label}
                        </>
                      ) : (
                        <>
                          <KeyRound className="w-3 h-3" /> Wix API · {s.label}
                        </>
                      )}
                    </div>
                  </div>
                </div>
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <button
                      data-testid={`delete-site-${s.id}`}
                      className="p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-md transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Supprimer ce site ?</AlertDialogTitle>
                      <AlertDialogDescription>
                        La connexion sera retirée. Les brouillons et audits existants seront conservés mais ne pourront plus être publiés sur ce site.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Annuler</AlertDialogCancel>
                      <AlertDialogAction
                        data-testid={`confirm-delete-site-${s.id}`}
                        onClick={() => onDelete(s.id)}
                        className="bg-red-600 hover:bg-red-700"
                      >
                        Supprimer
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>

              <dl className="text-xs space-y-1.5">
                {s.site_type === "vps_api" ? (
                  <>
                    <div className="flex justify-between gap-2">
                      <dt className="text-slate-500">URL site</dt>
                      <dd className="text-slate-800 truncate max-w-[220px]">{s.base_url || "—"}</dd>
                    </div>
                    <div className="flex justify-between gap-2">
                      <dt className="text-slate-500">URL API</dt>
                      <dd className="font-mono text-slate-800 truncate max-w-[220px]">{s.vps_api_url || "—"}</dd>
                    </div>
                    <div className="flex justify-between gap-2">
                      <dt className="text-slate-500">Token</dt>
                      <dd className="flex items-center gap-1 text-[#16A34A]">
                        <ShieldCheck className="w-3.5 h-3.5" /> {s.has_vps_token ? "Configuré" : "Manquant"}
                      </dd>
                    </div>
                  </>
                ) : s.site_type === "url_crawl" ? (
                  <>
                    <div className="flex justify-between gap-2">
                      <dt className="text-slate-500">URL</dt>
                      <dd className="text-slate-800 truncate max-w-[220px]">{s.base_url || "—"}</dd>
                    </div>
                    <div className="flex justify-between gap-2">
                      <dt className="text-slate-500">Méthode</dt>
                      <dd className="flex items-center gap-1 text-[#16A34A]">
                        <ShieldCheck className="w-3.5 h-3.5" /> Scraping public
                      </dd>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="flex justify-between gap-2">
                      <dt className="text-slate-500">Site ID</dt>
                      <dd className="font-mono text-slate-800 truncate max-w-[180px]" title={s.wix_site_id}>{s.wix_site_id}</dd>
                    </div>
                    <div className="flex justify-between gap-2">
                      <dt className="text-slate-500">Account ID</dt>
                      <dd className="font-mono text-slate-800 truncate max-w-[180px]" title={s.wix_account_id}>{s.wix_account_id}</dd>
                    </div>
                    <div className="flex justify-between gap-2">
                      <dt className="text-slate-500">URL</dt>
                      <dd className="text-slate-800 truncate max-w-[200px]">{s.base_url || "—"}</dd>
                    </div>
                    <div className="flex justify-between gap-2">
                      <dt className="text-slate-500">API Key</dt>
                      <dd className="flex items-center gap-1 text-[#16A34A]">
                        <ShieldCheck className="w-3.5 h-3.5" /> Chiffrée
                      </dd>
                    </div>
                  </>
                )}
              </dl>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
