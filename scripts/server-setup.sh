#!/usr/bin/env bash
# PatientSynapse — EC2 Server Setup (run ON the server via SSH)
set -euo pipefail

DOMAIN="patientsynapse.com"
APP_DIR="/opt/patientsynapse"

echo "=== PatientSynapse Server Setup ==="

# ---- 1. System packages ----
echo "[1/6] Installing system packages..."
sudo apt update
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y \
  python3.12 python3.12-venv python3.12-dev \
  nodejs npm \
  nginx certbot python3-certbot-nginx \
  tesseract-ocr \
  git

# ---- 2. App directory ----
echo "[2/6] Creating app directory..."
sudo mkdir -p "$APP_DIR"
sudo chown ubuntu:ubuntu "$APP_DIR"
mkdir -p "$APP_DIR/keys" "$APP_DIR/uploads" "$APP_DIR/IncomingFaxes"

# ---- 3. Nginx config ----
echo "[3/6] Configuring nginx..."
sudo tee /etc/nginx/sites-available/patientsynapse > /dev/null <<'NGINX'
server {
    listen 80;
    server_name patientsynapse.com www.patientsynapse.com;

    # Let's Encrypt challenge
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    # Redirect everything else to HTTPS
    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl;
    server_name patientsynapse.com www.patientsynapse.com;

    # SSL certs (certbot will fill these in)
    ssl_certificate /etc/letsencrypt/live/patientsynapse.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/patientsynapse.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    client_max_body_size 50M;

    # ── Public locations (no IP restriction) ────────────────

    # JWKS — must be public (eCW fetches this during OAuth token exchange)
    location /.well-known/jwks.json {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Let's Encrypt ACME challenge — must be public for cert renewal
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    # ── Restricted locations (IP allowlist) ───────────────
    # Run 'bash scripts/update-ip.sh' to set your current IP

    # API routes
    location /api/ {
        allow 0.0.0.0;  # PLACEHOLDER — updated by scripts/update-ip.sh
        deny all;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }

    # FastAPI docs (Swagger/ReDoc)
    location /docs {
        allow 0.0.0.0;
        deny all;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    location /redoc {
        allow 0.0.0.0;
        deny all;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    location /openapi.json {
        allow 0.0.0.0;
        deny all;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Frontend static assets
    location /assets/ {
        allow 0.0.0.0;
        deny all;
        alias /opt/patientsynapse/frontend/dist/assets/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Frontend SPA fallback
    location / {
        allow 0.0.0.0;
        deny all;
        root /opt/patientsynapse/frontend/dist;
        try_files $uri $uri/ /index.html;
    }
}
NGINX

sudo ln -sf /etc/nginx/sites-available/patientsynapse /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test nginx config (will warn about missing SSL certs — that's fine, certbot fixes it)
sudo nginx -t 2>/dev/null || echo "  Nginx config ready (SSL certs needed — run certbot next)"

# ---- 4. SSL Certificate ----
echo "[4/6] Obtaining SSL certificate..."
# Temporarily serve HTTP for Let's Encrypt challenge
sudo tee /etc/nginx/sites-available/patientsynapse-temp > /dev/null <<'TEMPNGINX'
server {
    listen 80;
    server_name patientsynapse.com www.patientsynapse.com;
    location /.well-known/acme-challenge/ { root /var/www/html; }
    location / { return 200 'PatientSynapse setup in progress'; }
}
TEMPNGINX
sudo ln -sf /etc/nginx/sites-available/patientsynapse-temp /etc/nginx/sites-enabled/patientsynapse
sudo systemctl restart nginx

sudo certbot certonly --webroot -w /var/www/html \
  -d "$DOMAIN" \
  --non-interactive --agree-tos --email admin@${DOMAIN} || {
    echo "  Certbot failed — make sure DNS is pointing to this server."
    echo "  You can re-run:  sudo certbot certonly --webroot -w /var/www/html -d $DOMAIN"
  }

# Restore real nginx config
sudo ln -sf /etc/nginx/sites-available/patientsynapse /etc/nginx/sites-enabled/patientsynapse
sudo rm -f /etc/nginx/sites-available/patientsynapse-temp
sudo systemctl restart nginx || echo "  Nginx restart deferred until SSL certs exist"

# ---- 5. Systemd service ----
echo "[5/6] Creating systemd service..."
sudo tee /etc/systemd/system/patientsynapse.service > /dev/null <<SERVICE
[Unit]
Description=PatientSynapse API Server
After=network.target

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/opt/patientsynapse
ExecStart=/opt/patientsynapse/.venv/bin/uvicorn server.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5
EnvironmentFile=/opt/patientsynapse/.env

[Install]
WantedBy=multi-user.target
SERVICE

sudo systemctl daemon-reload
sudo systemctl enable patientsynapse

# ---- 6. Certbot auto-renewal ----
echo "[6/6] Configuring auto-renewal..."
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer

echo ""
echo "=== Server Setup Complete ==="
echo "App directory: $APP_DIR"
echo ""
echo "Next: run 'bash scripts/deploy.sh' from your local machine to push code."
