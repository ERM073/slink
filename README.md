# SLINK // Secure Self-Hosted File Transfer

Slink is a lightweight, production-ready, and security-focused file sharing system designed for VPS environments. It features a cyberpunk-inspired dark mode UI, SHA-256 deduplication, and robust admin isolation.

## 🎯 Key Features

- **VPS Safe**: No system service modifications, no auto-running backgrounds.
- **Lightweight**: Pure Python (Flask) with JSON-based storage (no database required).
- **Secure**: Admin panel hidden behind 8-character random secrets, PBKDF2 password hashing, and IP-based brute force protection.
- **Smart Storage**: Files are stored using SHA-256 hashes to prevent duplication.
- **Cyberpunk UI**: Modern dark mode with neon accents and glassmorphism.

## 🚀 Installation

Ensure you have Python 3.10+ installed on your system.

```bash
# Clone the repository (if applicable)
# git clone https://github.com/ERM073/slink.git
# cd slink

# Run the installation script
bash install.sh
```

The installation script will generate your admin credentials and a unique secret path for the dashboard.

## ⚙️ Running the Server

Start the server manually when needed:

```bash
python3 main.py serve
```

Default access:
- **Public URL**: `http://localhost:5119`
- **Admin Dashboard**: `http://localhost:5119/slink/<your-secret-path>`

## 🛠 CLI Usage

You can upload files directly from the command line:

```bash
python3 main.py <file-path> [options]

# Options:
# --password <string> : Protect the share with a password
# --max <number>      : Limit total downloads
# --days <number>     : Set expiration in days
# --ip <CIDR>         : Restrict access to specific IP range
# --qr                : Display an ASCII QR code for the link
```

## 🧨 Uninstallation

To completely remove Slink and all stored data:

```bash
bash uninstall.sh
```

## ⚖️ License

MIT License - See [LICENSE](LICENSE) for details.
