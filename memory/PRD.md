# LOGI SEO Booster — Product Requirements Document

## Original problem statement
Application web "LOGI SEO Booster" compatible avec les sites Wix Logirent et Logitime,
permettant d'analyser, générer, optimiser et publier du contenu SEO afin d'améliorer
le classement Google et la visibilité dans les IA (ChatGPT, Gemini, Perplexity, Google AI Overviews).

## User Personas
- **Propriétaire / dirigeant** (cible primaire) : utilise l'outil pour Logirent et Logitime,
  veut un score SEO clair, des contenus prêts à valider, aucune publication automatique.
- **Rédacteur / content manager** (cible secondaire) : génère et relit les contenus avant publication.

## User Choices (from kickoff)
- Stack : React + FastAPI + MongoDB
- IA : Claude Sonnet 4.5 (Anthropic) via Emergent Universal Key
- Auth : JWT custom (email/password)
- Wix : clé API simple (pas d'OAuth) au MVP, multi-sites
- GSC/GA : mockés pour le MVP, architecture extensible
- Langue : Français

## Architecture
- Backend FastAPI sur `/api`, MongoDB via Motor, JWT auth (bcrypt), httpx pour Wix API.
- Frontend React (CRA), React Router, Tailwind, Shadcn UI, Recharts, Sonner, Lucide.
- Design : Swiss & High-Contrast, bleu #002FA7, fonts Cabinet Grotesk + IBM Plex Sans.
- Génération IA : `emergentintegrations.llm.chat.LlmChat` avec `claude-sonnet-4-5-20250929`.

## Implemented (2026-02-07 — MVP + Phase 2 + Phase 2.5)
- [x] Auth JWT (register, login, /me)
- [x] **Multi-plateformes : Wix API + URL publique (Emergent / WordPress / custom)**
- [x] **Bouton "Ajout rapide" : connecte logirent.ch + logitime.ch en 1 clic**
- [x] **Crawler HTTP réel (sitemap.xml + BFS) sur les vraies URLs publiques**
- [x] **Détection automatique des SPA (sites client-rendered) — issue SEO critique remontée**
- [x] Multi-sites isolés par utilisateur
- [x] Audit SEO automatique sur les vraies données scrapées
- [x] Génération IA Claude Sonnet 4.5 (article, page locale, FAQ, service)
- [x] Recherche IA de mots-clés (clustering par intention)
- [x] Liste de mots-clés cibles sauvegardés
- [x] Optimiseur de pages réelles (comparaison avant/après)
- [x] Application en 1 clic d'une optimisation → brouillon prêt à publier (idempotent)
- [x] Drafts CRUD + versions + rollback
- [x] Publication contextualisée : Wix Blog API (sites Wix) / "Ready for export" (URL publique)
- [x] Historique des publications
- [x] Performance (mock GSC) avec bandeau d'avertissement
- [x] Dashboard avec stats et accès rapides
- [x] UI complète FR, Swiss design, 9 pages
- [x] Export ZIP (HTML SEO + JSON + README) pour upload FTP manuel
- [x] **Publication GitHub** (2026-02-07) : push direct des fichiers HTML/JSON dans le repo du site via PAT — pour sites React/Vite hébergés sur Vercel/Netlify. Endpoints `/api/sites/{id}/test-github` et `/api/drafts/{id}/publish-github`. Dialogue de config par site avec test de connexion.
- [x] **Google Search Console + Analytics (OAuth)** (2026-02-07) : OAuth 2.0 web-server flow avec refresh tokens, scopes `webmasters.readonly` + `analytics.readonly`. Endpoints `/api/google/login`, `/api/google/callback`, `/api/google/status`, `/api/google/disconnect`, `/api/google/gsc-sites`, `/api/sites/{id}/google-settings`, `/api/sites/{id}/performance-real`. Page Performance complètement refondue : sélection propriété GSC depuis liste + GA4 Property ID, affichage temps réel des impressions/clics/CTR/position + sessions/utilisateurs/bounce/conversions. Fallback automatique sur mock si pas connecté.
- [x] **Suivi de classement par mot-clé** (2026-02-07) : snapshots quotidiens auto à 04:00 UTC via APScheduler. Endpoints `/api/sites/{id}/rank-snapshot` (manuel) et `/api/sites/{id}/rank-tracking` (séries temporelles). Bouton "Capturer maintenant" + tableau Δ position vs début dans la page Performance.
- [x] **Auto-update sitemap.xml sur push GitHub** (2026-02-07) : lors d'un `/drafts/{id}/publish-github`, le sitemap est lu, mis à jour (lastmod) ou créé en y ajoutant l'URL de la nouvelle page. Recherche le sitemap dans `folder/sitemap.xml`, `public/sitemap.xml` puis `sitemap.xml`.
- [x] **Chiffrement Fernet at-rest** (2026-02-07) : tous les tokens sensibles (`wix_api_key`, `ftp_password`, `vps_api_token`, `github_token`, `google_oauth.refresh_token` + `access_token`) chiffrés via Fernet avant insertion en MongoDB. Préfixe `enc::` pour permettre la migration progressive (legacy plaintext toujours lisible). `ENCRYPTION_KEY` dans `backend/.env`.
- [x] **Détection de doublons inter-pages** (2026-02-07) : endpoint `POST /api/sites/{id}/duplicate-scan` qui calcule la similarité Jaccard sur bigrams normalisés (titre + meta + body) entre toutes les pages du site + détecte les titres H1 et meta descriptions exactement identiques. Bouton "Détecter doublons" sur la page Audit avec panneau de résultats (paires similaires colorées par sévérité, groupes de titres/metas dupliqués, recommandations IA).
- [x] **Génération asynchrone (jobs)** (2026-02-07) : nouveau endpoint `POST /api/content/generate-async` + `GET /api/content/jobs/{id}` pour bypasser le timeout 60s de l'ingress K8s. Frontend Generator.jsx fait du polling toutes les 3s avec toast "Génération en cours…". Plus de timeout possible.
- [x] **Auto-publish GitHub depuis le Générateur** (2026-02-07) : checkbox "⚡ Publier automatiquement sur GitHub après génération" dans la page Générateur. Quand cochée + site avec GitHub configuré → la génération auto-push le brouillon. Désactivée + grisée si GitHub pas configuré.

## Pivot produit (2026-06) — "Agent Marketing IA d'entreprise"
Le produit pivote d'un outil SEO vers un Directeur Marketing IA autonome.
Nom final : EN RÉFLEXION (l'utilisateur veut analyser 50-100 propositions : domaines .com/.ai/.io,
réseaux sociaux, marques CH/UE/WIPO/US, prononciation, mémorisation). "Vela" DÉCONSEILLÉ
(conflits Vela Systems Inc. ~19 marques logicielles + Vela Software Group). Garder
"LOGI SEO Booster" en placeholder jusqu'à validation explicite.
Critère de décision produit : "Est-ce que cela nous rapproche du meilleur Directeur Marketing IA du marché ?"
Préférence : 20 fonctionnalités exceptionnelles plutôt que 100 moyennes.

- [x] **AI Visibility Center** (2026-06-12) : module GEO complet, remplace le simple "GEO Score".
  Backend `/app/backend/ai_visibility.py` (module séparé) + routes dans server.py :
  `POST /api/sites/{id}/ai-visibility` (job async, poll via /content/jobs/{job_id}),
  `GET .../ai-visibility/latest`, `GET .../ai-visibility/history`. Collection `ai_visibility_reports`.
  Pipeline : crawl pages clés (sitemap/BFS + fallback Playwright SPA) → analyses déterministes
  (Schema.org JSON-LD, Knowledge Graph/sameAs, lisibilité IA/chunking, fraîcheur, signaux EEAT)
  → analyse LLM Claude (entité, SEO sémantique, requêtes de test, explications, actions priorisées
  avec gains estimés) → **tests de citation RÉELS** sur ChatGPT (gpt-4o), Claude et Gemini
  (12 requêtes) ; Perplexity/Copilot/Mistral/DeepSeek estimés (badgés "Estimé").
  10 scores : AI Visibility (global), AI Citation, AI Trust, EEAT, Entity, Schema,
  Knowledge Graph, SEO Sémantique, Lisibilité IA, Fraîcheur.
  Frontend : page `/ai-visibility` (`AIVisibility.jsx`), nav "AI Visibility" (icône Radar).
  Testé e2e sur logirent.ch : score 43/100, diagnostic + 6 actions pertinentes.

## Backlog Sprint 1 (ordre validé par l'utilisateur, 2026-06)
- [x] 🥈 **Keyword Intelligence Engine 2.0** (2026-06-12) : backend `/app/backend/keyword_intelligence.py`
  (réutilise `ai_visibility.fetch_pages`). 2 appels LLM : (1) Business Profile (activité, produits,
  cibles, zones, positionnement, concurrents — stocké dans collection `business_profiles`, brique
  de l'AI Business Analyzer), (2) Intelligence complète : clusters scorés (potentiel 0-100,
  difficulté, rentabilité, volume, quick_win), quick wins, top opportunités, plan de contenu
  (types compatibles générateur), pages locales manquantes, concurrents + comment les dépasser.
  Routes : `POST /api/sites/{id}/keyword-intelligence` (job async), `GET .../latest`.
  Collection `keyword_intelligence_reports`. Frontend : page `/keyword-intelligence`
  (`KeywordIntelligence.jsx`), nav "Keyword Intelligence" (icône BrainCircuit).
  Boutons : ⭐ sauvegarder mot-clé (→ /keywords/saved), "Générer ce contenu" en 1 clic
  (→ /content/generate-async avec polling + toast). Testé e2e sur logirent.ch :
  6 clusters, 8 quick wins, 10 contenus, 5 pages locales, 6 concurrents — l'IA a détecté
  le désalignement stratégique B2C/B2B des mots-clés suivis.
- [x] Identifiants démo affichés sur la page de connexion + bouton "Remplir automatiquement" (2026-06-12).
- [x] 🥉 **AI Business Analyzer** (2026-06-12) : backend `/app/backend/business_analyzer.py`.
  Analyse "directeur marketing" : identité, produits/services, segments cibles (besoins + messages),
  zones, positionnement, value props, 6 concurrents (forces/faiblesses/comment les dépasser),
  SWOT complet, 5 priorités marketing. Routes : `POST /api/sites/{id}/business-analyzer` (job async),
  `GET/PUT /api/sites/{id}/business-profile` (profil éditable par l'utilisateur, flag `edited`,
  merge partiel). Le profil stocké (`business_profiles`) est RÉUTILISÉ par Keyword Intelligence
  (skip du crawl + de l'appel LLM profil si un profil existe — corrections utilisateur prioritaires).
  Frontend : page `/business` (`BusinessAnalyzer.jsx`), nav "Business Analyzer" (icône Building2),
  mode édition (activité, description, positionnement, zones, modèle). Testé e2e sur logirent.ch.
- [x] **Menu Aide** (2026-06-12) : page `/aide` (`Aide.jsx`) — boucle Connecter→Analyser→Générer→
  Publier→Mesurer, parcours 5 étapes avec liens, 13 modules expliqués, 7 FAQ, lien Guide PDF.
- [ ] **Repositionnement UI "Agent Marketing IA"** : dashboard, storytelling, agents IA
  (SEO Agent, GEO Agent, Content Agent, Social Agent). Nom placeholder inchangé.
- [ ] **Workflow Builder enrichi** : déclencheurs = perte de positions, baisse de trafic,
  nouvelle page, concurrent progresse, backlink perdu, 404, Core Web Vitals dégradés,
  nouvelle tendance, FAQ concurrent → actions (analyser, réécrire, publier, alerter).
- [ ] **Réseaux sociaux Meta** : Facebook Pages + Instagram + Threads — préparer architecture/UI ;
  connexion réelle dès que l'utilisateur fournit App ID/Secret Meta (pas encore disponibles).
- [ ] Recherche de nom : générer 50-100 propositions avec critères (domaines, marques, prononciation).

## Backlog / Phase 2 (P0)
- [x] Génération en lot (batch) — fait (Automation.jsx)
- [x] Calendrier éditorial cron — fait
- [x] LinkedIn auto-posting — fait
- [ ] Vraie Wix App (App ID + Secret) via Wix Dev Center pour OAuth multi-comptes
- [ ] Alerte email auto si une page tracée chute de >5 positions sur Google
- [ ] Vérification utilisateur du checkout Stripe (carte test 4242…) — toujours en attente

## Backlog / Phase 3 (P1)
- [ ] Comparateur de versions visuel (diff)
- [ ] Notifications email avant publication (validation par responsable)
- [ ] Multi-utilisateurs / rôles par site (admin / rédacteur)
- [ ] Génération en lot (10 pages locales d'un coup)
- [ ] Export PDF des audits
- [ ] Intégration Bing Webmaster Tools

## Phase 4 (P2)
- [ ] Suggestions automatiques de maillage interne
- [ ] Analyse de la concurrence (SERP scraping)
- [ ] Refactorer `server.py` (~990 lignes) en modules : auth/sites/wix/audit/content/drafts/publish

## Known limitations (MVP)
- Wix API key stockée en clair en base — l'UI affiche "Chiffrée" par anticipation. À chiffrer en P0.
- Publication Wix : transmet body_markdown comme texte simple — la mise en forme markdown
  ne sera pas rendue dans Wix tant que la conversion RichContent n'est pas implémentée.
- Données Performance entièrement simulées (mocked: true côté API).

## Test credentials
Voir `/app/memory/test_credentials.md`.
