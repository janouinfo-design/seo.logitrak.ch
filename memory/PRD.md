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

## Implemented (2026-02-07 — MVP + Phase 2)
- [x] Auth JWT (register, login, /me)
- [x] Multi-sites Wix (CRUD) avec isolation utilisateur
- [x] Récupération pages / blog posts Wix (avec fallback mock automatique)
- [x] Audit SEO automatique (titres, méta, H1/H2, images alt, contenu, URLs)
- [x] Génération IA Claude Sonnet 4.5 (article, page locale, FAQ, service)
- [x] **Recherche IA de mots-clés** (clustering par intention : locale, informationnelle, transactionnelle, navigationnelle ; difficulté + volume + priorité)
- [x] **Liste de mots-clés cibles sauvegardés**
- [x] **Optimiseur de pages Wix** (comparaison avant/après ; titre, meta, H1, plan H2, intro AI Overviews, FAQ, plan de contenu, améliorations chiffrées)
- [x] **Application en 1 clic d'une optimisation → brouillon prêt à publier** (idempotent)
- [x] Drafts CRUD + versions + rollback
- [x] Publication vers Wix Blog (création de brouillon)
- [x] Historique des publications (logs)
- [x] Performance (mock GSC : impressions, clics, position, CTR, mots-clés, recommandations)
- [x] Dashboard avec stats globales et accès rapides
- [x] UI complète FR, Swiss design, 9 pages + détail brouillon

## Backlog / Phase 2 (P0)
- [ ] OAuth Google → vraies données Google Search Console & Google Analytics
- [ ] Vraie Wix App (App ID + Secret) via Wix Dev Center pour OAuth multi-comptes
- [ ] Encryption at-rest des clés API Wix (Fernet ou KMS)
- [ ] Conversion markdown → Wix RichContent pour publication réelle des articles
- [ ] Suivi automatique du classement par mot-clé (cron)
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
