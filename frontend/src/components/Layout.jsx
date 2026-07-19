import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useState, useEffect } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useSites } from "@/contexts/SiteContext";
import { api } from "@/lib/api";
import {
  LayoutDashboard,
  Globe,
  Search,
  Sparkles,
  FileText,
  History,
  LineChart,
  Rocket,
  CreditCard,
  LogOut,
  ChevronsUpDown,
  Check,
  Plus,
  KeyRound,
  Wand2,
  BookOpen,
  Radar,
  BrainCircuit,
  HelpCircle,
  Building2,
  Swords,
  Zap,
  Users,
  ShieldCheck,
  Briefcase,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
  DropdownMenuLabel,
} from "@/components/ui/dropdown-menu";

const navGroups = [
  {
    title: null,
    items: [
      { to: "/", icon: LayoutDashboard, label: "Dashboard", end: true, testid: "nav-dashboard" },
      { to: "/sites", icon: Globe, label: "Sites", testid: "nav-sites" },
    ],
  },
  {
    title: "Analyses",
    items: [
      { to: "/audit", icon: Search, label: "Audit SEO", testid: "nav-audit" },
      { to: "/ai-visibility", icon: Radar, label: "AI Visibility", testid: "nav-ai-visibility" },
      { to: "/business", icon: Building2, label: "Business Analyzer", testid: "nav-business" },
      { to: "/competitors", icon: Swords, label: "Concurrents", testid: "nav-competitors" },
      { to: "/keywords", icon: KeyRound, label: "Mots-clés", testid: "nav-keywords" },
      { to: "/keyword-intelligence", icon: BrainCircuit, label: "Keyword Intelligence", testid: "nav-keyword-intelligence" },
      { to: "/performance", icon: LineChart, label: "Performance", testid: "nav-performance" },
    ],
  },
  {
    title: "Actions",
    items: [
      { to: "/generator", icon: Sparkles, label: "Générateur IA", testid: "nav-generator" },
      { to: "/optimizer", icon: Wand2, label: "Optimiseur de pages", testid: "nav-optimizer" },
      { to: "/automation", icon: Rocket, label: "Automatisation", testid: "nav-automation" },
      { to: "/workflows", icon: Zap, label: "Workflows", testid: "nav-workflows" },
      { to: "/drafts", icon: FileText, label: "Brouillons", testid: "nav-drafts" },
      { to: "/history", icon: History, label: "Historique", testid: "nav-history" },
    ],
  },
];

function buildNavGroups(user) {
  const role = user?.workspace_role;
  const restricted = role === "editor" || role === "viewer";
  const compte = [];
  if (!restricted) {
    compte.push({ to: "/billing", icon: CreditCard, label: "Facturation", testid: "nav-billing" });
    compte.push({ to: "/team", icon: Users, label: "Équipe", testid: "nav-team" });
  }
  compte.push({ to: "/aide", icon: HelpCircle, label: "Aide", testid: "nav-aide" });
  if (user?.is_admin) {
    compte.push({ to: "/admin", icon: ShieldCheck, label: "Admin", testid: "nav-admin" });
  }
  return [...navGroups, { title: "Compte", items: compte }];
}

const WS_ROLE_LABELS = { owner: "Propriétaire", admin: "Admin", editor: "Éditeur", viewer: "Lecteur" };

