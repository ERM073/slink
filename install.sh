#!/bin/bash
set -e
echo "------------------------------------------------"
echo "  SLINK_OS INITIALIZATION :: PRODUCTION_READY   "
echo "------------------------------------------------"

# Robust Python check
if command -v python3 &> /dev/null; then
    PY="python3"
elif command -v python &> /dev/null; then
    PY="python"
else
    echo "ERROR: Python environment not found. Aborting."
    exit 1
fi

INSTALL_DIR=$(pwd)
mkdir -p storage data templates static

# Virtual Env Setup
echo "[+] DEPLOYING_VIRTUAL_ENVIRONMENT..."
$PY -m venv .venv || { echo "ERROR: python3-venv missing. Required."; exit 1; }
source .venv/bin/activate

# Dependencies
echo "[+] INSTALLING_SYSTEM_DEPENDENCIES..."
pip install flask werkzeug requests pyqrcode pypng --quiet

# Initial Identity Generation
USER="admin"
PASS=$(openssl rand -base64 12)
SECRET=$(openssl rand -hex 6)
HASHED_PASS=$($PY -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('$PASS'))")

cat <<EOF > data/config.json
{
  "admin_username": "$USER",
  "admin_password": "$HASHED_PASS",
  "admin_secret": "$SECRET",
  "public": true
}
EOF

if [ ! -f data/shares.json ]; then echo "[]" > data/shares.json; fi

# Firewall Protocol
echo "[+] OPENING_NETWORK_PORTS (5119, 5120)..."
if command -v ufw &> /dev/null; then
    sudo ufw allow 5119/tcp &> /dev/null || true
    sudo ufw allow 5120/tcp &> /dev/null || true
elif command -v iptables &> /dev/null; then
    sudo iptables -I INPUT -p tcp --dport 5119 -j ACCEPT &> /dev/null || true
    sudo iptables -I INPUT -p tcp --dport 5120 -j ACCEPT &> /dev/null || true
fi

# Global Command Lifecycle
echo "[+] SYMLINKING_GLOBAL_EXECUTABLE..."
cat <<EOF > slink_wrapper
#!/bin/bash
cd $INSTALL_DIR
exec $INSTALL_DIR/.venv/bin/python $INSTALL_DIR/main.py "\$@"
EOF
chmod +x slink_wrapper
sudo mv slink_wrapper /usr/local/bin/slink

# IP Resolution
EXT_IP=$(curl -s https://ifconfig.me || curl -s https://api.ipify.org || echo "NODE_IP")

# Background Execution
echo "[+] STARTING_DUAL_SERVER_CLUSTER..."
pkill -f "main.py serve" || true
nohup /usr/local/bin/slink serve > slink.log 2>&1 &
PID=$!

echo "===================================================="
echo "    SLINK_OS v1.0 DEPLOYED SUCCESSFULLY (PID: $PID)  "
echo "----------------------------------------------------"
echo "  SHARE_NODE:  http://${EXT_IP}:5119"
echo "  ADMIN_NODE:  http://${EXT_IP}:5120/slink/${SECRET}"
echo ""
echo "  USERNAME:    ${USER}"
echo "  PASSWORD:    ${PASS}"
echo "----------------------------------------------------"
echo "  Logs: tail -f slink.log"
echo "===================================================="
