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

## Backlog / Phase 2 (P0)
- [ ] Vraie Wix App (App ID + Secret) via Wix Dev Center pour OAuth multi-comptes
- [ ] Conversion markdown → Wix RichContent pour publication réelle des articles
- [ ] Détection de doublons inter-pages + indexation/sitemap analysis

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
