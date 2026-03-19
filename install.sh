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

# Virtual Environment Setup (PEP 668 Fix)
echo "[+] SETTING_UP_VENV..."
python3 -m venv .venv || { echo "ERROR: python3-venv is missing. Install it with: apt install python3-venv"; exit 1; }
source .venv/bin/activate

# Install basic dependencies
echo "[+] FETCHING_CORES..."
pip install flask werkzeug requests --quiet

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
  "public": false
}
EOF

# Create initial shares file
if [ ! -f data/shares.json ]; then
    echo "[]" > data/shares.json
fi

echo "===================================="
echo " SLINK READY"
echo "------------------------------------"
echo " ADMIN URL: http://localhost:5119/slink/$SECRET"
echo " USERNAME: $USER"
echo " PASSWORD: $PASS"
echo "===================================="
echo "Run the server with: ./.venv/bin/python main.py serve"
