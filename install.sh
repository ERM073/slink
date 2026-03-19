#!/bin/bash
set -e
echo "INIT SLINK_INSTALL..."
mkdir -p storage data templates static

# Install basic dependencies first
echo "[+] FETCHING_CORES..."
pip3 install flask werkzeug requests --quiet

SECRET=$(openssl rand -hex 4)
PASS=$(openssl rand -base64 12)
HAHSED_PASS=$(python3 -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('$PASS'))")

cat <<EOF > data/config.json
{"admin_username": "admin", "admin_password": "$HAHSED_PASS", "admin_secret": "$SECRET"}
EOF

echo "===================================="
echo " SLINK READY"
echo "------------------------------------"
echo " ADMIN URL: http://localhost:5119/slink/$SECRET"
echo " PASSWORD: $PASS"
echo "===================================="
