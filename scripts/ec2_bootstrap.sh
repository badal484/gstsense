#!/usr/bin/env bash
# GSTSense — EC2 first-time bootstrap
# Run ONCE after connecting to fresh Ubuntu 22.04 EC2:
#   bash <(curl -s https://raw.githubusercontent.com/badal484/gstsense/main/scripts/ec2_bootstrap.sh)
set -euo pipefail

echo "==> [1/6] Updating system packages..."
sudo apt-get update -qq
sudo apt-get upgrade -y -qq

echo "==> [2/6] Installing Docker..."
sudo apt-get install -y -qq ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update -qq
sudo apt-get install -y -qq docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin

sudo usermod -aG docker ubuntu

echo "==> [3/6] Installing utilities..."
sudo apt-get install -y -qq git curl jq awscli certbot python3 postgresql-client

echo "==> [4/6] Cloning GSTSense repository..."
cd /home/ubuntu
if [ ! -d gstsense ]; then
  git clone https://github.com/badal484/gstsense.git
fi
cd gstsense

echo "==> [5/6] Creating .env from example..."
if [ ! -f backend/.env ]; then
  cp backend/.env.example backend/.env
  echo ""
  echo "  IMPORTANT: Edit backend/.env with your real credentials:"
  echo "  nano /home/ubuntu/gstsense/backend/.env"
  echo ""
fi

echo "==> [6/6] Setting up log rotation..."
sudo tee /etc/logrotate.d/gstsense > /dev/null << 'LOGROTATE'
/home/ubuntu/*.log {
    daily
    rotate 14
    compress
    missingok
    notifempty
}
LOGROTATE

echo ""
echo "==> Bootstrap complete."
echo ""
echo "Next steps:"
echo "  1. Log out and back in (so docker group takes effect):"
echo "     exit"
echo "     ssh -i ~/.ssh/gstsense-key.pem ubuntu@\$(hostname -I | awk '{print \$1}')"
echo ""
echo "  2. Fill in your credentials:"
echo "     nano /home/ubuntu/gstsense/backend/.env"
echo ""
echo "  3. Get SSL certificates (after DNS points to this IP):"
echo "     sudo certbot certonly --standalone -d gstsense.in -d www.gstsense.in -d api.gstsense.in --agree-tos -m your@email.com --non-interactive"
echo ""
echo "  4. Run database migrations:"
echo "     cd /home/ubuntu/gstsense"
echo "     docker compose run --rm backend alembic upgrade head"
echo ""
echo "  5. Start all services:"
echo "     docker compose up -d"
echo ""
echo "  6. Verify:"
echo "     docker compose ps"
echo "     curl http://localhost:8000/health"
