#!/bin/bash
echo "CAUTION: This will delete all slink data."
read -p "Proceed? (y/N): " confirm
if [[ $confirm == [yY] ]]; then
    rm -rf storage data templates static main.py install.sh uninstall.sh
    echo "WIPED."
fi
