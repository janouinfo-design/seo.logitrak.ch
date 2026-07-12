import { Link } from "react-router-dom";
import {
  HelpCircle,
  Globe,
  Search,
  Radar,
  BrainCircuit,
  Sparkles,
  Wand2,
  Rocket,
  FileText,
  LineChart,
  History,
  CreditCard,
  KeyRound,
  ArrowRight,
  RefreshCcw,
  CheckCircle2,
} from "lucide-react";

const STEPS = [
  {
    num: "1",
    title: "COMMENCER — Connecter votre site",
    color: "#002FA7",
    items: [
      { icon: Globe, to: "/sites", label: "Sites", text: "Ajoutez votre site (ou bouton « Ajout rapide » pour Logirent + Logitime). Sans site connecté, rien d'autre ne fonctionne." },
    ],
  },
  {
    num: "2",
    title: "Comprendre où vous en êtes (diagnostic)",
    color: "#0F766E",
    items: [
      { icon: Search, to: "/audit", label: "Audit SEO", text: "Scan technique de vos pages : titres, metas, images, doublons, erreurs SEO." },
      { icon: Radar, to: "/ai-visibility", label: "AI Visibility", text: "Êtes-vous cité par ChatGPT, Gemini, Claude ? Score /100 + actions prioritaires avec gains estimés." },
      { icon: BrainCircuit, to: "/keyword-intelligence", label: "Keyword Intelligence", text: "L'IA comprend votre business puis vous dit : quels mots-clés viser, quels contenus créer, quelles pages locales manquent, quels concurrents dépasser." },
    ],
    note: "Ces 3 analyses vous donnent votre feuille de route complète.",
  },
  {
    num: "3",
    title: "Agir — Créer le contenu",
    color: "#9333EA",
    items: [
      { icon: BrainCircuit, to: "/keyword-intelligence", label: "Keyword Intelligence", text: "Le plus simple ⚡ : cliquez « Générer ce contenu » directement sur les recommandations." },
      { icon: Sparkles, to: "/generator", label: "Générateur IA", text: "Créez un article, une page locale, une FAQ ou une page service manuellement." },
      { icon: Wand2, to: "/optimizer", label: "Optimiseur de pages", text: "Améliorez une page existante : comparaison avant/après, application en 1 clic." },
      { icon: Rocket, to: "/automation", label: "Automatisation", text: "Génération en lot (10-20 articles d'un coup) + calendrier éditorial automatique (1 article tous les X jours)." },
    ],
  },
  {
    num: "4",
    title: "Valider et publier",
    color: "#D97706",
    items: [
      { icon: FileText, to: "/drafts", label: "Brouillons", text: "Relisez chaque contenu généré, puis publiez : GitHub Pages (blog.logirent.ch) en 1 clic, post LinkedIn auto-généré, ou export ZIP/Wix." },
    ],
  },
  {
    num: "5",
    title: "FINIR — Mesurer et recommencer",
    color: "#15803D",
    items: [
      { icon: LineChart, to: "/performance", label: "Performance", text: "Positions Google réelles (Search Console), trafic, suivi quotidien des mots-clés." },
      { icon: History, to: "/history", label: "Historique", text: "Tout ce qui a été publié, avec versions et rollback." },
      { icon: Radar, to: "/ai-visibility", label: "AI Visibility", text: "Relancez l'analyse chaque mois pour voir votre score progresser 📈" },
    ],
  },
];

