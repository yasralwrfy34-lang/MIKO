import os
import json
import re
import subprocess
import psutil
import socket
import sys
import hashlib
import secrets
import time
import threading
import requests
from datetime import datetime, timedelta
from flask import Flask, send_from_directory, request, jsonify, session, redirect, url_for, make_response, render_template_string

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_DIR = os.path.join(BASE_DIR, "USERS")
os.makedirs(USERS_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

# Global State
USERS_FILE = os.path.join(BASE_DIR, "users.json")
SUPPORT_CHAT_FILE = os.path.join(BASE_DIR, "support_chat.json")
ADMIN_USERNAME = "elmodmen"
ADMIN_PASSWORD = "amar1212"

# Helper Functions
def load_users():
    if not os.path.exists(USERS_FILE): return {}
    with open(USERS_FILE, "r", encoding="utf-8") as f: return json.load(f)

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f: json.dump(users, f, indent=2)

def is_admin(username):
    return username == ADMIN_USERNAME

# Routes
@app.route('/')
def index():
    if 'username' not in session: return redirect(url_for('login_page'))
    if is_admin(session['username']): return redirect(url_for('admin_page'))
    try:
        with open(os.path.join(BASE_DIR, "index.html"), "r", encoding="utf-8") as f:
            return f.read()
    except:
        return "Index file missing. Please contact admin."

@app.route('/login')
def login_page():
    try:
        with open(os.path.join(BASE_DIR, "login.html"), "r", encoding="utf-8") as f:
            return f.read()
    except:
        return "Login file missing."

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    u, p = data.get('username'), data.get('password')
    if u == ADMIN_USERNAME and p == ADMIN_PASSWORD:
        session['username'] = u
        return jsonify({"success": True, "redirect": "/admin"})
    users = load_users()
    if u in users and users[u]['password'] == p:
        session['username'] = u
        return jsonify({"success": True, "redirect": "/"})
    return jsonify({"success": False, "message": "بيانات غير صحيحة"})

@app.route('/api/logout')
def api_logout():
    session.clear()
    return redirect(url_for('login_page'))

@app.route('/admin')
def admin_page():
    if 'username' not in session or not is_admin(session['username']):
        return redirect(url_for('login_page'))
    try:
        with open(os.path.join(BASE_DIR, "admin_panel.html"), "r", encoding="utf-8") as f:
            return f.read()
    except:
        return "Admin panel file missing."

@app.route('/api/user/info')
def user_info():
    if 'username' not in session: return jsonify({"username": "Guest"})
    return jsonify({"username": session['username']})

# File Management APIs
@app.route('/api/files/list')
def list_files():
    if 'username' not in session: return jsonify({"files": []})
    user_dir = os.path.join(USERS_DIR, session['username'])
    os.makedirs(user_dir, exist_ok=True)
    files = []
    for f in os.listdir(user_dir):
        path = os.path.join(user_dir, f)
        if os.path.isfile(path):
            stat = os.stat(path)
            files.append({
                "name": f,
                "size": f"{stat.st_size / 1024:.1f} KB",
                "time": datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
            })
    return jsonify({"files": files})

@app.route('/api/files/read', methods=['POST'])
def read_file():
    if 'username' not in session: return jsonify({"error": "Unauthorized"}), 403
    data = request.get_json()
    filename = data.get('filename')
    if not filename or '..' in filename: return jsonify({"error": "Invalid filename"}), 400
    
    user_dir = os.path.join(USERS_DIR, session['username'])
    path = os.path.join(user_dir, filename)
    if not os.path.exists(path): return jsonify({"error": "File not found"}), 404
    
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return jsonify({"content": f.read()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Support Chat API
@app.route('/api/support/send', methods=['POST'])
def send_support():
    if 'username' not in session: return jsonify({"success": False}), 403
    data = request.get_json()
    msg = data.get('message', '').strip()
    if not msg: return jsonify({"success": False})
    
    chats = {}
    if os.path.exists(SUPPORT_CHAT_FILE):
        with open(SUPPORT_CHAT_FILE, "r", encoding="utf-8") as f: chats = json.load(f)
    
    user = session['username']
    if user not in chats: chats[user] = []
    chats[user].append({"sender": user, "message": msg, "time": datetime.now().isoformat()})
    
    with open(SUPPORT_CHAT_FILE, "w", encoding="utf-8") as f: json.dump(chats, f, indent=2, ensure_ascii=False)
    return jsonify({"success": True})

@app.route('/api/support/messages')
def get_support():
    if 'username' not in session: return jsonify({"messages": []})
    if not os.path.exists(SUPPORT_CHAT_FILE): return jsonify({"messages": []})
    with open(SUPPORT_CHAT_FILE, "r", encoding="utf-8") as f: chats = json.load(f)
    return jsonify({"messages": chats.get(session['username'], [])})

# AI Chat API (DeepSeek)
@app.route('/api/ai/chat', methods=['POST'])
def ai_chat():
    data = request.get_json()
    user_msg = data.get('message', '').strip()
    if not user_msg:
        return jsonify({"success": False, "message": "رسالة فارغة"})

    api_key = "DarkAI-DeepAI-EFF939A9130A0ABAE3A7414D"
    model = "v3" # v3 للنموذج السريع، r1 للنموذج المفكر
    
    try:
        # استخدام API الخاص بـ DarkAI/DeepSeek
        response = requests.post(
            "https://api.darkai.foundation/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "أنت مساعد ذكي وخبير في البرمجة وإدارة السيرفرات، اسمك مساعد OMAR BRO HOST. أجب باللغة العربية دائماً وبشكل احترافي."},
                    {"role": "user", "content": user_msg}
                ],
                "stream": False
            },
            timeout=30
        )
        
        if response.status_code == 200:
            ai_res = response.json()
            content = ai_res['choices'][0]['message']['content']
            return jsonify({"success": True, "reply": content})
        else:
            return jsonify({"success": False, "message": f"خطأ من المزود: {response.status_code}"})
            
    except Exception as e:
        return jsonify({"success": False, "message": f"فشل الاتصال بالذكاء الاصطناعي: {str(e)}"})

# Metrics API
@app.route('/api/system/metrics')
def get_metrics():
    return jsonify({
        "cpu": psutil.cpu_percent(),
        "memory": psutil.virtual_memory().percent,
        "disk": psutil.disk_usage('/').percent
    })

# Keep-Alive Ping
@app.route('/api/ping')
def ping():
    return jsonify({"status": "alive", "time": datetime.now().isoformat()})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
