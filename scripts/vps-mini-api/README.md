# LOGI SEO Booster — Mini-API VPS

Petite API Node.js/Express à déployer sur votre VPS (Logirent.ch / Logitime.ch)
pour recevoir directement les contenus SEO depuis LOGI SEO Booster — sans
copier-coller manuel.

## Ce que ça fait

1. Reçoit un brouillon optimisé depuis LOGI SEO Booster via un endpoint sécurisé
2. Le stocke en JSON (et HTML) dans `data/`
3. Expose les contenus sur `/blog/:slug` et via une API publique

## Installation (5 minutes)

```bash
# 1. Sur votre VPS, en SSH :
mkdir -p /opt/logi-seo-api
cd /opt/logi-seo-api

# 2. Copiez les fichiers depuis votre poste local
scp -r vps-mini-api/* user@votre-vps:/opt/logi-seo-api/

# 3. Installez les dépendances
npm install

# 4. Créez votre fichier de configuration
cp .env.example .env

# 5. Générez un token aléatoire et collez-le dans .env (variable SEO_API_TOKEN)
openssl rand -hex 32

# 6. Démarrez en mode test
node server.js
# Vous devriez voir : ✓ LOGI SEO mini-API démarrée sur le port 3001
```

## Test rapide

```bash
# Sur votre VPS, dans un autre terminal :
curl http://localhost:3001/api/health
# → {"ok":true,"app":"logi-seo-vps-mini-api","version":"1.0.0"}

# Publication test (remplacez TOKEN par votre vraie valeur) :
curl -X POST http://localhost:3001/api/seo/publish \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Test","body_markdown":"## Hello\nContenu de test","meta_description":"Démo"}'
# → {"id":"...","slug":"test","url_path":"/blog/test"}

curl http://localhost:3001/api/seo/list
curl http://localhost:3001/blog/test
```

## Mise en production avec PM2 (recommandé)

```bash
npm install -g pm2
pm2 start server.js --name logi-seo-api
pm2 save
pm2 startup       # affiche la commande systemd à exécuter
```

## Mise en production avec systemd

Créez `/etc/systemd/system/logi-seo-api.service` :

```ini
[Unit]
Description=LOGI SEO Booster Mini-API
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/logi-seo-api
EnvironmentFile=/opt/logi-seo-api/.env
ExecStart=/usr/bin/node /opt/logi-seo-api/server.js
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Puis :

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now logi-seo-api
sudo systemctl status logi-seo-api
```

## Reverse proxy Nginx (HTTPS)

Ajoutez à votre config Nginx (ex. `/etc/nginx/sites-available/logirent.ch`) :

```nginx
# Si vous voulez exposer l'API sur https://api.logirent.ch :
server {
    listen 443 ssl http2;
    server_name api.logirent.ch;

    ssl_certificate     /etc/letsencrypt/live/api.logirent.ch/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.logirent.ch/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:3001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# OU sur votre domaine principal, sous le chemin /seo-api :
location /seo-api/ {
    proxy_pass http://127.0.0.1:3001/;
}
```

Pensez à `sudo nginx -t && sudo systemctl reload nginx` et à obtenir un
certificat Let's Encrypt avec `sudo certbot --nginx -d api.logirent.ch`.

## Connecter LOGI SEO Booster à votre VPS

Dans l'app LOGI SEO Booster :

1. Page **Sites** → bouton **« Ajouter un site »**
2. Choisissez le type **« VPS API »**
3. Renseignez :
   - **URL du site** : `https://www.logirent.ch`
   - **URL de l'API** : `https://api.logirent.ch` (ou `https://www.logirent.ch/seo-api`)
   - **Token API** : la valeur copiée de votre `.env` (SEO_API_TOKEN)
4. Sauvegardez. À partir de maintenant, le bouton **« Publier sur Wix »**
   sur les brouillons enverra le contenu directement à votre VPS.

## Consommer le contenu côté site Logirent / Logitime

### Option A — Page statique HTML (le plus simple)
Les contenus sont accessibles immédiatement sur `https://api.logirent.ch/blog/:slug`
sous forme de page HTML basique. Vous pouvez les iframer ou les linker depuis vos
sites principaux.

### Option B — Consommer le JSON dans votre app React
```js
const r = await fetch("https://api.logirent.ch/api/seo/list");
const { items } = await r.json();
// items = [{id, slug, title, meta_title, meta_description, ...}]

const detail = await fetch(`https://api.logirent.ch/api/seo/${slug}`).then(r => r.json());
// detail = {body_html, body_markdown, faq, keywords, ...}
```

### Option C — Recopier au build dans votre site
Faites un script `prebuild` qui lit `/api/seo/list` et copie les contenus
dans votre dossier `public/blog/` pour qu'ils soient servis statiquement
(et donc indexables sans JS).

## Sécurité

- Le token est lu depuis `.env` (jamais commité, jamais hardcodé)
- Seul l'endpoint POST `/api/seo/publish` requiert le token
- Les endpoints GET (`/api/seo/list`, `/api/seo/:slug`, `/blog/:slug`) sont publics
  → c'est volontaire pour que vos vraies pages puissent les consommer
- Mettez l'API derrière Nginx + Let's Encrypt pour le HTTPS
- Si plusieurs sites (Logirent + Logitime), déployez 2 instances avec 2 ports
  ou 2 sous-domaines distincts (`api.logirent.ch`, `api.logitime.ch`)

## Désinstallation

```bash
pm2 delete logi-seo-api          # si PM2
sudo systemctl stop logi-seo-api && sudo systemctl disable logi-seo-api   # si systemd
sudo rm -rf /opt/logi-seo-api
```
