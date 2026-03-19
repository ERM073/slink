#!/bin/bash
set -e
echo "------------------------------------"
echo " SLINK_INSTALLER: INITIATING..."
echo "------------------------------------"

# Check Python
if ! command -v python3 & { echo "ERROR: Python3 not found."; exit 1; }; then
    : # python3 exists
fi

# Setup directories
INSTALL_DIR=$(pwd)
mkdir -p storage data templates static

# Virtual Environment Setup
echo "[+] SETTING_UP_VENV..."
python3 -m venv .venv || { echo "ERROR: python3-venv missing. apt install python3-venv"; exit 1; }
source .venv/bin/activate

# Install basic dependencies
echo "[+] FETCHING_CORES..."
pip install flask werkzeug requests pyqrcode pypng --quiet

# Generate Credentials
USER="admin"
PASS=$(openssl rand -base64 12)
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
if [ ! -f data/shares.json ]; then echo "[]" > data/shares.json; fi

# Open Port 5119
echo "[+] OPENING_PORT_5119..."
if command -v ufw &> /dev/null; then
    sudo ufw allow 5119/tcp || true
elif command -v iptables &> /dev/null; then
    sudo iptables -I INPUT -p tcp --dport 5119 -j ACCEPT || true
fi

# Global Command Setup
echo "[+] CREATING_GLOBAL_COMMAND..."
cat <<EOF > slink_wrapper
#!/bin/bash
cd $INSTALL_DIR
exec $INSTALL_DIR/.venv/bin/python $INSTALL_DIR/main.py "\$@"
EOF
chmod +x slink_wrapper
sudo mv slink_wrapper /usr/local/bin/slink

# Detect IP
LOCAL_IP="localhost"
EXT_IP=$(curl -s https://ifconfig.me || curl -s https://api.ipify.org || echo "unknown")

# Kill existing slink if any
pkill -f "main.py serve" || true

# Start Server in Background
echo "[+] STARTING_SERVER_BACKGROUND..."
nohup /usr/local/bin/slink serve > slink.log 2>&1 &
PID=$!

echo "===================================="
echo " SLINK READY (PID: $PID)"
echo "------------------------------------"
echo " LOCAL:  http://$LOCAL_IP:5119/slink/$SECRET"
echo " PUBLIC: http://$EXT_IP:5119/slink/$SECRET"
echo ""
echo " COMMAND: slink <file>"
echo " USERNAME: $USER"
echo " PASSWORD: $PASS"
echo "===================================="
