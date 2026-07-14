import { useState } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import { Sparkles, MailCheck, ArrowLeft } from "lucide-react";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await axios.post(`${API}/auth/forgot-password`, { email });
      setSent(true);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Une erreur est survenue, réessayez.");
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

        {sent ? (
          <div data-testid="forgot-password-success">
            <div className="w-12 h-12 rounded-md bg-green-50 flex items-center justify-center mb-4">
              <MailCheck className="w-6 h-6 text-green-600" />
            </div>
            <h1 className="font-display text-2xl font-bold tracking-tight text-slate-950 mb-2">Demande envoyée</h1>
            <p className="text-sm text-slate-600 mb-6">
              Si un compte existe avec <span className="font-medium text-slate-900">{email}</span>, un lien de
              réinitialisation (valable 1 heure) a été envoyé. Vérifiez aussi vos spams.
            </p>
            <Link to="/login" className="inline-flex items-center gap-1.5 text-sm text-[#002FA7] font-medium hover:underline" data-testid="forgot-back-to-login">
              <ArrowLeft className="w-4 h-4" /> Retour à la connexion
            </Link>
          </div>
        ) : (
          <>
            <div className="overline mb-2">Mot de passe oublié</div>
            <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight text-slate-950 mb-2">
              Réinitialisation
            </h1>
            <p className="text-sm text-slate-600 mb-8">
              Entrez votre email : nous vous enverrons un lien pour choisir un nouveau mot de passe.
            </p>
            <form onSubmit={onSubmit} className="space-y-4" data-testid="forgot-password-form">
              <div>
                <label htmlFor="email" className="text-xs font-medium text-slate-700 mb-1.5 block">Email</label>
                <input
                  data-testid="forgot-email-input"
                  id="email"
                  name="email"
                  type="email"
                  autoComplete="username email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full border border-slate-300 rounded-md px-3 py-2.5 bg-white text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-[#002FA7]/30 focus:border-[#002FA7] transition-all"
                  placeholder="vous@logirent.fr"
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                data-testid="forgot-submit-button"
                className="w-full bg-[#002FA7] hover:bg-[#001D6B] disabled:opacity-60 text-white rounded-md py-2.5 text-sm font-medium transition-colors shadow-sm"
              >
                {loading ? "Envoi…" : "Envoyer le lien de réinitialisation"}
              </button>
            </form>
            <p className="mt-6 text-sm text-slate-600">
              <Link to="/login" className="inline-flex items-center gap-1.5 text-[#002FA7] font-medium hover:underline" data-testid="forgot-to-login-link">
                <ArrowLeft className="w-4 h-4" /> Retour à la connexion
              </Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
