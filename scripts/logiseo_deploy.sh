#!/usr/bin/env bash
# Déploiement / mise à jour — application logiseo UNIQUEMENT
# Ne touche à AUCUNE autre application du VPS.
set -euo pipefail

APP_DIR="/opt/logi-seo-booster"

# --- Garde-fou : vérifier qu'on est dans le bon dossier ---
cd "$APP_DIR"
if [ "$(pwd)" != "$APP_DIR" ]; then
  echo "❌ ERREUR : pas dans $APP_DIR — abandon."; exit 1
fi
echo "📂 Dossier : $(pwd)"
echo "🔗 Remote  : $(git remote -v | head -1)"
echo "🌿 Branche : $(git branch --show-current)"

# --- Sauvegarde avant mise à jour ---
if docker ps --format '{{.Names}}' | grep -q '^logiseo_mongodb$'; then
  echo "💾 Sauvegarde pré-déploiement…"
  ./scripts/logiseo_backup.sh
fi

# --- Mémoriser le commit actuel pour rollback ---
CURRENT_COMMIT=$(git rev-parse --short HEAD)
echo "$CURRENT_COMMIT $(date +%F_%H%M)" >> ./logs/deploy_history.log
echo "🏷  Commit actuel (rollback possible) : $CURRENT_COMMIT"

# --- Mise à jour du code ---
git pull

# --- Build & redémarrage (projet logiseo uniquement) ---
docker compose -p logiseo build
docker compose -p logiseo up -d

# --- Vérification santé ---
sleep 8
echo "🩺 Santé backend :"
curl -fs http://127.0.0.1:8105/api/ && echo " ✅ backend OK" || echo " ❌ backend KO — rollback : git checkout $CURRENT_COMMIT && docker compose -p logiseo build && docker compose -p logiseo up -d"
echo "🩺 Santé frontend :"
curl -fs -o /dev/null -w "%{http_code}" http://127.0.0.1:3105/ && echo " ✅ frontend OK"

echo ""
echo "📋 Conteneurs logiseo :"
docker compose -p logiseo ps
