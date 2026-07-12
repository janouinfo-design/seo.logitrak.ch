#!/usr/bin/env bash
# Sauvegarde quotidienne — application logiseo UNIQUEMENT
# Cron suggéré : 0 2 * * * /opt/logi-seo-booster/scripts/logiseo_backup.sh >> /opt/logi-seo-booster/logs/backup.log 2>&1
set -euo pipefail

APP_DIR="/opt/logi-seo-booster"
BACKUP_DIR="$APP_DIR/backups"
DATE=$(date +%F_%H%M)
RETENTION_DAYS=14

cd "$APP_DIR"
mkdir -p "$BACKUP_DIR"

echo "[logiseo_backup] $DATE — début"

# 1. Dump MongoDB (base logiseo_prod uniquement, via le conteneur logiseo_mongodb)
source .env
docker exec logiseo_mongodb mongodump \
  --username "$MONGO_ROOT_USER" --password "$MONGO_ROOT_PASSWORD" --authenticationDatabase admin \
  --db "$DB_NAME" --archive --gzip > "$BACKUP_DIR/logiseo_db_${DATE}.archive.gz"

# 2. Copie du .env (secrets) — permissions restreintes
cp .env "$BACKUP_DIR/logiseo_env_${DATE}.bak"
chmod 600 "$BACKUP_DIR/logiseo_env_${DATE}.bak"

# 3. Rotation : suppression des sauvegardes logiseo_* de plus de N jours (ce dossier uniquement)
find "$BACKUP_DIR" -name "logiseo_*" -mtime +$RETENTION_DAYS -delete

echo "[logiseo_backup] $DATE — terminé : $(ls -lh "$BACKUP_DIR" | tail -3)"
