#!/usr/bin/env bash
# PatientSynapse — Deploy from local machine to EC2
# Usage:
#   bash scripts/deploy.sh                  # Deploy to patientsynapse.com
#   bash scripts/deploy.sh [hostname]       # Deploy to specific host
#   bash scripts/deploy.sh --update-env     # Push .env to server and restart
#   bash scripts/deploy.sh --update-ip      # Update nginx IP allowlist
set -euo pipefail

SSH_KEY="$HOME/.ssh/patientsynapse-key.pem"
SSH_USER="ubuntu"
APP_DIR="/opt/patientsynapse"

# Parse arguments
SERVER="patientsynapse.com"
ACTION="deploy"
for arg in "$@"; do
  case "$arg" in
    --update-env) ACTION="update-env" ;;
    --update-ip)  ACTION="update-ip" ;;
    --*)          echo "Unknown flag: $arg"; exit 1 ;;
    *)            SERVER="$arg" ;;
  esac
done

SSH_CMD="ssh -i $SSH_KEY -o StrictHostKeyChecking=no $SSH_USER@$SERVER"
SCP_CMD="scp -i $SSH_KEY -o StrictHostKeyChecking=no"

# ---- Quick actions (no full deploy) ----

if [[ "$ACTION" == "update-env" ]]; then
    echo "→ Updating .env on $SERVER..."
    $SCP_CMD .env "$SSH_USER@$SERVER:$APP_DIR/.env"
    $SSH_CMD "sudo systemctl restart patientsynapse"
    echo "  .env updated and service restarted."
    exit 0
fi

if [[ "$ACTION" == "update-ip" ]]; then
    exec bash scripts/update-ip.sh "$SERVER"
fi

# ---- Full deploy ----

echo "=== Deploying PatientSynapse to $SERVER ==="

# ---- 0. Pre-flight checks ----
echo "[0/6] Pre-flight checks..."

if [[ ! -f "$SSH_KEY" ]]; then
    echo "  ERROR: SSH key not found at $SSH_KEY"
    exit 1
fi

$SSH_CMD "echo ok" > /dev/null 2>&1 || {
    echo "  ERROR: Cannot SSH to $SERVER"
    echo "  Is the instance running? Try:"
    echo "    aws ec2 start-instances --instance-ids i-0981c6d653020fb71 --region us-east-1"
    exit 1
}
echo "  SSH: OK"

# ---- 1. Build frontend ----
echo "[1/6] Building frontend..."
cd frontend
npm install --silent
npm run build
cd ..

# ---- 2. Sync code to server ----
echo "[2/6] Syncing code..."
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
echo "[3/6] Checking .env..."
$SSH_CMD "test -f $APP_DIR/.env" 2>/dev/null || {
  echo "  Copying .env to server (first deploy)..."
  $SCP_CMD .env "$SSH_USER@$SERVER:$APP_DIR/.env"
}
echo "  To update .env later: bash scripts/deploy.sh --update-env"
echo "  Secrets stored in AWS Secrets Manager: bash scripts/setup-secrets.sh --show"

# ---- 4. Copy RSA keys (only if they don't exist on server) ----
echo "[4/6] Checking RSA keys..."
$SSH_CMD "test -f $APP_DIR/keys/private_key.pem" 2>/dev/null || {
  if [[ -f keys/private_key.pem ]]; then
    echo "  Copying RSA keys to server (first deploy)..."
    $SCP_CMD keys/private_key.pem "$SSH_USER@$SERVER:$APP_DIR/keys/"
    $SCP_CMD keys/public_key.pem "$SSH_USER@$SERVER:$APP_DIR/keys/"
  else
    echo "  WARNING: No local keys/private_key.pem — JWKS will auto-generate on first start"
  fi
}

# ---- 5. Install Python deps on server ----
echo "[5/6] Installing dependencies on server..."
$SSH_CMD <<'REMOTE'
cd /opt/patientsynapse
python3.12 -m venv .venv 2>/dev/null || true
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
mkdir -p keys uploads IncomingFaxes
REMOTE

# ---- 6. Restart service ----
echo "[6/6] Restarting service..."
$SSH_CMD "sudo systemctl restart patientsynapse && sudo systemctl restart nginx"

# ---- Verify ----
echo ""
echo "Waiting 3 seconds for startup..."
sleep 3

# Check JWKS (public, always works)
JWKS_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "https://$SERVER/.well-known/jwks.json" 2>/dev/null || echo "000")

# Check API status (may 403 if IP not yet allowed)
API_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "https://$SERVER/api/status" 2>/dev/null || echo "000")
API_BODY=$(curl -s "https://$SERVER/api/status" 2>/dev/null || echo "{}")

if [[ "$JWKS_STATUS" == "200" ]]; then
    echo "=== Deploy Successful ==="
    echo "  JWKS:   https://$SERVER/.well-known/jwks.json  [HTTP $JWKS_STATUS]"
    echo "  Status: https://$SERVER/api/status  [HTTP $API_STATUS]"
    if [[ "$API_STATUS" == "200" ]]; then
        echo "  $API_BODY"
    elif [[ "$API_STATUS" == "403" ]]; then
        echo ""
        echo "  App is IP-restricted. Run to allow your IP:"
        echo "    bash scripts/update-ip.sh"
    fi
    echo ""
    echo "  App:    https://$SERVER"
    echo "  Docs:   https://$SERVER/docs"
    echo "  Logs:   ssh -i $SSH_KEY $SSH_USER@$SERVER 'sudo journalctl -u patientsynapse -n 50'"
else
    echo "=== Deploy Complete (JWKS returned HTTP $JWKS_STATUS) ==="
    echo "  The service may still be starting up, or SSL certs may need renewal."
    echo "  Check logs: ssh -i $SSH_KEY $SSH_USER@$SERVER 'sudo journalctl -u patientsynapse -n 50'"
fi