const MODULES = [
  { icon: Globe, to: "/sites", label: "Sites", text: "Connexion de vos sites (Wix, URL publique, GitHub, FTP). Configuration des accès de publication." },
  { icon: Search, to: "/audit", label: "Audit SEO", text: "Audit technique complet + détection de contenus dupliqués entre vos pages." },
  { icon: Radar, to: "/ai-visibility", label: "AI Visibility", text: "10 scores d'optimisation IA (GEO) : citation réelle par ChatGPT/Claude/Gemini, EEAT, Schema.org, entités…" },
  { icon: KeyRound, to: "/keywords", label: "Mots-clés", text: "Recherche simple de mots-clés par thème + liste de mots-clés suivis." },
  { icon: BrainCircuit, to: "/keyword-intelligence", label: "Keyword Intelligence", text: "Stratégie complète : clusters scorés, victoires rapides, plan de contenu, pages locales, concurrents." },
  { icon: Wand2, to: "/optimizer", label: "Optimiseur de pages", text: "Réécriture IA de vos pages existantes avec comparaison avant/après." },
  { icon: Sparkles, to: "/generator", label: "Générateur IA", text: "Génération d'articles, pages locales, FAQ et pages service (avec auto-publication GitHub optionnelle)." },
  { icon: Rocket, to: "/automation", label: "Automatisation", text: "Génération en lot + calendrier éditorial : l'application produit et publie toute seule." },
  { icon: FileText, to: "/drafts", label: "Brouillons", text: "Validation, édition, versions et publication de tous vos contenus." },
  { icon: History, to: "/history", label: "Historique", text: "Journal de toutes les publications effectuées." },
  { icon: LineChart, to: "/performance", label: "Performance", text: "Données réelles Google Search Console + Analytics, suivi de classement par mot-clé." },
  { icon: CreditCard, to: "/billing", label: "Facturation", text: "Votre plan (Free, Pro, Business, Agency), quotas d'articles et gestion de l'abonnement." },
];

const FAQ = [
  { q: "Par quoi commencer si je découvre l'application ?", a: "Suivez le parcours ci-dessus dans l'ordre : connectez votre site (étape 1), puis lancez les 3 diagnostics (étape 2). En 10 minutes vous saurez exactement quoi faire." },
  { q: "Une génération semble longue, est-ce normal ?", a: "Oui. L'IA rédige des contenus complets (1-2 min) et les analyses AI Visibility interrogent plusieurs moteurs IA (2-3 min). Un bandeau de progression s'affiche — vous pouvez naviguer ailleurs, le résultat vous attend." },
  { q: "Mes contenus sont-ils publiés automatiquement ?", a: "Non, jamais sans votre accord. Tout passe par les Brouillons pour validation — sauf si vous activez explicitement l'auto-publication (Générateur ou Calendrier éditorial)." },
  { q: "Comment être cité par ChatGPT et les autres IA ?", a: "Lancez AI Visibility : le rapport liste précisément ce qui vous freine (Schema.org, EEAT, témoignages, fraîcheur…) avec des actions priorisées et le gain estimé pour chacune." },
  { q: "À quoi sert la page Mots-clés si j'ai Keyword Intelligence ?", a: "Mots-clés = recherche rapide par thème + votre liste de suivi. Keyword Intelligence = stratégie complète pilotée par l'IA (elle analyse votre business avant de recommander). Les mots-clés sauvegardés depuis les deux pages se retrouvent au même endroit." },
  { q: "Comment connecter Google Search Console ?", a: "Page Performance → « Connecter Google ». Vous verrez alors vos vraies positions, impressions et clics, et le suivi quotidien automatique s'activera." },
  { q: "Que se passe-t-il si j'atteins mon quota d'articles ?", a: "Le plan Free inclut 5 articles/mois. Passez sur un plan supérieur depuis la page Facturation pour continuer (paiement sécurisé Stripe)." },
];

