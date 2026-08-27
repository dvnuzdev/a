#!/bin/bash
# ==============================================================================
# OpenBudget Telegram Bot — Oracle Cloud Infrastructure (OCI) Auto-Installer
# OS Target: Ubuntu 20.04 / 22.04 / 24.04 LTS
# ==============================================================================

set -e

echo "🚀 Starting OpenBudget Telegram Bot Oracle Cloud Deployment Setup..."

# 1. Update system packages
echo "📦 Updating Ubuntu system packages..."
sudo apt update -y
sudo apt install -y curl git ufw

# 2. Configure Ubuntu Firewall for Ports 80, 443, 22
echo "🛡 Configuring Firewall (Ports 80, 443, 22)..."
sudo ufw allow 22/tcp || true
sudo ufw allow 80/tcp || true
sudo ufw allow 443/tcp || true

# 3. Build and launch Docker Compose services
echo "⚡️ Building & Launching Docker Compose containers (Bot, Postgres, Redis, Nginx)..."
sudo docker compose up -d --build

echo ""
echo "=============================================================================="
echo "🎉 OPENBUDGET BOT SUCCESSFULLY DEPLOYED ON ORACLE CLOUD!"
echo "=============================================================================="
echo "📊 Service Status:"
sudo docker compose ps
echo ""
echo "📝 View logs anytime with: sudo docker compose logs -f bot1"
echo "=============================================================================="
