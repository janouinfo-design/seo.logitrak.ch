import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { Sparkles } from "lucide-react";
import { toast } from "sonner";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await login(email, password);
      toast.success("Connexion réussie");
      navigate("/");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Échec de la connexion");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex bg-white">
      {/* Left: Form */}
      <div className="w-full md:w-1/2 flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">
          <div className="flex items-center gap-2.5 mb-12">
            <div className="w-10 h-10 rounded-md bg-[#002FA7] flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-white" strokeWidth={2.2} />
            </div>
            <div>
              <div className="font-display text-lg font-bold tracking-tight text-slate-950 leading-none">LOGI</div>
              <div className="font-display text-[11px] font-semibold tracking-[0.18em] text-slate-500 uppercase mt-0.5">SEO Booster</div>
            </div>
          </div>

          <div className="overline mb-2">Connexion</div>
          <h1 className="font-display text-3xl sm:text-4xl font-bold tracking-tight text-slate-950 mb-2">
            Bon retour.
          </h1>
          <p className="text-sm text-slate-600 mb-8">
            Accédez à vos audits SEO et à la génération IA pour Logirent et Logitime.
          </p>

          <form onSubmit={onSubmit} className="space-y-4" data-testid="login-form">
            <div>
              <label className="text-xs font-medium text-slate-700 mb-1.5 block">Email professionnel</label>
              <input
                data-testid="login-email-input"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full border border-slate-300 rounded-md px-3 py-2.5 bg-white text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7] transition-all"
                placeholder="vous@logirent.fr"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-700 mb-1.5 block">Mot de passe</label>
              <input
                data-testid="login-password-input"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full border border-slate-300 rounded-md px-3 py-2.5 bg-white text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7] transition-all"
                placeholder="••••••••"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              data-testid="login-submit-button"
              className="w-full bg-[#002FA7] hover:bg-[#001D6B] disabled:opacity-60 text-white rounded-md py-2.5 text-sm font-medium transition-colors shadow-sm"
            >
              {loading ? "Connexion…" : "Se connecter"}
            </button>
          </form>

          <p className="mt-6 text-sm text-slate-600">
            Pas encore de compte ?{" "}
            <Link to="/register" className="text-[#002FA7] font-medium hover:underline" data-testid="login-to-register-link">
              Créer un compte
            </Link>
          </p>
        </div>
      </div>

      {/* Right: visual */}
      <div className="hidden md:block w-1/2 relative overflow-hidden border-l border-slate-200">
        <img
          src="https://images.unsplash.com/photo-1637625854255-d893202554f4?crop=entropy&cs=srgb&fm=jpg&w=1600&q=80"
          alt="Background"
          className="absolute inset-0 w-full h-full object-cover"
        />
        <div className="absolute inset-0 bg-gradient-to-tr from-white/40 to-white/0" />
        <div className="absolute bottom-10 left-10 right-10">
          <div className="bg-white/95 backdrop-blur border border-slate-200 rounded-md p-6 shadow-sm max-w-md">
            <div className="overline mb-2">SEO B2B · Immobilier</div>
            <p className="font-display text-xl font-semibold tracking-tight text-slate-950 leading-snug">
              Une plateforme rigoureuse pour faire grimper Logirent et Logitime dans Google et les IA.
            </p>
            <div className="mt-4 grid grid-cols-3 gap-3 text-center">
              {[
                { k: "+340%", v: "Visibilité IA" },
                { k: "5×", v: "Pages produites" },
                { k: "−72%", v: "Erreurs SEO" },
              ].map((s) => (
                <div key={s.v} className="border border-slate-200 rounded-md py-2 px-1.5 bg-white">
                  <div className="font-mono text-base font-semibold text-[#002FA7]">{s.k}</div>
                  <div className="text-[10px] text-slate-500 uppercase tracking-wider mt-0.5">{s.v}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
