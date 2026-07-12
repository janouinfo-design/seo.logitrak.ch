# VPS APPLICATION REGISTRY — LOGI SEO Booster

Fiche d'identification de cette application sur le VPS.
À conserver à jour. Ne contient AUCUN secret.

| Élément | Valeur |
|---|---|
| Application | LOGI SEO Booster / AI Marketing Agent |
| Dossier | `/opt/logi-seo-booster` |
| Projet Docker Compose | `logiseo` (`docker compose -p logiseo …`) |
| Domaine | `seo.logitrak.ch` |
| VPS | 83.228.207.198 (Ubuntu) |
| Frontend | conteneur `logiseo_frontend` → 127.0.0.1:**3105** |
| Backend | conteneur `logiseo_backend` → 127.0.0.1:**8105** (FastAPI, préfixe `/api`) |
| Base de données | MongoDB 7 — conteneur `logiseo_mongodb`, base `logiseo_prod`, user `logiseo_app` (réseau Docker uniquement, jamais exposée) |
| Réseau Docker | `logiseo_network` |
| Volumes | `logiseo_mongo_data` |
| Nginx (hôte) | `/etc/nginx/sites-available/logiseo.conf` → symlink sites-enabled |
| SSL | Let's Encrypt / certbot, domaine `seo.logitrak.ch` uniquement |
| Logs | `/opt/logi-seo-booster/logs/{backend,nginx}` + `docker compose -p logiseo logs` |
| Sauvegardes | `/opt/logi-seo-booster/backups/logiseo_db_YYYY-MM-DD_HHMM.archive.gz` (cron 02:00, rétention 14 j) |
| Cron | `logiseo_backup.sh` (02:00 quotidien) |
| Worker / scheduler | intégré au backend (APScheduler dans `logiseo_backend`) — pas de conteneur séparé |
| Dépôt Git | dédié à cette application (déploiement : `scripts/logiseo_deploy.sh`) |

## Ne PAS confondre avec les autres applications du VPS
New Navixy, LogiBus, LogiTime, LogiRent, Logitrak CRM / Prospective — aucune ressource partagée.
