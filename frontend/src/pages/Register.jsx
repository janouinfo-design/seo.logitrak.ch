import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { Sparkles } from "lucide-react";
import { toast } from "sonner";

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ full_name: "", email: "", password: "" });
  const [loading, setLoading] = useState(false);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const onSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await register(form.email, form.password, form.full_name);
      toast.success("Compte créé");
      navigate("/sites");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Échec de l'inscription");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex bg-white">
      <div className="w-full md:w-1/2 flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">
          <div className="flex items-center gap-2.5 mb-10">
            <div className="w-10 h-10 rounded-md bg-[#002FA7] flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-white" strokeWidth={2.2} />
            </div>
            <div>
              <div className="font-display text-lg font-bold tracking-tight text-slate-950 leading-none">LOGI</div>
              <div className="font-display text-[11px] font-semibold tracking-[0.18em] text-slate-500 uppercase mt-0.5">SEO Booster</div>
            </div>
          </div>

          <div className="overline mb-2">Inscription</div>
          <h1 className="font-display text-3xl sm:text-4xl font-bold tracking-tight text-slate-950 mb-2">
            Créez votre compte.
          </h1>
          <p className="text-sm text-slate-600 mb-8">
            Connectez Logirent ou Logitime en moins de 2 minutes.
          </p>

          <form onSubmit={onSubmit} className="space-y-4" data-testid="register-form">
            <div>
              <label className="text-xs font-medium text-slate-700 mb-1.5 block">Nom complet</label>
              <input
                data-testid="register-name-input"
                required
                value={form.full_name}
                onChange={set("full_name")}
                className="w-full border border-slate-300 rounded-md px-3 py-2.5 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7]"
                placeholder="Jean Dupont"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-700 mb-1.5 block">Email professionnel</label>
              <input
                data-testid="register-email-input"
                type="email"
                required
                value={form.email}
                onChange={set("email")}
                className="w-full border border-slate-300 rounded-md px-3 py-2.5 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7]"
                placeholder="vous@logirent.fr"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-700 mb-1.5 block">Mot de passe (min. 6)</label>
              <input
                data-testid="register-password-input"
                type="password"
                required
                minLength={6}
                value={form.password}
                onChange={set("password")}
                className="w-full border border-slate-300 rounded-md px-3 py-2.5 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7]"
                placeholder="••••••••"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              data-testid="register-submit-button"
              className="w-full bg-[#002FA7] hover:bg-[#001D6B] disabled:opacity-60 text-white rounded-md py-2.5 text-sm font-medium transition-colors shadow-sm"
            >
              {loading ? "Création…" : "Créer mon compte"}
            </button>
          </form>

          <p className="mt-6 text-sm text-slate-600">
            Déjà inscrit ?{" "}
            <Link to="/login" className="text-[#002FA7] font-medium hover:underline" data-testid="register-to-login-link">
              Se connecter
            </Link>
          </p>
        </div>
      </div>

      <div className="hidden md:block w-1/2 relative overflow-hidden border-l border-slate-200">
        <img
          src="https://images.unsplash.com/photo-1637625854255-d893202554f4?crop=entropy&cs=srgb&fm=jpg&w=1600&q=80"
          alt=""
          className="absolute inset-0 w-full h-full object-cover"
        />
        <div className="absolute inset-0 bg-gradient-to-tr from-white/40 to-white/0" />
      </div>
    </div>
  );
}
