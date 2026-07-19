import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import PageHeader from "@/components/PageHeader";
import { toast } from "sonner";
import { Users, Mail, Copy, Trash2, Crown } from "lucide-react";

const ROLE_LABELS = { owner: "Propriétaire", admin: "Admin", editor: "Éditeur", viewer: "Lecteur" };
const ROLE_DESCRIPTIONS = {
  admin: "Tout, y compris la gestion de l'équipe et des sites",
  editor: "Génère et publie des articles (pas de gestion sites/facturation)",
  viewer: "Consultation seule",
};

function RoleBadge({ role }) {
  const colors = {
    owner: "bg-[#002FA7]/10 text-[#002FA7] border-[#002FA7]/20",
    admin: "bg-emerald-50 text-emerald-700 border-emerald-200",
    editor: "bg-amber-50 text-amber-700 border-amber-200",
    viewer: "bg-slate-100 text-slate-600 border-slate-200",
  };
  return (
    <span className={`inline-block text-[11px] font-medium px-2 py-0.5 rounded border ${colors[role] || colors.viewer}`}>
      {ROLE_LABELS[role] || role}
    </span>
  );
}

export default function Team() {
  const [data, setData] = useState(null);
  const [invites, setInvites] = useState([]);
  const [inviteForm, setInviteForm] = useState({ email: "", role: "editor" });
  const [inviting, setInviting] = useState(false);
  const [lastLink, setLastLink] = useState(null);

  const load = useCallback(async () => {
    try {
      const [m, i] = await Promise.all([api.get("/team/members"), api.get("/team/invites")]);
      setData(m.data);
      setInvites(i.data.invites || []);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Erreur de chargement");
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const sendInvite = async (e) => {
    e.preventDefault();
    setInviting(true);
    try {
      const { data: res } = await api.post("/team/invites", inviteForm);
      setLastLink({ email: inviteForm.email, link: res.invite_link, emailSent: res.email_sent });
      toast.success(res.email_sent ? "Invitation envoyée par email" : "Invitation créée — copiez le lien ci-dessous");
      setInviteForm({ email: "", role: "editor" });
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Échec de l'invitation");
    } finally {
      setInviting(false);
    }
  };

  const copyLink = async (link) => {
    try {
      await navigator.clipboard.writeText(link);
      toast.success("Lien copié !");
    } catch {
      toast.error("Impossible de copier — sélectionnez le lien manuellement");
    }
  };

  const copyInviteLink = async (inviteId) => {
    try {
      const { data: res } = await api.get(`/team/invites/${inviteId}/link`);
      await copyLink(res.invite_link);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Erreur");
    }
  };

  const revokeInvite = async (inviteId) => {
    try {
      await api.delete(`/team/invites/${inviteId}`);
      toast.success("Invitation révoquée");
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Erreur");
    }
  };

  const changeRole = async (memberId, role) => {
    try {
      await api.patch(`/team/members/${memberId}`, { role });
      toast.success("Rôle mis à jour");
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Erreur");
    }
  };

  const removeMember = async (memberId, email) => {
    if (!window.confirm(`Retirer ${email} de l'équipe ?`)) return;
    try {
      await api.delete(`/team/members/${memberId}`);
      toast.success("Membre retiré");
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Erreur");
    }
  };

  if (!data) return <div className="p-8 text-sm text-slate-500">Chargement…</div>;
  const canManage = data.can_manage;

  return (
    <div className="p-8 max-w-4xl" data-testid="team-page">
      <PageHeader
        overline="Espace de travail"
        title="Équipe"
        description={`Invitez des collaborateurs dans « ${data.workspace.name} » et gérez leurs rôles.`}
      />

      {canManage && (
        <div className="bg-white border border-slate-200 rounded-lg p-5 mb-6">
          <div className="text-sm font-semibold text-slate-900 mb-3 flex items-center gap-2">
            <Mail className="w-4 h-4 text-[#002FA7]" /> Inviter un collaborateur
          </div>
          <form onSubmit={sendInvite} className="flex flex-col sm:flex-row gap-3" data-testid="invite-form">
            <input
              type="email"
              required
              value={inviteForm.email}
              onChange={(e) => setInviteForm((f) => ({ ...f, email: e.target.value }))}
              placeholder="collaborateur@exemple.ch"
              data-testid="invite-email-input"
              className="flex-1 border border-slate-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7]"
            />
            <select
              value={inviteForm.role}
              onChange={(e) => setInviteForm((f) => ({ ...f, role: e.target.value }))}
              data-testid="invite-role-select"
              className="border border-slate-300 rounded-md px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30"
            >
              <option value="admin">Admin</option>
              <option value="editor">Éditeur</option>
              <option value="viewer">Lecteur</option>
            </select>
            <button
              type="submit"
              disabled={inviting}
              data-testid="invite-submit-button"
              className="bg-[#002FA7] hover:bg-[#001D6B] disabled:opacity-60 text-white rounded-md px-5 py-2 text-sm font-medium transition-colors"
            >
              {inviting ? "Envoi…" : "Inviter"}
            </button>
          </form>
          <p className="text-xs text-slate-500 mt-2">{ROLE_DESCRIPTIONS[inviteForm.role]}</p>

          {lastLink && (
            <div className="mt-4 rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3" data-testid="invite-link-box">
              <div className="text-xs font-medium text-emerald-800 mb-1.5">
                Lien d'invitation pour {lastLink.email}
                {!lastLink.emailSent && " — transmettez-le lui directement :"}
              </div>
              <div className="flex items-center gap-2">
                <code className="flex-1 text-[11px] text-slate-700 bg-white border border-slate-200 rounded px-2 py-1.5 truncate">
                  {lastLink.link}
                </code>
                <button
                  onClick={() => copyLink(lastLink.link)}
                  data-testid="copy-invite-link-button"
                  className="flex items-center gap-1 text-xs font-medium text-[#002FA7] hover:underline flex-shrink-0"
                >
                  <Copy className="w-3.5 h-3.5" /> Copier
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden mb-6">
        <div className="px-5 py-3 border-b border-slate-200 text-sm font-semibold text-slate-900 flex items-center gap-2">
          <Users className="w-4 h-4 text-[#002FA7]" /> Membres ({1 + data.members.length})
        </div>
        <table className="w-full text-sm">
          <tbody>
            <tr className="border-b border-slate-100" data-testid="member-row-owner">
              <td className="px-5 py-3">
                <div className="font-medium text-slate-900 flex items-center gap-1.5">
                  <Crown className="w-3.5 h-3.5 text-amber-500" /> {data.owner.full_name}
                </div>
                <div className="text-xs text-slate-500">{data.owner.email}</div>
              </td>
              <td className="px-5 py-3 text-right"><RoleBadge role="owner" /></td>
              <td className="px-5 py-3 w-10"></td>
            </tr>
            {data.members.map((m) => (
              <tr key={m.id} className="border-b border-slate-100 last:border-0" data-testid={`member-row-${m.email}`}>
                <td className="px-5 py-3">
                  <div className="font-medium text-slate-900">{m.full_name || "—"}</div>
                  <div className="text-xs text-slate-500">{m.email}</div>
                </td>
                <td className="px-5 py-3 text-right">
                  {canManage ? (
                    <select
                      value={m.role}
                      onChange={(e) => changeRole(m.id, e.target.value)}
                      data-testid={`member-role-select-${m.email}`}
                      className="border border-slate-300 rounded-md px-2 py-1 text-xs bg-white"
                    >
                      <option value="admin">Admin</option>
                      <option value="editor">Éditeur</option>
                      <option value="viewer">Lecteur</option>
                    </select>
                  ) : (
                    <RoleBadge role={m.role} />
                  )}
                </td>
                <td className="px-5 py-3 w-10 text-right">
                  {canManage && (
                    <button
                      onClick={() => removeMember(m.id, m.email)}
                      data-testid={`member-remove-${m.email}`}
                      className="text-slate-400 hover:text-red-600 transition-colors"
                      title="Retirer"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {data.members.length === 0 && (
              <tr>
                <td colSpan={3} className="px-5 py-6 text-center text-sm text-slate-500">
                  Aucun collaborateur pour le moment. Envoyez une invitation ci-dessus.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {invites.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-lg overflow-hidden" data-testid="pending-invites">
          <div className="px-5 py-3 border-b border-slate-200 text-sm font-semibold text-slate-900">
            Invitations en attente ({invites.length})
          </div>
          <table className="w-full text-sm">
            <tbody>
              {invites.map((inv) => (
                <tr key={inv.id} className="border-b border-slate-100 last:border-0" data-testid={`invite-row-${inv.email}`}>
                  <td className="px-5 py-3">
                    <div className="font-medium text-slate-900">{inv.email}</div>
                    <div className="text-xs text-slate-500">Invité le {new Date(inv.created_at).toLocaleDateString("fr-FR")}</div>
                  </td>
                  <td className="px-5 py-3 text-right"><RoleBadge role={inv.role} /></td>
                  <td className="px-5 py-3 w-24 text-right">
                    {canManage && (
                      <div className="flex items-center justify-end gap-3">
                        <button
                          onClick={() => copyInviteLink(inv.id)}
                          data-testid={`invite-copy-${inv.email}`}
                          className="text-slate-400 hover:text-[#002FA7] transition-colors"
                          title="Copier le lien"
                        >
                          <Copy className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => revokeInvite(inv.id)}
                          data-testid={`invite-revoke-${inv.email}`}
                          className="text-slate-400 hover:text-red-600 transition-colors"
                          title="Révoquer"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
