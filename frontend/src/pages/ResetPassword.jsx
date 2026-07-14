import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import axios from "axios";
import { Sparkles, Eye, EyeOff } from "lucide-react";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function ResetPassword() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get("token") || "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    if (password !== confirm) return toast.error("Les deux mots de passe ne correspondent pas");
    if (password.length < 8) return toast.error("Le mot de passe doit contenir au moins 8 caractères");
    setLoading(true);
    try {
      await axios.post(`${API}/auth/reset-password`, { token, new_password: password });
      toast.success("Mot de passe mis à jour ✓ Connectez-vous.");
      navigate("/login");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Lien invalide ou expiré");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-white px-6">
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

        <div className="overline mb-2">Nouveau mot de passe</div>
        <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight text-slate-950 mb-2">
          Choisissez un mot de passe
        </h1>
        <p className="text-sm text-slate-600 mb-8">Minimum 8 caractères.</p>

        {!token ? (
          <div className="border border-amber-200 bg-amber-50 rounded-md p-4 text-sm text-amber-800" data-testid="reset-missing-token">
            Lien invalide : le jeton de réinitialisation est manquant.{" "}
            <Link to="/forgot-password" className="font-medium underline">Refaire une demande</Link>
          </div>
        ) : (
          <form onSubmit={onSubmit} className="space-y-4" data-testid="reset-password-form">
            <div>
              <label htmlFor="new-password" className="text-xs font-medium text-slate-700 mb-1.5 block">Nouveau mot de passe</label>
              <div className="relative">
                <input
                  data-testid="reset-password-input"
                  id="new-password"
                  name="new-password"
                  type={showPw ? "text" : "password"}
                  autoComplete="new-password"
                  required
                  minLength={8}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full border border-slate-300 rounded-md px-3 py-2.5 pr-10 bg-white text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7] transition-all"
                  placeholder="••••••••"
                />
                <button
                  type="button"
                  tabIndex={-1}
                  onClick={() => setShowPw((v) => !v)}
                  data-testid="reset-toggle-password-visibility"
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
                >
                  {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>
            <div>
              <label htmlFor="confirm-password" className="text-xs font-medium text-slate-700 mb-1.5 block">Confirmez le mot de passe</label>
              <input
                data-testid="reset-confirm-input"
                id="confirm-password"
                name="confirm-password"
                type={showPw ? "text" : "password"}
                autoComplete="new-password"
                required
                minLength={8}
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                className="w-full border border-slate-300 rounded-md px-3 py-2.5 bg-white text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7] transition-all"
                placeholder="••••••••"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              data-testid="reset-submit-button"
              className="w-full bg-[#002FA7] hover:bg-[#001D6B] disabled:opacity-60 text-white rounded-md py-2.5 text-sm font-medium transition-colors shadow-sm"
            >
              {loading ? "Mise à jour…" : "Mettre à jour le mot de passe"}
            </button>
          </form>
        )}

        <p className="mt-6 text-sm text-slate-600">
          <Link to="/login" className="text-[#002FA7] font-medium hover:underline" data-testid="reset-to-login-link">
            Retour à la connexion
          </Link>
        </p>
      </div>
    </div>
  );
}
