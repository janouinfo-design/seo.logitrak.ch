# README_DEPLOYMENT — LOGI SEO Booster sur VPS (isolation stricte)

Application : **LOGI SEO Booster / AI Marketing Agent**
Domaine : **seo.logitrak.ch** — VPS : **83.228.207.198** (Ubuntu)
Projet Docker : **logiseo** — Dossier : **/opt/logi-seo-booster**

> Règle absolue : cette application est totalement isolée. Aucune commande de ce guide
> ne touche aux autres applications du VPS (New Navixy, LogiBus, LogiTime, LogiRent, Logitrak CRM…).
> Toutes les commandes Docker utilisent `-p logiseo`. Jamais de commande Docker globale.

---

## Architecture

```
Internet ──> Nginx hôte (443, SSL seo.logitrak.ch)
              ├── /api ──> 127.0.0.1:8105 ──> logiseo_backend (FastAPI + APScheduler)
              └── /    ──> 127.0.0.1:3105 ──> logiseo_frontend (React build statique)
                                   logiseo_backend ──> logiseo_mongodb (réseau logiseo_network, non exposé)
```

- Pas de conteneur worker séparé : le scheduler (rank tracking, calendrier éditorial) tourne DANS `logiseo_backend`.
- MongoDB n'est jamais exposé sur un port public.

## 0. Prérequis — inspection NON destructive du VPS

```bash
pwd && ls -la /opt
docker ps
docker compose ls
docker network ls
docker volume ls
sudo nginx -T | grep -E "server_name|listen" | sort -u
sudo ss -lntp
```

Vérifier que **3105** et **8105** sont libres et qu'aucun conteneur/réseau/volume `logiseo_*` n'existe déjà.
Si un port est pris → changer les ports côté gauche dans `docker-compose.yml` ET dans `nginx/logiseo.conf`.
**Ne rien supprimer pendant cette inspection.**

## 1. Récupérer le code

```bash
sudo mkdir -p /opt/logi-seo-booster && sudo chown $USER:$USER /opt/logi-seo-booster
git clone <VOTRE_REPO_GIT> /opt/logi-seo-booster
cd /opt/logi-seo-booster
mkdir -p logs/backend logs/nginx backups
chmod +x scripts/*.sh
```

## 2. Configurer les secrets

```bash
cp env.production.example .env
nano .env        # remplacer TOUS les CHANGE_ME
chmod 600 .env
```

Générer les secrets :
```bash
# JWT_SECRET
openssl rand -hex 32
# ENCRYPTION_KEY (Fernet)
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### ⚠️ Clé IA — IMPORTANT
La clé `EMERGENT_LLM_KEY` fournie sur la plateforme Emergent **ne fonctionne pas hors Emergent**.
Sur le VPS, mettre dans `EMERGENT_LLM_KEY` votre **propre clé Anthropic** (`sk-ant-…`, console.anthropic.com).
- Claude alimente : génération de contenu, Keyword Intelligence, Business Analyzer, AI Visibility.
- Les tests de citation ChatGPT/Gemini (module AI Visibility) nécessiteraient des clés OpenAI/Google —
  sans elles, ces moteurs seront marqués « indisponibles » (comportement dégradé propre, pas de crash).
- Si un appel IA échoue avec votre clé Anthropic, le signaler : une petite adaptation du code sera faite.

### OAuth (redirect URIs à mettre à jour chez les fournisseurs)
- Google Cloud Console → `https://seo.logitrak.ch/api/google/callback`
- LinkedIn Developer → `https://seo.logitrak.ch/api/linkedin/oauth/callback`

## 3. DNS

Créer l'enregistrement **A** : `seo.logitrak.ch → 83.228.207.198` puis vérifier :
```bash
dig +short seo.logitrak.ch   # doit renvoyer 83.228.207.198
```

## 4. Build & démarrage (projet logiseo uniquement)

```bash
cd /opt/logi-seo-booster
docker compose -p logiseo build      # ~5-10 min (Chromium inclus)
docker compose -p logiseo up -d
docker compose -p logiseo ps         # 3 conteneurs UP : logiseo_mongodb, logiseo_backend, logiseo_frontend
curl -fs http://127.0.0.1:8105/api/  # backend OK
curl -fs -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3105/   # 200
```

## 5. Nginx hôte (nouveau fichier UNIQUEMENT)

```bash
sudo cp nginx/logiseo.conf /etc/nginx/sites-available/logiseo.conf
sudo ln -s /etc/nginx/sites-available/logiseo.conf /etc/nginx/sites-enabled/logiseo.conf
sudo nginx -t                        # OBLIGATOIRE avant reload
sudo systemctl reload nginx          # reload, PAS restart
```

## 6. HTTPS (ce domaine uniquement)

```bash
sudo certbot --nginx -d seo.logitrak.ch
sudo nginx -t && sudo systemctl reload nginx
```

## 7. Sauvegardes automatiques

```bash
crontab -e
# Ajouter :
0 2 * * * /opt/logi-seo-booster/scripts/logiseo_backup.sh >> /opt/logi-seo-booster/logs/backup.log 2>&1
```

## 8. Contrôle final avant mise en production

- [ ] Les autres applications du VPS répondent toujours (tester leurs domaines)
- [ ] `docker ps` : aucun conteneur pré-existant supprimé/renommé
- [ ] `https://seo.logitrak.ch` ouvre la bonne application (page login LOGI SEO Booster)
- [ ] Création de compte + login OK
- [ ] Connexion d'un site + lancement d'un audit OK
- [ ] Génération IA OK (clé Anthropic valide)
- [ ] `docker compose -p logiseo logs -f` lisible
- [ ] `./scripts/logiseo_backup.sh` produit une archive dans `backups/`
- [ ] `sudo reboot` (fenêtre de maintenance) → les 3 conteneurs logiseo redémarrent seuls (`restart: unless-stopped`), les autres apps aussi
- [ ] Aucun secret visible dans le frontend (source de la page) ni dans Git (`.env` ignoré)

## Commandes du quotidien (toujours avec -p logiseo)

```bash
cd /opt/logi-seo-booster
docker compose -p logiseo ps                    # état
docker compose -p logiseo logs -f logiseo_backend   # logs backend
docker compose -p logiseo restart logiseo_backend   # redémarrer le backend seul
docker compose -p logiseo stop                  # arrêter CETTE app uniquement
./scripts/logiseo_deploy.sh                     # mise à jour complète (backup + pull + build + health check)
```

## Mise à jour & rollback

`scripts/logiseo_deploy.sh` fait automatiquement : vérification du dossier → sauvegarde DB →
mémorisation du commit courant → `git pull` → build → up → health check.

Rollback manuel :
```bash
cd /opt/logi-seo-booster
tail logs/deploy_history.log            # retrouver le dernier commit fonctionnel
git checkout <COMMIT>
docker compose -p logiseo build && docker compose -p logiseo up -d
# Si la base doit aussi revenir en arrière :
./scripts/logiseo_restore.sh backups/logiseo_db_<DATE>.archive.gz
```

## Interdictions absolues (rappel)

Jamais : `docker system prune -a`, `docker volume/network/container prune`,
`docker compose down -v` (hors de ce dossier ou sans confirmation), `rm -rf /opt/*`,
modification de `/etc/nginx/nginx.conf` ou des vhosts des autres applications,
arrêt/restart global de Docker, réutilisation d'un volume ou conteneur d'une autre app.
