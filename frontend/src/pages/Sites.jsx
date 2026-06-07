import { useState } from "react";
import { api } from "@/lib/api";
import { useSites } from "@/contexts/SiteContext";
import PageHeader from "@/components/PageHeader";
import { Plus, Trash2, ShieldCheck, KeyRound, Globe2, Zap, Download, Server, FolderUp, Github, CheckCircle2, Loader2 } from "lucide-react";
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
  ftp_host: "",
  ftp_port: 21,
  ftp_user: "",
  ftp_password: "",
  ftp_remote_path: "/public_html/blog",
  ftp_public_url: "",
  github_token: "",
  github_owner: "",
  github_repo: "",
  github_branch: "main",
  github_folder: "public/blog",
  github_public_url: "",
};

export default function Sites() {
  const { sites, refresh, selectSite } = useSites();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(empty);
  const [saving, setSaving] = useState(false);
  const [quickAdding, setQuickAdding] = useState(false);
  // GitHub config dialog
  const [ghSite, setGhSite] = useState(null); // site being configured
  const [ghForm, setGhForm] = useState({
    github_token: "",
    github_owner: "",
    github_repo: "",
    github_branch: "main",
    github_folder: "public/blog",
    github_public_url: "",
  });
  const [ghSaving, setGhSaving] = useState(false);
  const [ghTesting, setGhTesting] = useState(false);
  const [ghTestResult, setGhTestResult] = useState(null);
  const ghSet = (k) => (e) => setGhForm((f) => ({ ...f, [k]: e?.target ? e.target.value : e }));

  const openGhDialog = (site) => {
    setGhSite(site);
    setGhTestResult(null);
    setGhForm({
      github_token: "", // never echo back the token from server
      github_owner: site.github_owner || "",
      github_repo: site.github_repo || "",
      github_branch: site.github_branch || "main",
      github_folder: site.github_folder || "public/blog",
      github_public_url: site.github_public_url || site.base_url || "",
    });
  };

  const saveGh = async (e) => {
    e?.preventDefault?.();
    if (!ghSite) return;
    setGhSaving(true);
    try {
      const payload = {
        github_owner: ghForm.github_owner.trim(),
        github_repo: ghForm.github_repo.trim(),
        github_branch: (ghForm.github_branch || "main").trim(),
        github_folder: ghForm.github_folder.trim(),
        github_public_url: ghForm.github_public_url.trim() || null,
      };
      if (ghForm.github_token.trim()) payload.github_token = ghForm.github_token.trim();
      await api.patch(`/sites/${ghSite.id}`, payload);
      toast.success("Configuration GitHub enregistrée");
      await refresh();
      setGhSite(null);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Échec de l'enregistrement");
    } finally {
      setGhSaving(false);
    }
  };

  const testGh = async () => {
    if (!ghSite) return;
    // Save first so test endpoint can read the latest config (esp. token)
    setGhTesting(true);
    setGhTestResult(null);
    try {
      const payload = {
        github_owner: ghForm.github_owner.trim(),
        github_repo: ghForm.github_repo.trim(),
        github_branch: (ghForm.github_branch || "main").trim(),
        github_folder: ghForm.github_folder.trim(),
      };
      if (ghForm.github_token.trim()) payload.github_token = ghForm.github_token.trim();
      if (!payload.github_owner || !payload.github_repo) {
        toast.error("Renseignez owner et repo avant de tester");
        return;
      }
      await api.patch(`/sites/${ghSite.id}`, payload);
      const { data } = await api.post(`/sites/${ghSite.id}/test-github`);
      setGhTestResult(data);
      toast.success(`Connexion OK · branche ${data.branch} · dernier commit ${data.commit_sha}`);
      await refresh();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Échec du test");
      setGhTestResult({ error: err?.response?.data?.detail || "Erreur inconnue" });
    } finally {
      setGhTesting(false);
    }
  };

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
      if (form.site_type === "ftp") {
        payload.ftp_host = form.ftp_host;
        payload.ftp_port = parseInt(form.ftp_port || 21, 10);
        payload.ftp_user = form.ftp_user;
        payload.ftp_password = form.ftp_password;
        payload.ftp_remote_path = form.ftp_remote_path;
        payload.ftp_public_url = form.ftp_public_url || null;
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
                  <div className="grid grid-cols-4 gap-2">
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
                      onClick={() => setForm((f) => ({ ...f, site_type: "ftp" }))}
                      data-testid="site-type-ftp"
                      className={`p-3 border rounded-md text-left transition-all ${
                        form.site_type === "ftp"
                          ? "border-[#002FA7] bg-blue-50/50 ring-2 ring-[#002FA7]/20"
                          : "border-slate-200 hover:border-slate-300"
                      }`}
                    >
                      <FolderUp className="w-4 h-4 text-[#002FA7] mb-1.5" />
                      <div className="text-xs font-semibold text-slate-950">FTP</div>
                      <div className="text-[10px] text-slate-500 mt-0.5">Le plus simple</div>
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
                      <div className="text-[10px] text-slate-500 mt-0.5">Node.js</div>
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
                      <div className="text-[10px] text-slate-500 mt-0.5">API native</div>
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

                  {form.site_type === "ftp" && (
                    <div className="border-t border-slate-100 pt-3.5 space-y-3.5">
                      <div className="text-xs text-slate-700 bg-blue-50 border border-blue-200 rounded p-2.5">
                        <strong>FTP simple :</strong> les contenus sont uploadés en <strong>HTML + JSON</strong> dans le dossier choisi. Les fichiers HTML sont directement indexables par Google (pas besoin de SSR).
                      </div>
                      <div className="grid grid-cols-3 gap-3">
                        <div className="col-span-2">
                          <label className="text-xs font-medium text-slate-700 mb-1.5 block">Hôte FTP *</label>
                          <input
                            required={form.site_type === "ftp"}
                            data-testid="site-ftp-host-input"
                            value={form.ftp_host}
                            onChange={set("ftp_host")}
                            placeholder="ftp.logirent.ch"
                            className="w-full border border-slate-300 rounded-md px-3 py-2 bg-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7]"
                          />
                        </div>
                        <div>
                          <label className="text-xs font-medium text-slate-700 mb-1.5 block">Port</label>
                          <input
                            data-testid="site-ftp-port-input"
                            type="number"
                            value={form.ftp_port}
                            onChange={set("ftp_port")}
                            className="w-full border border-slate-300 rounded-md px-3 py-2 bg-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7]"
                          />
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label className="text-xs font-medium text-slate-700 mb-1.5 block">Utilisateur *</label>
                          <input
                            required={form.site_type === "ftp"}
                            data-testid="site-ftp-user-input"
                            value={form.ftp_user}
                            onChange={set("ftp_user")}
                            placeholder="ftpuser"
                            className="w-full border border-slate-300 rounded-md px-3 py-2 bg-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7]"
                          />
                        </div>
                        <div>
                          <label className="text-xs font-medium text-slate-700 mb-1.5 block">Mot de passe *</label>
                          <input
                            required={form.site_type === "ftp"}
                            data-testid="site-ftp-password-input"
                            type="password"
                            value={form.ftp_password}
                            onChange={set("ftp_password")}
                            className="w-full border border-slate-300 rounded-md px-3 py-2 bg-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7]"
                          />
                        </div>
                      </div>
                      <div>
                        <label className="text-xs font-medium text-slate-700 mb-1.5 block">Dossier distant *</label>
                        <input
                          required={form.site_type === "ftp"}
                          data-testid="site-ftp-path-input"
                          value={form.ftp_remote_path}
                          onChange={set("ftp_remote_path")}
                          placeholder="/public_html/blog"
                          className="w-full border border-slate-300 rounded-md px-3 py-2 bg-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7]"
                        />
                        <div className="text-[11px] text-slate-500 mt-1.5">
                          Exemples par hébergeur :
                          <span className="font-mono mx-1 text-slate-700">/public_html/blog</span>(cPanel) ·
                          <span className="font-mono mx-1 text-slate-700">/httpdocs/blog</span>(Plesk) ·
                          <span className="font-mono mx-1 text-slate-700">/var/www/logirent/blog</span>(VPS Linux) ·
                          <span className="font-mono mx-1 text-slate-700">/www/blog</span>(OVH)
                        </div>
                      </div>
                      <div>
                        <label className="text-xs font-medium text-slate-700 mb-1.5 block">URL publique du dossier (pour la canonical) </label>
                        <input
                          data-testid="site-ftp-public-url-input"
                          value={form.ftp_public_url}
                          onChange={set("ftp_public_url")}
                          placeholder="https://www.logirent.ch/blog"
                          className="w-full border border-slate-300 rounded-md px-3 py-2 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7]"
                        />
                        <div className="text-[11px] text-slate-500 mt-1.5">
                          URL où ces fichiers seront accessibles. Ex : si le dossier <span className="font-mono">/public_html/blog</span> est servi sous <span className="font-mono">https://www.logirent.ch/blog</span>.
                        </div>
                      </div>
                    </div>
                  )}

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
                      {s.site_type === "ftp" ? (
                        <>
                          <FolderUp className="w-3 h-3" /> FTP · {s.label}
                        </>
                      ) : s.site_type === "vps_api" ? (
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
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => openGhDialog(s)}
                    data-testid={`configure-github-${s.id}`}
                    title="Configurer la publication GitHub"
                    className={`p-2 rounded-md transition-colors ${
                      s.has_github_token
                        ? "text-emerald-600 bg-emerald-50 hover:bg-emerald-100"
                        : "text-slate-400 hover:text-slate-900 hover:bg-slate-100"
                    }`}
                  >
                    <Github className="w-4 h-4" />
                  </button>
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
              </div>

              <dl className="text-xs space-y-1.5">
                {s.site_type === "ftp" ? (
                  <>
                    <div className="flex justify-between gap-2">
                      <dt className="text-slate-500">Hôte FTP</dt>
                      <dd className="font-mono text-slate-800 truncate max-w-[220px]">{s.ftp_host}:{s.ftp_port}</dd>
                    </div>
                    <div className="flex justify-between gap-2">
                      <dt className="text-slate-500">Utilisateur</dt>
                      <dd className="font-mono text-slate-800 truncate max-w-[180px]">{s.ftp_user}</dd>
                    </div>
                    <div className="flex justify-between gap-2">
                      <dt className="text-slate-500">Dossier distant</dt>
                      <dd className="font-mono text-slate-800 truncate max-w-[200px]">{s.ftp_remote_path}</dd>
                    </div>
                    <div className="flex justify-between gap-2">
                      <dt className="text-slate-500">URL publique</dt>
                      <dd className="text-slate-800 truncate max-w-[220px]">{s.ftp_public_url || "—"}</dd>
                    </div>
                    <div className="flex justify-between gap-2">
                      <dt className="text-slate-500">Mot de passe</dt>
                      <dd className="flex items-center gap-1 text-[#16A34A]">
                        <ShieldCheck className="w-3.5 h-3.5" /> Chiffré
                      </dd>
                    </div>
                  </>
                ) : s.site_type === "vps_api" ? (
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
                {s.has_github_token && (
                  <div className="flex justify-between gap-2 pt-1.5 mt-1.5 border-t border-slate-100">
                    <dt className="text-slate-500 flex items-center gap-1"><Github className="w-3 h-3" /> GitHub</dt>
                    <dd className="font-mono text-emerald-700 truncate max-w-[220px]" title={`${s.github_owner}/${s.github_repo}@${s.github_branch}`}>
                      {s.github_owner}/{s.github_repo}
                    </dd>
                  </div>
                )}
              </dl>
            </div>
          ))}
        </div>
      )}

      {/* GitHub configuration dialog */}
      <Dialog open={!!ghSite} onOpenChange={(o) => !o && setGhSite(null)}>
        <DialogContent className="max-w-lg" data-testid="github-config-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Github className="w-5 h-5" /> Publication GitHub
              {ghSite && <span className="text-sm font-normal text-slate-500">— {ghSite.name}</span>}
            </DialogTitle>
            <DialogDescription>
              Vos articles seront commités directement dans votre repo GitHub. Vercel / Netlify redéploiera automatiquement le site avec la nouvelle page.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={saveGh} className="space-y-3.5">
            <div>
              <label className="text-xs font-medium text-slate-700 mb-1.5 block">
                Personal Access Token (PAT) {ghSite?.has_github_token && <span className="text-emerald-600">· déjà configuré</span>}
              </label>
              <input
                type="password"
                data-testid="github-token-input"
                value={ghForm.github_token}
                onChange={ghSet("github_token")}
                placeholder={ghSite?.has_github_token ? "Laissez vide pour conserver l'existant" : "ghp_xxxxxxxxxxxxxxxxxxxx"}
                className="w-full border border-slate-300 rounded-md px-3 py-2 bg-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7]"
              />
              <p className="text-[11px] text-slate-500 mt-1">
                <a href="https://github.com/settings/tokens?type=beta" target="_blank" rel="noreferrer" className="text-[#002FA7] hover:underline">
                  Créez un Fine-grained token →
                </a>{" "}
                avec permission <strong>Contents: Read &amp; write</strong> sur ce repo.
              </p>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-slate-700 mb-1.5 block">Owner *</label>
                <input
                  required
                  data-testid="github-owner-input"
                  value={ghForm.github_owner}
                  onChange={ghSet("github_owner")}
                  placeholder="mon-username"
                  className="w-full border border-slate-300 rounded-md px-3 py-2 bg-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7]"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-700 mb-1.5 block">Repo *</label>
                <input
                  required
                  data-testid="github-repo-input"
                  value={ghForm.github_repo}
                  onChange={ghSet("github_repo")}
                  placeholder="logirent-site"
                  className="w-full border border-slate-300 rounded-md px-3 py-2 bg-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7]"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-slate-700 mb-1.5 block">Branche</label>
                <input
                  data-testid="github-branch-input"
                  value={ghForm.github_branch}
                  onChange={ghSet("github_branch")}
                  placeholder="main"
                  className="w-full border border-slate-300 rounded-md px-3 py-2 bg-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7]"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-700 mb-1.5 block">Dossier cible</label>
                <input
                  data-testid="github-folder-input"
                  value={ghForm.github_folder}
                  onChange={ghSet("github_folder")}
                  placeholder="public/blog"
                  className="w-full border border-slate-300 rounded-md px-3 py-2 bg-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7]"
                />
                <p className="text-[10px] text-slate-500 mt-1">Vite/CRA : <code>public/blog</code> · Next.js : <code>public/blog</code></p>
              </div>
            </div>
            <div>
              <label className="text-xs font-medium text-slate-700 mb-1.5 block">URL publique du dossier</label>
              <input
                data-testid="github-public-url-input"
                value={ghForm.github_public_url}
                onChange={ghSet("github_public_url")}
                placeholder="https://www.logirent.ch/blog"
                className="w-full border border-slate-300 rounded-md px-3 py-2 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7]"
              />
              <p className="text-[10px] text-slate-500 mt-1">Sert à générer le lien canonical et l&apos;URL finale de chaque article.</p>
            </div>

            {ghTestResult && !ghTestResult.error && (
              <div className="bg-emerald-50 border border-emerald-200 rounded-md p-3 text-xs" data-testid="github-test-success">
                <div className="flex items-center gap-2 font-medium text-emerald-900">
                  <CheckCircle2 className="w-4 h-4" /> Connexion réussie · dernier commit {ghTestResult.commit_sha}
                </div>
                {ghTestResult.listing?.length > 0 && (
                  <div className="mt-2 text-emerald-800">
                    <div className="font-medium mb-1">Contenu actuel de <code>{ghTestResult.folder}</code> :</div>
                    <div className="font-mono text-[10px] max-h-24 overflow-auto">
                      {ghTestResult.listing.map((i) => (
                        <div key={i.name}>{i.type === "dir" ? "📁" : "📄"} {i.name}</div>
                      ))}
                    </div>
                  </div>
                )}
                {ghTestResult.listing?.length === 0 && (
                  <div className="mt-1 text-emerald-700">Dossier vide ou inexistant — sera créé au premier commit.</div>
                )}
              </div>
            )}
            {ghTestResult?.error && (
              <div className="bg-red-50 border border-red-200 rounded-md p-3 text-xs text-red-800" data-testid="github-test-error">
                ❌ {ghTestResult.error}
              </div>
            )}

            <DialogFooter className="pt-2 gap-2">
              <button
                type="button"
                onClick={testGh}
                disabled={ghTesting}
                data-testid="github-test-button"
                className="inline-flex items-center gap-2 px-4 py-2 text-sm text-slate-700 border border-slate-300 rounded-md hover:bg-slate-50 disabled:opacity-60"
              >
                {ghTesting ? <Loader2 className="w-4 h-4 animate-spin" /> : <ShieldCheck className="w-4 h-4" />}
                Tester la connexion
              </button>
              <button
                type="submit"
                disabled={ghSaving}
                data-testid="github-save-button"
                className="px-4 py-2 bg-[#002FA7] hover:bg-[#001D6B] text-white text-sm font-medium rounded-md disabled:opacity-60"
              >
                {ghSaving ? "Enregistrement…" : "Enregistrer"}
              </button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
