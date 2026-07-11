import { useEffect, useState, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "@/lib/api";
import PageHeader from "@/components/PageHeader";
import { toast } from "sonner";
import { CheckCircle2, Loader2, Zap, Rocket, Building2, Crown } from "lucide-react";

const ICONS = { free: Zap, pro: Rocket, business: Building2, agency: Crown };
const COLORS = {
  free: { bg: "bg-slate-50", border: "border-slate-200", text: "text-slate-700" },
  pro: { bg: "bg-[#002FA7]/5", border: "border-[#002FA7]", text: "text-[#002FA7]" },
  business: { bg: "bg-emerald-50", border: "border-emerald-500", text: "text-emerald-700" },
  agency: { bg: "bg-amber-50", border: "border-amber-500", text: "text-amber-700" },
};

export default function Billing() {
  const [workspace, setWorkspace] = useState(null);
  const [plans, setPlans] = useState({});
  const [checkingOut, setCheckingOut] = useState(null);
  const [searchParams, setSearchParams] = useSearchParams();

  const load = useCallback(async () => {
    const [{ data: ws }, { data: p }] = await Promise.all([
      api.get("/workspace"),
      api.get("/billing/plans"),
    ]);
    setWorkspace(ws);
    setPlans(p);
  }, []);

  useEffect(() => { load(); }, [load]);

  // Handle Stripe return
  useEffect(() => {
    const sid = searchParams.get("session_id");
    const canceled = searchParams.get("canceled");
    if (canceled) {
      toast.info("Paiement annulé");
      searchParams.delete("canceled");
      setSearchParams(searchParams, { replace: true });
      return;
    }
    if (!sid) return;
    let attempts = 0;
    const poll = async () => {
      if (attempts >= 15) {
        toast.warning("Vérification du paiement trop longue. Rafraîchissez la page dans quelques minutes.");
        return;
      }
      attempts++;
      try {
        const { data } = await api.get(`/billing/checkout/status/${sid}`);
        if (data.payment_status === "paid") {
          toast.success(`Paiement réussi ! Plan ${data.plan_id?.toUpperCase()} activé ✨`);
          searchParams.delete("session_id");
          setSearchParams(searchParams, { replace: true });
          load();
          return;
        }
        if (data.payment_status === "expired" || data.status === "expired") {
          toast.error("Session de paiement expirée");
          return;
        }
        setTimeout(poll, 2000);
      } catch {
        setTimeout(poll, 3000);
      }
    };
    poll();
  }, [searchParams, setSearchParams, load]);

  const upgrade = async (planId) => {
    setCheckingOut(planId);
    try {
      const { data } = await api.post("/billing/checkout", {
        plan_id: planId,
        origin_url: window.location.origin,
      });
      window.location.href = data.url;
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Échec");
      setCheckingOut(null);
    }
  };

  if (!workspace) return <div className="p-8"><Loader2 className="w-6 h-6 animate-spin text-slate-400" /></div>;

  const currentPlan = workspace.plan;
  const usage = workspace.usage;
  const usagePct = Math.min(100, Math.round((usage.articles_this_month / usage.articles_limit) * 100));

  return (
    <div className="p-6 md:p-8 max-w-7xl">
      <PageHeader
        overline="Facturation"
        title="Choisissez votre plan"
        description="Développez votre stratégie SEO au rythme de votre entreprise. Changez de plan à tout moment."
      />

      <div className="mb-8 p-5 border border-slate-200 bg-white rounded-md" data-testid="current-plan-card">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <div className="overline text-slate-500 mb-1">Plan actuel</div>
            <div className="flex items-center gap-2">
              <div className="font-display text-2xl font-semibold text-slate-950">{workspace.plan_details.name}</div>
              <span className="text-xs px-2 py-0.5 bg-[#002FA7]/10 text-[#002FA7] rounded-full font-medium">Actif</span>
            </div>
            {workspace.plan_expires_at && <div className="text-xs text-slate-500 mt-1">Renouvellement le {new Date(workspace.plan_expires_at).toLocaleDateString("fr-FR")}</div>}
          </div>
          <div className="flex-1 max-w-md">
            <div className="flex justify-between text-xs text-slate-600 mb-1.5">
              <span>Articles ce mois-ci</span>
              <span className="font-mono">{usage.articles_this_month} / {usage.articles_limit}</span>
            </div>
            <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
              <div className={`h-full transition-all ${usagePct > 80 ? "bg-red-500" : usagePct > 60 ? "bg-amber-500" : "bg-[#002FA7]"}`} style={{ width: `${usagePct}%` }} />
            </div>
            <div className="text-xs text-slate-500 mt-1">{usage.articles_remaining} article(s) restant(s)</div>
          </div>
        </div>
      </div>

      <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
        {["free", "pro", "business", "agency"].map((planId) => {
          const p = plans[planId];
          if (!p) return null;
          const Icon = ICONS[planId];
          const clr = COLORS[planId];
          const isCurrent = currentPlan === planId;
          const isDowngrade = ["free", "pro", "business", "agency"].indexOf(planId) < ["free", "pro", "business", "agency"].indexOf(currentPlan);
          return (
            <div key={planId} className={`p-5 border-2 rounded-lg ${clr.bg} ${clr.border} flex flex-col`} data-testid={`plan-card-${planId}`}>
              <div className="flex items-center gap-2 mb-3">
                <Icon className={`w-5 h-5 ${clr.text}`} />
                <div className={`font-display font-semibold text-lg ${clr.text}`}>{p.name}</div>
              </div>
              <div className="mb-4">
                <div className="font-mono text-3xl font-bold text-slate-950">{p.price_eur}€</div>
                <div className="text-xs text-slate-500">/ mois</div>
              </div>
              <ul className="space-y-2 mb-6 flex-1">
                {p.features.map((f, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs text-slate-700">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 mt-0.5 flex-shrink-0" />
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
              {isCurrent ? (
                <button disabled className="w-full py-2 border border-slate-300 text-slate-500 rounded-md text-sm font-medium cursor-default" data-testid={`plan-current-${planId}`}>
                  Plan actuel
                </button>
              ) : planId === "free" ? (
                <button disabled className="w-full py-2 border border-slate-200 text-slate-400 rounded-md text-sm cursor-not-allowed" data-testid={`plan-downgrade-${planId}`}>
                  {isDowngrade ? "Contactez-nous pour rétrograder" : "Gratuit"}
                </button>
              ) : (
                <button
                  onClick={() => upgrade(planId)}
                  disabled={checkingOut === planId}
                  data-testid={`plan-upgrade-${planId}`}
                  className={`w-full py-2 rounded-md text-sm font-medium transition-colors ${
                    planId === "pro" ? "bg-[#002FA7] hover:bg-[#001D6B] text-white" :
                    planId === "business" ? "bg-emerald-600 hover:bg-emerald-700 text-white" :
                    "bg-amber-500 hover:bg-amber-600 text-white"
                  } disabled:opacity-60 inline-flex items-center justify-center gap-2`}
                >
                  {checkingOut === planId ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                  {isDowngrade ? "Rétrograder" : "Passer à " + p.name}
                </button>
              )}
            </div>
          );
        })}
      </div>

      <div className="mt-8 p-4 border border-blue-100 bg-blue-50 rounded-md text-sm text-slate-700">
        💳 Paiement sécurisé via Stripe · Mode test actif · Annulation possible à tout moment · Support 7j/7
      </div>
    </div>
  );
}