function WorkspaceSwitcher() {
  const [memberships, setMemberships] = useState([]);

  useEffect(() => {
    api.get("/workspace/memberships")
      .then(({ data }) => setMemberships(data.memberships || []))
      .catch(() => {});
  }, []);

  if (memberships.length < 2) return null;
  const active = memberships.find((m) => m.active) || memberships[0];

  const switchTo = async (m) => {
    if (m.active) return;
    try {
      await api.post("/workspace/switch", { workspace_id: m.workspace_id });
      window.location.reload();
    } catch (e) {
      /* toast handled by interceptor */
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className="mt-2 w-full flex items-center justify-between gap-2 px-3 py-2 rounded-md border border-slate-200 bg-slate-50 hover:border-slate-300 transition-colors"
        data-testid="workspace-switcher-trigger"
      >
        <div className="flex items-center gap-2 min-w-0">
          <Briefcase className="w-4 h-4 text-[#002FA7] flex-shrink-0" />
          <div className="text-left min-w-0">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Espace de travail</div>
            <div className="text-xs font-medium text-slate-900 truncate">{active.name}</div>
          </div>
        </div>
        <ChevronsUpDown className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-[260px]">
        <DropdownMenuLabel className="text-xs uppercase tracking-wider text-slate-500">Vos espaces</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {memberships.map((m) => (
          <DropdownMenuItem
            key={m.workspace_id}
            onClick={() => switchTo(m)}
            className="flex items-center justify-between cursor-pointer"
            data-testid={`workspace-option-${m.workspace_id}`}
          >
            <div>
              <div className="text-sm font-medium">{m.name}</div>
              <div className="text-[10px] text-slate-500">{WS_ROLE_LABELS[m.role] || m.role}</div>
            </div>
            {m.active && <Check className="w-4 h-4 text-[#002FA7]" />}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function SiteSwitcher() {
  const { sites, activeSite, selectSite } = useSites();
  const navigate = useNavigate();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className="w-full flex items-center justify-between gap-2 px-3 py-2.5 rounded-md border border-slate-200 bg-white hover:border-slate-300 transition-colors"
        data-testid="site-switcher-trigger"
      >
        <div className="flex items-center gap-2.5 min-w-0">
          <div
            className="w-8 h-8 rounded flex items-center justify-center text-white text-xs font-bold flex-shrink-0"
            style={{ background: activeSite?.label === "Logitime" ? "#0F766E" : "#002FA7" }}
          >
            {activeSite ? activeSite.label.slice(0, 2).toUpperCase() : "—"}
          </div>
          <div className="text-left min-w-0">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Site actif</div>
            <div className="text-sm font-medium text-slate-900 truncate">{activeSite?.name || "Aucun site"}</div>
          </div>
        </div>
        <ChevronsUpDown className="w-4 h-4 text-slate-400 flex-shrink-0" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-[260px]">
        <DropdownMenuLabel className="text-xs uppercase tracking-wider text-slate-500">Vos sites Wix</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {sites.length === 0 && (
          <div className="px-3 py-3 text-sm text-slate-500">Aucun site connecté.</div>
        )}
        {sites.map((s) => (
          <DropdownMenuItem
            key={s.id}
            onClick={() => selectSite(s.id)}
            className="flex items-center justify-between cursor-pointer"
            data-testid={`site-option-${s.id}`}
          >
            <div className="flex items-center gap-2">
              <div
                className="w-6 h-6 rounded flex items-center justify-center text-white text-[10px] font-bold"
                style={{ background: s.label === "Logitime" ? "#0F766E" : "#002FA7" }}
              >
                {s.label.slice(0, 2).toUpperCase()}
              </div>
              <div>
                <div className="text-sm font-medium">{s.name}</div>
                <div className="text-[10px] text-slate-500">{s.label}</div>
              </div>
            </div>
            {activeSite?.id === s.id && <Check className="w-4 h-4 text-[#002FA7]" />}
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={() => navigate("/sites")} className="cursor-pointer" data-testid="site-add-new">
          <Plus className="w-4 h-4 mr-2" />
          Ajouter un site Wix
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export default function Layout() {
  const { user, logout } = useAuth();
  const groups = buildNavGroups(user);

  return (
    <div className="min-h-screen flex bg-[#FAFAFA]">
      {/* Sidebar */}
      <aside className="w-64 border-r border-slate-200 bg-white flex flex-col flex-shrink-0">
        <div className="px-5 py-5 border-b border-slate-200">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-md bg-[#002FA7] flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-white" strokeWidth={2.2} />
            </div>
            <div>
              <div className="font-display text-base font-bold tracking-tight text-slate-950 leading-none">LOGI</div>
              <div className="font-display text-[11px] font-semibold tracking-[0.18em] text-slate-500 uppercase mt-0.5">SEO Booster</div>
            </div>
          </div>
        </div>

        <div className="p-3 border-b border-slate-200">
          <SiteSwitcher />
          <WorkspaceSwitcher />
        </div>

        <nav className="flex-1 p-3 overflow-y-auto">
          {groups.map((group, gi) => (
            <div key={gi} className={gi > 0 ? "mt-3" : ""}>
              {group.title && (
                <div className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                  {group.title}
                </div>
              )}
              <div className="space-y-0.5">
                {group.items.map((item) => {
                  const Icon = item.icon;
                  return (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      end={item.end}
                      data-testid={item.testid}
                      className={({ isActive }) =>
                        `flex items-center gap-3 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                          isActive
                            ? "bg-slate-100 text-slate-950"
                            : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                        }`
                      }
                    >
                      <Icon className="w-[18px] h-[18px]" strokeWidth={1.8} />
                      {item.label}
                    </NavLink>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        <div className="p-3 border-t border-slate-200">
          <a
            href="/guide-logi-seo-booster.pdf"
            target="_blank"
            rel="noopener noreferrer"
            data-testid="sidebar-guide-pdf"
            className="flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium text-slate-600 hover:bg-slate-50 hover:text-slate-900 transition-colors mb-1"
          >
            <BookOpen className="w-[18px] h-[18px]" strokeWidth={1.8} />
            Guide PDF
          </a>
          <div className="px-3 py-2 mb-1">
            <div className="text-xs font-medium text-slate-900 truncate">{user?.full_name}</div>
            <div className="text-[11px] text-slate-500 truncate">{user?.email}</div>
            {user?.workspace_role && (
              <div
                className="mt-1 text-[10px] font-medium text-[#002FA7] bg-[#002FA7]/5 border border-[#002FA7]/15 rounded px-1.5 py-0.5 inline-block truncate max-w-full"
                data-testid="acting-role-badge"
              >
                {user.acting_workspace_name} · {WS_ROLE_LABELS[user.workspace_role] || user.workspace_role}
              </div>
            )}
          </div>
          <button
            onClick={logout}
            data-testid="logout-button"
            className="w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm text-slate-600 hover:bg-slate-50 hover:text-slate-900 transition-colors"
          >
            <LogOut className="w-4 h-4" />
            Déconnexion
          </button>
        </div>
      </aside>

      <main className="flex-1 min-w-0">
        <Outlet />
      </main>
    </div>
  );
}