export default function Aide() {
  return (
    <div className="p-8 max-w-5xl" data-testid="aide-page">
      <div className="flex items-center gap-2.5 mb-1">
        <div className="w-9 h-9 rounded-md bg-[#002FA7] flex items-center justify-center">
          <HelpCircle className="w-5 h-5 text-white" />
        </div>
        <h1 className="font-display text-2xl font-bold text-slate-950">Aide & mode d'emploi</h1>
      </div>
      <p className="text-sm text-slate-600 mb-8 max-w-2xl">
        Le parcours complet, de la connexion de votre site jusqu'au suivi de vos résultats — où commencer, où finir.
      </p>

      {/* La boucle */}
      <div className="border border-[#002FA7]/20 bg-blue-50/40 rounded-lg p-5 mb-8" data-testid="aide-boucle">
        <div className="flex items-center gap-2 mb-2">
          <RefreshCcw className="w-4 h-4 text-[#002FA7]" />
          <div className="text-sm font-semibold text-slate-900">La boucle en résumé</div>
        </div>
        <div className="flex items-center flex-wrap gap-2 text-sm font-semibold text-slate-800">
          {["Connecter", "Analyser", "Générer", "Publier", "Mesurer"].map((s, i) => (
            <span key={s} className="flex items-center gap-2">
              <span className="bg-white border border-slate-200 rounded-md px-3 py-1.5">{s}</span>
              {i < 4 && <ArrowRight className="w-4 h-4 text-slate-400" />}
            </span>
          ))}
          <span className="flex items-center gap-2 text-slate-500 font-normal text-xs">… et on recommence 🔄</span>
        </div>
        <p className="text-xs text-slate-600 mt-3">
          💡 <span className="font-semibold">Routine idéale :</span> 1× par mois, relancez AI Visibility + Keyword Intelligence,
          générez les contenus recommandés, publiez, et suivez vos positions dans Performance.
        </p>
      </div>

      {/* Parcours étape par étape */}
      <h2 className="text-base font-display font-bold text-slate-950 mb-4">🚀 Parcours recommandé, étape par étape</h2>
      <div className="space-y-4 mb-10" data-testid="aide-parcours">
        {STEPS.map((step) => (
          <div key={step.num} className="border border-slate-200 bg-white rounded-lg p-5">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-7 h-7 rounded-full flex items-center justify-center text-white text-sm font-bold flex-shrink-0" style={{ background: step.color }}>
                {step.num}
              </div>
              <div className="font-semibold text-sm text-slate-900">{step.title}</div>
            </div>
            <div className="space-y-2.5 ml-10">
              {step.items.map((it) => {
                const Icon = it.icon;
                return (
                  <div key={it.label + it.text} className="flex items-start gap-3">
                    <Icon className="w-4 h-4 text-slate-400 mt-0.5 flex-shrink-0" />
                    <div className="text-sm text-slate-700">
                      <Link to={it.to} className="font-semibold text-[#002FA7] hover:underline">{it.label}</Link>
                      {" — "}{it.text}
                    </div>
                  </div>
                );
              })}
              {step.note && (
                <div className="flex items-center gap-2 text-xs text-slate-500 pt-1">
                  <CheckCircle2 className="w-3.5 h-3.5 text-green-600" /> {step.note}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Modules */}
      <h2 className="text-base font-display font-bold text-slate-950 mb-4">📚 Toutes les pages en un coup d'œil</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mb-10" data-testid="aide-modules">
        {MODULES.map((m) => {
          const Icon = m.icon;
          return (
            <Link
              key={m.to + m.label}
              to={m.to}
              className="border border-slate-200 bg-white rounded-lg p-4 hover:border-[#002FA7]/40 hover:shadow-sm transition-all group"
            >
              <div className="flex items-center gap-2 mb-1.5">
                <Icon className="w-4 h-4 text-[#002FA7]" />
                <div className="font-semibold text-sm text-slate-900 group-hover:text-[#002FA7] transition-colors">{m.label}</div>
              </div>
              <p className="text-xs text-slate-600 leading-snug">{m.text}</p>
            </Link>
          );
        })}
      </div>

      {/* FAQ */}
      <h2 className="text-base font-display font-bold text-slate-950 mb-4">❓ Questions fréquentes</h2>
      <div className="space-y-2 mb-8" data-testid="aide-faq">
        {FAQ.map((f, i) => (
          <details key={i} className="border border-slate-200 bg-white rounded-lg px-4 py-3 group">
            <summary className="text-sm font-semibold text-slate-900 cursor-pointer hover:text-[#002FA7] transition-colors">
              {f.q}
            </summary>
            <p className="text-sm text-slate-600 mt-2 leading-relaxed">{f.a}</p>
          </details>
        ))}
      </div>

      <div className="border border-slate-200 bg-slate-50 rounded-lg p-4 text-sm text-slate-600">
        📖 Besoin de plus de détails ? Le{" "}
        <a href="/guide-logi-seo-booster.pdf" target="_blank" rel="noopener noreferrer" className="text-[#002FA7] font-semibold hover:underline">
          Guide PDF complet
        </a>{" "}
        est disponible en bas du menu latéral.
      </div>
    </div>
  );
}
