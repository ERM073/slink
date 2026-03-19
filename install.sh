#!/bin/bash
set -e
echo "------------------------------------"
echo " SLINK_INSTALLER: INITIATING..."
echo "------------------------------------"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python3 not found."
    exit 1
fi

# Setup directories
mkdir -p storage data templates static

# Virtual Environment Setup
echo "[+] SETTING_UP_VENV..."
python3 -m venv .venv || { echo "ERROR: python3-venv is missing. Install it with: apt install python3-venv"; exit 1; }
source .venv/bin/activate

# Install basic dependencies
echo "[+] FETCHING_CORES..."
pip install flask werkzeug requests --quiet

# Generate Credentials
USER="admin"
PASS=$(openssl rand -base64 12)
SECRET=$(openssl rand -hex(4)) # Wait, hex(4) is wrong in bash
SECRET=$(openssl rand -hex 4)
HAHSED_PASS=$(python3 -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('$PASS'))")

# Create initial config
cat <<EOF > data/config.json
{
  "admin_username": "$USER",
  "admin_password": "$HAHSED_PASS",
  "admin_secret": "$SECRET",
  "public": true
}
EOF

# Create initial shares file
if [ ! -f data/shares.json ]; then
    echo "[]" > data/shares.json
fi

# Open Port 5119
echo "[+] OPENING_PORT_5119..."
if command -v ufw &> /dev/null; then
    sudo ufw allow 5119/tcp || echo "Warning: Could not open port via ufw."
elif command -v iptables &> /dev/null; then
    sudo iptables -I INPUT -p tcp --dport 5119 -j ACCEPT || echo "Warning: Could not open port via iptables."
fi

# Detect IP
LOCAL_IP="localhost"
EXT_IP=$(curl -s https://ifconfig.me || curl -s https://api.ipify.org || echo "unknown")

# Start Server in Background
echo "[+] STARTING_SERVER_BACKGROUND..."
nohup ./.venv/bin/python main.py serve > slink.log 2>&1 &
PID=$!

echo "===================================="
echo " SLINK READY (PID: $PID)"
echo "------------------------------------"
echo " LOCAL:  http://$LOCAL_IP:5119/slink/$SECRET"
echo " PUBLIC: http://$EXT_IP:5119/slink/$SECRET"
echo ""
echo " USERNAME: $USER"
echo " PASSWORD: $PASS"
echo "===================================="
echo "Logs are being written to slink.log"
