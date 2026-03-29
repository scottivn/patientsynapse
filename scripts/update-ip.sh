#!/usr/bin/env bash
# PatientSynapse — Update nginx IP allowlist with your current public IP
# Usage: bash scripts/update-ip.sh [IP_OR_HOSTNAME]
#
# This updates the 'allow' directives in nginx so only your IP can access
# the app. The JWKS endpoint (/.well-known/jwks.json) stays public because
# eCW needs it for OAuth JWT verification.
#
# Re-run whenever your IP changes (e.g., after reconnecting to WiFi).
set -euo pipefail

SSH_KEY="$HOME/.ssh/patientsynapse-key.pem"
SERVER="${1:-patientsynapse.com}"
SSH_USER="ubuntu"
NGINX_CONF="/etc/nginx/sites-available/patientsynapse"

# Detect current public IP
MY_IP=$(curl -s --max-time 5 https://checkip.amazonaws.com || curl -s --max-time 5 https://ifconfig.me)
if [[ -z "$MY_IP" ]]; then
    echo "ERROR: Could not detect your public IP."
    exit 1
fi

echo "Your public IP: $MY_IP"
echo "Updating nginx on $SERVER ..."

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SSH_USER@$SERVER" \
    "sudo sed -i 's/allow [0-9.\/]\+;/allow $MY_IP;/g' $NGINX_CONF && sudo nginx -t && sudo nginx -s reload"

echo ""
echo "Done. Only $MY_IP can access the app."
echo "  JWKS endpoint remains public (eCW needs it)."
echo ""
echo "Verify:"
echo "  curl https://$SERVER/.well-known/jwks.json   # Should work (public)"
echo "  curl https://$SERVER/api/status               # Should work (your IP)"
