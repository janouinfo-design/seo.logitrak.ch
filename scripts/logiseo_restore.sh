#!/usr/bin/env bash
# Restauration MongoDB — application logiseo UNIQUEMENT
# Usage : ./logiseo_restore.sh /opt/logi-seo-booster/backups/logiseo_db_2026-07-12_0200.archive.gz
set -euo pipefail

APP_DIR="/opt/logi-seo-booster"
ARCHIVE="${1:?Usage: logiseo_restore.sh <chemin_archive.gz>}"

cd "$APP_DIR"
source .env

echo "⚠️  Restauration de la base $DB_NAME depuis : $ARCHIVE"
echo "    Conteneur cible : logiseo_mongodb (application logiseo uniquement)"
read -p "Confirmer ? (oui/non) " CONFIRM
[ "$CONFIRM" = "oui" ] || { echo "Annulé."; exit 1; }

docker exec -i logiseo_mongodb mongorestore \
  --username "$MONGO_ROOT_USER" --password "$MONGO_ROOT_PASSWORD" --authenticationDatabase admin \
  --archive --gzip --drop --nsInclude="${DB_NAME}.*" < "$ARCHIVE"

echo "✅ Restauration terminée."
