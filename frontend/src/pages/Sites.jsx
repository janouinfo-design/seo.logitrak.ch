import { useState } from "react";
import { api } from "@/lib/api";
import { useSites } from "@/contexts/SiteContext";
import PageHeader from "@/components/PageHeader";
import { Plus, Trash2, ShieldCheck, KeyRound } from "lucide-react";
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
  label: "Logirent",
  name: "",
  wix_site_id: "",
  wix_account_id: "",
  wix_api_key: "",
  base_url: "",
};

export default function Sites() {
  const { sites, refresh, selectSite } = useSites();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(empty);
  const [saving, setSaving] = useState(false);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e?.target ? e.target.value : e }));

  const onSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const { data } = await api.post("/sites", form);
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

  return (
    <div className="p-6 md:p-8 max-w-6xl">
      <PageHeader
        overline="Connexions"
        title="Sites Wix"
        description="Reliez Logirent et Logitime via leurs clés API Wix. Les clés sont stockées de manière chiffrée et utilisées uniquement côté serveur."
        action={
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
                <DialogTitle>Connecter un site Wix</DialogTitle>
                <DialogDescription>
                  Générez une clé API depuis Wix → Settings → Headless Settings → API keys. Donnez-lui les permissions Blog & Site Pages.
                </DialogDescription>
              </DialogHeader>
              <form onSubmit={onSubmit} className="space-y-3.5" data-testid="add-site-form">
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
                    placeholder="Logirent Paris"
                    className="w-full border border-slate-300 rounded-md px-3 py-2 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7]"
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-medium text-slate-700 mb-1.5 block">Wix Site ID</label>
                    <input
                      required
                      data-testid="site-wix-site-id-input"
                      value={form.wix_site_id}
                      onChange={set("wix_site_id")}
                      placeholder="abc-123-…"
                      className="w-full border border-slate-300 rounded-md px-3 py-2 bg-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7]"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-slate-700 mb-1.5 block">Wix Account ID</label>
                    <input
                      required
                      data-testid="site-wix-account-id-input"
                      value={form.wix_account_id}
                      onChange={set("wix_account_id")}
                      placeholder="xyz-456-…"
                      className="w-full border border-slate-300 rounded-md px-3 py-2 bg-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7]"
                    />
                  </div>
                </div>
                <div>
                  <label className="text-xs font-medium text-slate-700 mb-1.5 block">Wix API Key</label>
                  <input
                    required
                    data-testid="site-wix-api-key-input"
                    value={form.wix_api_key}
                    onChange={set("wix_api_key")}
                    type="password"
                    placeholder="IST.eyJraWQiOi…"
                    className="w-full border border-slate-300 rounded-md px-3 py-2 bg-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7]"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-slate-700 mb-1.5 block">URL du site (optionnel)</label>
                  <input
                    data-testid="site-base-url-input"
                    value={form.base_url}
                    onChange={set("base_url")}
                    placeholder="https://www.logirent.fr"
                    className="w-full border border-slate-300 rounded-md px-3 py-2 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7]"
                  />
                </div>
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
        }
      />

      {sites.length === 0 ? (
        <div className="border border-dashed border-slate-300 bg-white rounded-md p-10 text-center" data-testid="sites-empty">
          <KeyRound className="w-8 h-8 text-slate-400 mx-auto mb-3" />
          <p className="text-sm text-slate-600">Aucun site Wix connecté pour le moment.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4" data-testid="sites-list">
          {sites.map((s) => (
            <div key={s.id} className="border border-slate-200 bg-white rounded-md p-5" data-testid={`site-card-${s.id}`}>
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div
                    className="w-11 h-11 rounded-md flex items-center justify-center text-white font-bold"
                    style={{ background: s.label === "Logitime" ? "#0F766E" : "#002FA7" }}
                  >
                    {s.label.slice(0, 2).toUpperCase()}
                  </div>
                  <div>
                    <div className="font-display font-semibold text-slate-950">{s.name}</div>
                    <div className="text-xs text-slate-500">{s.label}</div>
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
                        La connexion Wix sera retirée. Les brouillons et audits existants seront conservés mais ne pourront plus être publiés sur ce site.
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
              </dl>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
