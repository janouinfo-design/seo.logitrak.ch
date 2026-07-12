# README_RECOVERY — LOGI SEO Booster (procédures de secours)

Application : projet Docker **logiseo** — dossier **/opt/logi-seo-booster** — domaine **seo.logitrak.ch**
Toutes les procédures ci-dessous ne concernent QUE cette application.

## 1. L'application ne répond plus

```bash
cd /opt/logi-seo-booster
docker compose -p logiseo ps                          # quel conteneur est down ?
docker compose -p logiseo logs --tail=100 logiseo_backend
docker compose -p logiseo restart logiseo_backend     # ou logiseo_frontend / logiseo_mongodb
```

Si le backend boucle en erreur : vérifier `.env` (MONGO_URL généré, clé Anthropic, ENCRYPTION_KEY).

## 2. Erreur 502 sur seo.logitrak.ch

```bash
curl -fs http://127.0.0.1:8105/api/       # backend joignable ?
curl -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3105/
sudo nginx -t && sudo systemctl reload nginx
sudo tail -50 /opt/logi-seo-booster/logs/nginx/error.log
```

## 3. Restaurer la base de données

```bash
cd /opt/logi-seo-booster
ls -lh backups/                            # choisir l'archive
./scripts/logiseo_restore.sh backups/logiseo_db_<DATE>.archive.gz
```

## 4. Revenir à la version précédente du code (rollback)

```bash
cd /opt/logi-seo-booster
tail logs/deploy_history.log               # dernier commit fonctionnel
git checkout <COMMIT>
docker compose -p logiseo build && docker compose -p logiseo up -d
```

## 5. Reconstruire complètement (sans perte de données)

Les données vivent dans le volume `logiseo_mongo_data` — un rebuild ne les efface PAS.

```bash
cd /opt/logi-seo-booster
docker compose -p logiseo stop
docker compose -p logiseo build --no-cache
docker compose -p logiseo up -d
```

⚠️ Ne JAMAIS utiliser `docker compose down -v` : le `-v` détruirait le volume de données.

## 6. Réinstallation totale sur un nouveau VPS

1. Suivre README_DEPLOYMENT.md étapes 0 → 6
2. Copier la dernière sauvegarde `logiseo_db_*.archive.gz` + `logiseo_env_*.bak` sur le nouveau serveur
3. `cp logiseo_env_<DATE>.bak /opt/logi-seo-booster/.env`
4. `./scripts/logiseo_restore.sh backups/logiseo_db_<DATE>.archive.gz`
5. Mettre à jour le DNS

## 7. Certificat SSL expiré

```bash
sudo certbot renew --dry-run
sudo certbot renew
sudo systemctl reload nginx
```
(Ne renouvelle que les certificats gérés par certbot ; n'affecte pas les autres domaines.)

## 8. Disque plein

```bash
df -h
du -sh /opt/logi-seo-booster/backups      # purger les vieilles archives logiseo_* SEULEMENT
docker image prune -f --filter "label=com.docker.compose.project=logiseo"   # images orphelines de CE projet
```
Jamais de `docker system prune -a` (toucherait les autres applications).
