import os
import sys
import json
import hashlib
import time
import secrets
import argparse
import ipaddress
import threading
from datetime import datetime
from functools import wraps
from flask import Flask, request, send_from_directory, render_template, abort, jsonify, make_response, redirect, url_for
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

# Configuration
STORAGE_DIR = './storage'
DATA_DIR = './data'
SHARES_FILE = os.path.join(DATA_DIR, 'shares.json')
CONFIG_FILE = os.path.join(DATA_DIR, 'config.json')

for d in [STORAGE_DIR, DATA_DIR]: os.makedirs(d, exist_ok=True)

def load_json(path, default=[]):
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f: return json.load(f)
    return default

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f: json.dump(data, f, indent=2)

# --- Dual Apps ---
share_app = Flask(__name__, template_folder='templates', static_folder='static')
admin_app = Flask(__name__, template_folder='templates', static_folder='static')

# Authentication & Rate Limiting
login_attempts = {} # {ip: [count, timestamp]}
blocked_ips = {}    # {ip: timestamp}

def check_admin_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        config = load_json(CONFIG_FILE, {})
        session_token = request.cookies.get('slink_session')
        if session_token != config.get('admin_secret'):
            # Allow initial login via secret path
            if kwargs.get('secret') == config.get('admin_secret'):
                return f(*args, **kwargs)
            abort(404)
        return f(*args, **kwargs)
    return decorated

def is_ip_blocked(ip):
    if ip in blocked_ips:
        if time.time() < blocked_ips[ip]: return True
        del blocked_ips[ip]
    return False

# ----- PUBLIC (SHARE) APP ROUTES -----

@share_app.route('/share/<fhash>/<token>')
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

@share_app.route('/api/dl/<fhash>/<token>')
def download_file(fhash, token):
    shares = load_json(SHARES_FILE)
    share = next((s for s in shares if s['hash'] == fhash and s['token'] == token), None)
    if not share or not share['enabled']: abort(404)
    
    safe_hash = os.path.basename(fhash)
    share['downloads'] += 1
    save_json(SHARES_FILE, shares)
    return send_from_directory(STORAGE_DIR, safe_hash, as_attachment=True, download_name=share['filename'])

@share_app.route('/api/upload', methods=['POST'])
def upload_api():
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
    return jsonify({"url": f"http://{request.host.split(':')[0]}:5119/share/{fhash}/{token}"})

# ----- ADMIN APP ROUTES -----

@admin_app.route('/slink/<secret>', methods=['GET', 'POST'])
def admin_login(secret):
    config = load_json(CONFIG_FILE, {})
    if secret != config.get('admin_secret'): abort(404)
    
    ip = request.remote_addr
    if is_ip_blocked(ip): return "Temporarily blocked due to security violations.", 429

    if request.method == 'POST':
        user = request.form.get('username')
        pw = request.form.get('password')
        if user == config.get('admin_username') and check_password_hash(config.get('admin_password'), pw):
            login_attempts.pop(ip, None)
            resp = make_response(redirect(url_for('admin_dashboard', secret=secret)))
            resp.set_cookie('slink_session', secret, httponly=True, samesite='Strict')
            return resp
        else:
            cnt, _ = login_attempts.get(ip, [0, 0])
            cnt += 1
            login_attempts[ip] = [cnt, time.time()]
            if cnt >= 5: blocked_ips[ip] = time.time() + 3600
            return render_template('login.html', secret=secret, error="AUTHENTICATION_FAILED")

    return render_template('login.html', secret=secret)

@admin_app.route('/slink/<secret>/dashboard')
@check_admin_auth
def admin_dashboard(secret):
    shares = load_json(SHARES_FILE)
    files = []
    for fhash in os.listdir(STORAGE_DIR):
        fpath = os.path.join(STORAGE_DIR, fhash)
        if os.path.isfile(fpath):
            filename = next((s['filename'] for s in shares if s['hash'] == fhash), fhash)
            stats = os.stat(fpath)
            files.append({"hash": fhash, "filename": filename, "size": stats.st_size, "created": stats.st_mtime})
    config = load_json(CONFIG_FILE, {})
    return render_template('dashboard.html', shares=shares, files=files, secret=secret, config=config)

@admin_app.route('/api/admin/<secret>/<action>', methods=['POST'])
@check_admin_auth
def admin_api(secret, action):
    config = load_json(CONFIG_FILE, {})
    if action == 'toggle':
        token = request.json.get('token')
        shares = load_json(SHARES_FILE)
        for s in shares:
            if s['token'] == token: s['enabled'] = not s['enabled']
        save_json(SHARES_FILE, shares)
    elif action == 'delete_token':
        token = request.json.get('token')
        save_json(SHARES_FILE, [s for s in load_json(SHARES_FILE) if s['token'] != token])
    elif action == 'delete_file':
        fhash = request.json.get('hash')
        fpath = os.path.join(STORAGE_DIR, os.path.basename(fhash))
        if os.path.exists(fpath): os.remove(fpath)
        save_json(SHARES_FILE, [s for s in load_json(SHARES_FILE) if s['hash'] != fhash])
    elif action == 'update_settings':
        new_user = request.json.get('username')
        new_pass = request.json.get('password')
        new_secret = request.json.get('secret_path')
        if new_user: config['admin_username'] = new_user
        if new_pass: config['admin_password'] = generate_password_hash(new_pass)
        if new_secret and len(new_secret) >= 4: config['admin_secret'] = secure_filename(new_secret)
        save_json(CONFIG_FILE, config)
        return jsonify({"status": "ok", "new_url": f"/slink/{config['admin_secret']}/dashboard"})
    
    return jsonify({"status": "ok"})

@admin_app.route('/api/admin/dl/<secret>/<fhash>')
@check_admin_auth
def admin_download(secret, fhash):
    filename = next((s['filename'] for s in load_json(SHARES_FILE) if s['hash'] == fhash), fhash)
    return send_from_directory(STORAGE_DIR, os.path.basename(fhash), as_attachment=True, download_name=filename)

# --- Common Utilities ---
@share_app.template_filter('datetime')
@admin_app.template_filter('datetime')
def format_dt(v): return datetime.fromtimestamp(v).strftime('%Y-%m-%d %H:%M')

@admin_app.template_filter('filesize')
def format_fs(s):
    for u in ['B','KB','MB','GB']:
        if s < 1024: return f"{s:.1f} {u}"
        s /= 1024
    return f"{s:.1f} TB"

def run_share(): share_app.run(port=5119, host='0.0.0.0', debug=False)
def run_admin(): admin_app.run(port=5120, host='0.0.0.0', debug=False)

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] != 'serve':
        # Simple CLI Placeholder
        print("Slink CLI - Not in server mode")
    else:
        print("// SLINK NODE BOOTING...")
        print("SHARE SERVER: http://0.0.0.0:5119")
        print("ADMIN SERVER: http://0.0.0.0:5120")
        t1 = threading.Thread(target=run_share)
        t2 = threading.Thread(target=run_admin)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
