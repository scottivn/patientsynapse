#!/usr/bin/env bash
# PatientSynapse — Deploy from local machine to EC2
# Usage: bash scripts/deploy.sh [IP_OR_HOSTNAME]
set -euo pipefail

SSH_KEY="$HOME/.ssh/patientsynapse-key.pem"
SERVER="${1:-patientsynapse.com}"
SSH_USER="ubuntu"
APP_DIR="/opt/patientsynapse"
SSH_CMD="ssh -i $SSH_KEY -o StrictHostKeyChecking=no $SSH_USER@$SERVER"
SCP_CMD="scp -i $SSH_KEY -o StrictHostKeyChecking=no"

echo "=== Deploying PatientSynapse to $SERVER ==="

# ---- 1. Build frontend ----
echo "[1/5] Building frontend..."
cd frontend
npm install --silent
npm run build
cd ..

# ---- 2. Sync code to server ----
echo "[2/5] Syncing code..."
rsync -avz --delete \
  -e "ssh -i $SSH_KEY -o StrictHostKeyChecking=no" \
  --exclude '.venv' \
  --exclude 'node_modules' \
  --exclude '.git' \
  --exclude '.env' \
  --exclude 'keys/' \
  --exclude 'IncomingFaxes/' \
  --exclude '__pycache__' \
  --exclude '.DS_Store' \
  ./ "$SSH_USER@$SERVER:$APP_DIR/"

# ---- 3. Copy .env (only if it doesn't exist on server) ----
echo "[3/5] Checking .env..."
$SSH_CMD "test -f $APP_DIR/.env" 2>/dev/null || {
  echo "  Copying .env to server (first deploy)..."
  $SCP_CMD .env "$SSH_USER@$SERVER:$APP_DIR/.env"
}
echo "  To update .env: scp -i $SSH_KEY .env $SSH_USER@$SERVER:$APP_DIR/.env"

# ---- 4. Install Python deps on server ----
echo "[4/5] Installing dependencies on server..."
$SSH_CMD <<'REMOTE'
cd /opt/patientsynapse
python3.12 -m venv .venv 2>/dev/null || true
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
mkdir -p keys uploads IncomingFaxes
REMOTE

# ---- 5. Restart service ----
echo "[5/5] Restarting service..."
$SSH_CMD "sudo systemctl restart patientsynapse && sudo systemctl restart nginx"

# Verify
echo ""
echo "Waiting 3 seconds for startup..."
sleep 3
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "https://$SERVER/.well-known/jwks.json" 2>/dev/null || echo "000")

if [ "$HTTP_STATUS" = "200" ]; then
  echo "=== Deploy Successful ==="
  echo "  App:  https://$SERVER"
  echo "  API:  https://$SERVER/api/status"
  echo "  JWKS: https://$SERVER/.well-known/jwks.json"
else
  echo "=== Deploy Complete (JWKS returned HTTP $HTTP_STATUS) ==="
  echo "  Check logs: ssh -i $SSH_KEY $SSH_USER@$SERVER 'sudo journalctl -u patientsynapse -n 50'"
fi
