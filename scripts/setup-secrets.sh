#!/usr/bin/env bash
# PatientSynapse — Create or update secrets in AWS Secrets Manager
#
# Usage:
#   bash scripts/setup-secrets.sh                   # Create/update from local .env
#   bash scripts/setup-secrets.sh --env staging      # Use patientsynapse/staging
#   bash scripts/setup-secrets.sh --env production   # Use patientsynapse/production
#   bash scripts/setup-secrets.sh --show             # Print current secret (masked)
#   bash scripts/setup-secrets.sh --delete           # Delete the secret
#
# This reads your local .env file and pushes only the SECRET keys
# (API keys, passwords, client secrets) to Secrets Manager.
# Non-secret config (APP_ENV, LLM_PROVIDER, etc.) stays in the environment.
set -euo pipefail

# Disable AWS CLI pager so output doesn't get stuck in less
export AWS_PAGER=""

REGION="us-east-1"
TARGET_ENV="staging"
ACTION="upsert"

# Keys that are actual secrets (not configuration)
SECRET_KEYS=(
    APP_SECRET_KEY
    ADMIN_DEFAULT_PASSWORD
    ECW_CLIENT_ID
    ECW_JWKS_URL
    ECW_TOKEN_URL
    ECW_AUTHORIZE_URL
    ATHENA_CLIENT_ID
    ATHENA_CLIENT_SECRET
    ATHENA_PRACTICE_ID
    XAI_API_KEY
    OPENAI_API_KEY
    ANTHROPIC_API_KEY
    DATABASE_URL
)

for arg in "$@"; do
    case "$arg" in
        --env)       shift; TARGET_ENV="$1"; shift ;;
        --show)      ACTION="show" ;;
        --delete)    ACTION="delete" ;;
        --help|-h)
            echo "Usage: bash scripts/setup-secrets.sh [--env staging|production] [--show] [--delete]"
            exit 0 ;;
        *)
            if [[ "$arg" != --* ]]; then
                TARGET_ENV="$arg"
            fi ;;
    esac
done

SECRET_ID="patientsynapse/${TARGET_ENV}"

echo "=== Secrets Manager: ${SECRET_ID} (${REGION}) ==="

# ---- Show ----
if [[ "$ACTION" == "show" ]]; then
    echo "Fetching ${SECRET_ID}..."
    RAW=$(aws secretsmanager get-secret-value \
        --secret-id "$SECRET_ID" \
        --region "$REGION" \
        --query 'SecretString' \
        --output text 2>/dev/null) || {
        echo "Secret '${SECRET_ID}' not found."
        exit 1
    }
    # Print keys with masked values
    echo "$RAW" | python3 -c "
import json, sys
d = json.load(sys.stdin)
for k, v in sorted(d.items()):
    masked = v[:4] + '...' + v[-4:] if len(v) > 12 else '****'
    print(f'  {k}: {masked}')
"
    exit 0
fi

# ---- Delete ----
if [[ "$ACTION" == "delete" ]]; then
    read -rp "Delete secret '${SECRET_ID}'? This cannot be undone. [y/N] " confirm
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        aws secretsmanager delete-secret \
            --secret-id "$SECRET_ID" \
            --region "$REGION" \
            --force-delete-without-recovery
        echo "Deleted."
    else
        echo "Cancelled."
    fi
    exit 0
fi

# ---- Upsert (create or update) ----

# Read .env file
ENV_FILE=".env"
if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERROR: No .env file found. Create one first (see .env.example)."
    exit 1
fi

echo "Reading secrets from ${ENV_FILE}..."

# Build JSON from .env, extracting only secret keys
JSON_PAYLOAD=$(python3 -c "
import json, os

env_file = '${ENV_FILE}'
secret_keys = set('${SECRET_KEYS[*]}'.split())

secrets = {}
with open(env_file) as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' not in line:
            continue
        key, _, value = line.partition('=')
        key = key.strip()
        value = value.strip()
        # Remove surrounding quotes if present
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('\"', \"'\"):
            value = value[1:-1]
        if key in secret_keys and value and not value.startswith('<'):
            secrets[key] = value

print(json.dumps(secrets))
")

KEY_COUNT=$(echo "$JSON_PAYLOAD" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))")
echo "  Found ${KEY_COUNT} secrets to store."

if [[ "$KEY_COUNT" == "0" ]]; then
    echo "ERROR: No secret values found in .env. Are the keys populated?"
    exit 1
fi

# Check if secret exists
if aws secretsmanager describe-secret \
    --secret-id "$SECRET_ID" \
    --region "$REGION" > /dev/null 2>&1; then
    EXISTS="yes"
else
    EXISTS="no"
fi

if [[ "$EXISTS" == "yes" ]]; then
    echo "Updating existing secret..."
    aws secretsmanager put-secret-value \
        --secret-id "$SECRET_ID" \
        --region "$REGION" \
        --secret-string "$JSON_PAYLOAD"
else
    echo "Creating new secret..."
    aws secretsmanager create-secret \
        --name "$SECRET_ID" \
        --region "$REGION" \
        --description "PatientSynapse ${TARGET_ENV} secrets — API keys, passwords, client credentials" \
        --secret-string "$JSON_PAYLOAD" \
        --tags "Key=project,Value=patientsynapse" "Key=environment,Value=${TARGET_ENV}"
fi

echo ""
echo "=== Done ==="
echo "Secret ID: ${SECRET_ID}"
echo "Keys stored: ${KEY_COUNT}"
echo ""
echo "Stored keys:"
echo "$JSON_PAYLOAD" | python3 -c "
import json, sys
for k in sorted(json.load(sys.stdin).keys()):
    print(f'  - {k}')
"
echo ""
echo "Your EC2 instance needs the following IAM permission:"
echo "  Action:   secretsmanager:GetSecretValue"
echo "  Resource: arn:aws:secretsmanager:${REGION}:*:secret:${SECRET_ID}-*"
echo ""
echo "To verify: bash scripts/setup-secrets.sh --show --env ${TARGET_ENV}"
