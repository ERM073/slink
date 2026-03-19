import os
import sys
import json
import hashlib
import time
import secrets
import argparse
import ipaddress
from datetime import datetime
from functools import wraps
from flask import Flask, request, send_from_directory, render_template, abort, jsonify, make_response, redirect, url_for
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
STORAGE_DIR = './storage'
DATA_DIR = './data'
SHARES_FILE = os.path.join(DATA_DIR, 'shares.json')
CONFIG_FILE = os.path.join(DATA_DIR, 'config.json')

# Init system
for d in [STORAGE_DIR, DATA_DIR]: os.makedirs(d, exist_ok=True)

# Rate limiter
login_attempts = {}
blocked_ips = {}

def load_json(path, default=[]):
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f: return json.load(f)
    return default

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f: json.dump(data, f, indent=2)

def check_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        config = load_json(CONFIG_FILE, {})
        auth_cookie = request.cookies.get('slink_session')
        if auth_cookie != config.get('admin_secret'):
            if kwargs.get('secret') == config.get('admin_secret'): return f(*args, **kwargs)
            abort(404)
        return f(*args, **kwargs)
    return decorated

def is_blocked(ip):
    if ip in blocked_ips:
        if time.time() < blocked_ips[ip]: return True
        del blocked_ips[ip]
    return False

@app.route('/share/<fhash>/<token>')
def download_page(fhash, token):
    shares = load_json(SHARES_FILE)
    share = next((s for s in shares if s['hash'] == fhash and s['token'] == token), None)
    if not share or not share['enabled']: abort(404)
    if share.get('max_downloads') and share['downloads'] >= share['max_downloads']: abort(404)
    if share.get('expires') and time.time() > share['expires']: abort(404)
    
    # IP check
    if share.get('ip_limit'):
        try:
            if request.remote_addr not in ipaddress.ip_network(share['ip_limit']): abort(403)
        except: pass

    # Preview logic
    preview = None
    is_img = False
    ext = os.path.splitext(share['filename'])[1].lower()
    if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']: is_img = True
    elif ext in ['.txt', '.log', '.py', '.js', '.html', '.md']:
        try:
            with open(os.path.join(STORAGE_DIR, fhash), 'r', encoding='utf-8') as f:
                preview = f.read(2048)
        except: pass

    return render_template('download.html', share=share, is_image=is_img, preview=preview)

@app.route('/api/dl/<fhash>/<token>')
def download_file(fhash, token):
    shares = load_json(SHARES_FILE)
    share = next((s for s in shares if s['hash'] == fhash and s['token'] == token), None)
    if not share or not share['enabled']: abort(404)
    
    safe_hash = os.path.basename(fhash)
    share['downloads'] += 1
    save_json(SHARES_FILE, shares)
    return send_from_directory(STORAGE_DIR, safe_hash, as_attachment=True, download_name=share['filename'])

@app.route('/slink/<secret>', methods=['GET', 'POST'])
def admin_portal(secret):
    config = load_json(CONFIG_FILE, {})
    if secret != config.get('admin_secret'): abort(404)
    
    ip = request.remote_addr
    if is_blocked(ip): return "Blocked", 429

    if request.method == 'POST':
        user = request.form.get('username')
        pw = request.form.get('password')
        if user == config.get('admin_username') and check_password_hash(config.get('admin_password'), pw):
            login_attempts.pop(ip, None)
            resp = make_response(redirect(url_for('dashboard', secret=secret)))
            resp.set_cookie('slink_session', secret, httponly=True)
            return resp
        else:
            cnt, _ = login_attempts.get(ip, [0, 0])
            cnt += 1
            login_attempts[ip] = [cnt, time.time()]
            if cnt >= 5: blocked_ips[ip] = time.time() + 3600
            return render_template('login.html', secret=secret, error="INVALID")

    return render_template('login.html', secret=secret)

@app.route('/slink/<secret>/dashboard')
@check_auth
def dashboard(secret):
    shares = load_json(SHARES_FILE)
    return render_template('dashboard.html', shares=shares, secret=secret)

@app.route('/api/upload', methods=['POST'])
def upload():
    file = request.files.get('file')
    if not file: return jsonify({"error": "No file"}), 400
    content = file.read()
    fhash = hashlib.sha256(content).hexdigest()
    with open(os.path.join(STORAGE_DIR, fhash), 'wb') as f: f.write(content)
    
    token = secrets.token_hex(4)
    shares = load_json(SHARES_FILE)
    days = request.form.get('days')
    expiry = time.time() + (int(days) * 86400) if days and int(days) > 0 else None
    
    shares.append({
        "hash": fhash, "token": token, "filename": secure_filename(file.filename),
        "downloads": 0, "max_downloads": int(request.form.get('max', 0)),
        "expires": expiry, "enabled": True, "password": request.form.get('password', ''),
        "ip_limit": request.form.get('ip', '')
    })
    save_json(SHARES_FILE, shares)
    return jsonify({"url": f"{request.host_url.rstrip('/')}/share/{fhash}/{token}"})

@app.template_filter('datetime')
def format_datetime(value):
    return datetime.fromtimestamp(value).strftime('%Y-%m-%d %H:%M')

def cli():
    p = argparse.ArgumentParser()
    p.add_argument('file')
    p.add_argument('--max', type=int, default=0)
    p.add_argument('--days', type=int, default=0)
    p.add_argument('--qr', action='store_true')
    args = p.parse_args()
    # Simple direct upload if running locally
    print(f"Uploading {args.file}...")

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] != 'serve': cli()
    else: app.run(port=5119, host='127.0.0.1')
