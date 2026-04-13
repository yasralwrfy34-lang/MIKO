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
import shutil
import zipfile
import signal
from datetime import datetime, timedelta
from flask import Flask, send_from_directory, request, jsonify, session, redirect, url_for, make_response

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_DIR = os.path.join(BASE_DIR, "USERS")
os.makedirs(USERS_DIR, exist_ok=True)

app = Flask(__name__, static_folder=BASE_DIR)
app.secret_key = secrets.token_hex(32)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# ============== بيانات المسؤول ==============
ADMIN_USERNAME = "yasralwrfy"
ADMIN_PASSWORD_RAW = "amiailafu"

# ============== قاعدة البيانات ==============
DB_FILE = os.path.join(BASE_DIR, "db.json")

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    admin_hash = hashlib.sha256(ADMIN_PASSWORD_RAW.encode()).hexdigest()
    default_db = {
        "users": {
            ADMIN_USERNAME: {
                "password": admin_hash,
                "is_admin": True,
                "created_at": str(datetime.now()),
                "max_servers": 999999,
                "expiry_days": 3650,
                "last_login": None,
                "telegram_id": None,
                "api_key": None
            }
        },
        "servers": {},
        "logs": []
    }
    save_db(default_db)
    return default_db

def save_db(db_data):
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(db_data, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"❌ خطأ: {e}")
        return False

db = load_db()

# ============== المنافذ ==============
PORT_RANGE_START = 8100
PORT_RANGE_END = 9100

def get_assigned_port():
    used = set()
    for srv in db.get("servers", {}).values():
        if srv.get("port"):
            used.add(srv["port"])
    for port in range(PORT_RANGE_START, PORT_RANGE_END):
        if port not in used:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.1)
                result = s.connect_ex(('127.0.0.1', port))
                s.close()
                if result != 0:
                    return port
            except:
                return port
    return PORT_RANGE_START

# ============== مراقبة العمليات ==============
def process_monitor():
    while True:
        try:
            for folder, srv in list(db["servers"].items()):
                if srv.get("status") == "Running" and srv.get("pid"):
                    try:
                        p = psutil.Process(srv["pid"])
                        if not p.is_running() or p.status() == psutil.STATUS_ZOMBIE:
                            restart_server(folder)
                    except psutil.NoSuchProcess:
                        restart_server(folder)
                    except:
                        pass
        except:
            pass
        time.sleep(15)

def restart_server(folder):
    srv = db["servers"].get(folder)
    if not srv:
        return
    if srv.get("pid"):
        try:
            p = psutil.Process(srv["pid"])
            if hasattr(os, 'killpg'):
                try:
                    os.killpg(os.getpgid(p.pid), signal.SIGTERM)
                except:
                    pass
            for child in p.children(recursive=True):
                child.kill()
            p.kill()
        except:
            pass
    srv["status"] = "Stopped"
    srv["pid"] = None
    save_db(db)
    time.sleep(2)
    start_server_process(folder)

def start_server_process(folder):
    srv = db["servers"].get(folder)
    if not srv:
        return False
    main_file = srv.get("startup_file", "")
    if not main_file:
        py_files = [f for f in os.listdir(srv["path"]) if f.endswith('.py') and f not in ['out.log', 'meta.json']]
        if py_files:
            main_file = py_files[0]
            srv["startup_file"] = main_file
            save_db(db)
        else:
            return False
    file_path = os.path.join(srv["path"], main_file)
    if not os.path.exists(file_path):
        return False
    port = srv.get("port")
    if not port:
        port = get_assigned_port()
        srv["port"] = port
        save_db(db)
    log_path = os.path.join(srv["path"], "out.log")
    log_file = open(log_path, "a", encoding='utf-8')
    log_file.write(f"\n{'='*50}\n🚀 بدء التشغيل - {datetime.now()}\n📁 {main_file}\n🔌 المنفذ: {port}\n{'='*50}\n\n")
    log_file.flush()
    try:
        env = os.environ.copy()
        env["PORT"] = str(port)
        env["SERVER_PORT"] = str(port)
        proc = subprocess.Popen(
            [sys.executable, "-u", main_file],
            cwd=srv["path"],
            stdout=log_file,
            stderr=subprocess.STDOUT,
            env=env,
            preexec_fn=os.setsid if hasattr(os, 'setsid') else None
        )
        srv["status"] = "Running"
        srv["pid"] = proc.pid
        srv["start_time"] = time.time()
        save_db(db)
        return True
    except Exception as e:
        log_file.write(f"\n❌ خطأ: {str(e)}\n")
        log_file.close()
        return False

threading.Thread(target=process_monitor, daemon=True).start()

def get_current_user():
    if "username" in session:
        return db["users"].get(session["username"])
    return None

def get_user_servers_dir(username):
    path = os.path.join(USERS_DIR, username, "SERVERS")
    os.makedirs(path, exist_ok=True)
    return path

def is_admin(username):
    if username == ADMIN_USERNAME:
        return True
    u = db["users"].get(username)
    return u.get("is_admin", False) if u else False

def get_public_ip():
    try:
        return requests.get('https://api.ipify.org', timeout=3).text
    except:
        try:
            return requests.get('https://icanhazip.com', timeout=3).text.strip()
        except:
            return "127.0.0.1"

# ============== دوال API Key ==============
def generate_api_key():
    return secrets.token_urlsafe(32)

def get_user_by_api_key(api_key):
    for username, udata in db["users"].items():
        if udata.get("api_key") == api_key:
            return username, udata
    return None, None

# ============== الصفحات ==============
@app.route('/')
def home():
    if 'username' not in session:
        return redirect('/login')
    user = get_current_user()
    if user and user.get("is_admin"):
        return redirect('/admin')
    return redirect('/dashboard')

@app.route('/login')
def login_page():
    if 'username' in session:
        return redirect('/')
    return send_from_directory(BASE_DIR, 'login.html')

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect('/login')
    return send_from_directory(BASE_DIR, 'index.html')

@app.route('/admin')
def admin_panel():
    if 'username' not in session or not is_admin(session['username']):
        return redirect('/login')
    return send_from_directory(BASE_DIR, 'admin_panel.html')

# ============== API المصادقة ==============
@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    if not username or not password:
        return jsonify({"success": False, "message": "جميع الحقول مطلوبة"})
    if len(username) < 3:
        return jsonify({"success": False, "message": "اسم المستخدم 3 أحرف على الأقل"})
    if len(password) < 4:
        return jsonify({"success": False, "message": "كلمة المرور 4 أحرف على الأقل"})
    if username in db["users"]:
        return jsonify({"success": False, "message": "اسم المستخدم موجود"})
    if username == ADMIN_USERNAME:
        return jsonify({"success": False, "message": "لا يمكن استخدام هذا الاسم"})
    db["users"][username] = {
        "password": hashlib.sha256(password.encode()).hexdigest(),
        "is_admin": False,
        "created_at": str(datetime.now()),
        "max_servers": 1,
        "expiry_days": 365,
        "last_login": None,
        "telegram_id": None,
        "api_key": None
    }
    save_db(db)
    user_dir = os.path.join(USERS_DIR, username)
    os.makedirs(user_dir, exist_ok=True)
    os.makedirs(os.path.join(user_dir, "SERVERS"), exist_ok=True)
    return jsonify({"success": True, "message": "تم إنشاء الحساب"})

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD_RAW:
        session.clear()
        session['username'] = username
        session.permanent = True
        return jsonify({"success": True, "redirect": "/admin", "is_admin": True})
    user = db["users"].get(username)
    if user and user["password"] == hashlib.sha256(password.encode()).hexdigest():
        session.clear()
        session['username'] = username
        session.permanent = True
        user["last_login"] = str(datetime.now())
        save_db(db)
        return jsonify({"success": True, "redirect": "/dashboard", "is_admin": False})
    return jsonify({"success": False, "message": "بيانات غير صحيحة"})

@app.route('/api/logout', methods=['GET', 'POST'])
def api_logout():
    session.clear()
    response = make_response(jsonify({"success": True}))
    response.set_cookie('session', '', expires=0)
    return response

@app.route('/api/current_user')
def api_current_user():
    if "username" in session:
        u = db["users"].get(session["username"])
        if u:
            return jsonify({
                "success": True,
                "username": session["username"],
                "is_admin": u.get("is_admin", False) or session["username"] == ADMIN_USERNAME
            })
    return jsonify({"success": False})

# ============== API إنشاء API Key ==============
@app.route('/api/create_api_key', methods=['POST'])
def create_api_key():
    if 'username' not in session:
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    username = session['username']
    new_key = generate_api_key()
    db["users"][username]["api_key"] = new_key
    save_db(db)
    return jsonify({"success": True, "api_key": new_key, "message": "تم إنشاء مفتاح API"})

@app.route('/api/link_telegram', methods=['POST'])
def link_telegram():
    if 'username' not in session:
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json()
    tg_id = str(data.get('telegram_id'))
    if not tg_id:
        return jsonify({"success": False, "message": "معرف تليجرام مطلوب"})
    db["users"][session['username']]["telegram_id"] = tg_id
    save_db(db)
    return jsonify({"success": True, "message": "تم ربط حساب التليجرام"})

# ============== API للبوت (التحكم عبر API Key أو telegram_id) ==============
@app.route('/api/bot/verify', methods=['POST'])
def bot_verify():
    data = request.get_json()
    api_key = data.get('api_key', '').strip()
    if not api_key:
        return jsonify({"success": False, "message": "API Key مطلوب"})
    username, user = get_user_by_api_key(api_key)
    if not username:
        return jsonify({"success": False, "message": "API Key غير صالح"})
    return jsonify({
        "success": True,
        "username": username,
        "is_admin": user.get("is_admin", False),
        "max_servers": user.get("max_servers", 1),
        "expiry_days": user.get("expiry_days", 365)
    })

@app.route('/api/bot/servers', methods=['GET'])
def bot_list_servers():
    api_key = request.args.get('api_key')
    if not api_key:
        return jsonify({"success": False, "message": "API Key مطلوب"}), 401
    username, _ = get_user_by_api_key(api_key)
    if not username:
        return jsonify({"success": False, "message": "API Key غير صالح"}), 401
    user_servers = []
    for folder, srv in db["servers"].items():
        if srv["owner"] == username:
            uptime_str = "0 ثانية"
            if srv.get("status") == "Running" and srv.get("start_time"):
                diff = time.time() - srv["start_time"]
                days = int(diff // 86400)
                hours = int((diff % 86400) // 3600)
                mins = int((diff % 3600) // 60)
                parts = []
                if days > 0: parts.append(f"{days} يوم")
                if hours > 0: parts.append(f"{hours} ساعة")
                if mins > 0: parts.append(f"{mins} دقيقة")
                uptime_str = " و ".join(parts) if parts else "أقل من دقيقة"
            user_servers.append({
                "folder": folder,
                "title": srv["name"],
                "status": srv.get("status", "Stopped"),
                "uptime": uptime_str,
                "port": srv.get("port", "N/A"),
                "plan": srv.get("plan", "free"),
                "storage_limit": srv.get("storage_limit", 100),
                "ram_limit": srv.get("ram_limit", 256),
                "cpu_limit": srv.get("cpu_limit", 0.5)
            })
    return jsonify({"success": True, "servers": user_servers})

@app.route('/api/bot/server/action', methods=['POST'])
def bot_server_action():
    data = request.get_json()
    api_key = data.get('api_key')
    folder = data.get('folder')
    action = data.get('action')
    if not api_key or not folder or not action:
        return jsonify({"success": False, "message": "بيانات ناقصة"}), 400
    username, _ = get_user_by_api_key(api_key)
    if not username:
        return jsonify({"success": False, "message": "API Key غير صالح"}), 401
    srv = db["servers"].get(folder)
    if not srv or srv["owner"] != username:
        return jsonify({"success": False, "message": "غير مصرح"}), 403
    if action == "start":
        if srv.get("status") == "Running":
            return jsonify({"success": False, "message": "السيرفر يعمل بالفعل"})
        if start_server_process(folder):
            return jsonify({"success": True, "message": "✅ تم التشغيل"})
        else:
            return jsonify({"success": False, "message": "فشل التشغيل - تأكد من وجود ملف تشغيل"})
    elif action == "stop":
        if srv.get("pid"):
            try:
                p = psutil.Process(srv["pid"])
                if hasattr(os, 'killpg'):
                    try:
                        os.killpg(os.getpgid(p.pid), signal.SIGTERM)
                    except:
                        pass
                for child in p.children(recursive=True):
                    child.kill()
                p.kill()
            except:
                pass
        srv["status"] = "Stopped"
        srv["pid"] = None
        save_db(db)
        return jsonify({"success": True, "message": "🛑 تم الإيقاف"})
    elif action == "restart":
        restart_server(folder)
        return jsonify({"success": True, "message": "✅ تم إعادة التشغيل"})
    elif action == "delete":
        if srv.get("pid"):
            try:
                p = psutil.Process(srv["pid"])
                if hasattr(os, 'killpg'):
                    try:
                        os.killpg(os.getpgid(p.pid), signal.SIGTERM)
                    except:
                        pass
                for child in p.children(recursive=True):
                    child.kill()
                p.kill()
            except:
                pass
        if os.path.exists(srv["path"]):
            try:
                shutil.rmtree(srv["path"])
            except:
                try:
                    subprocess.run(["rm", "-rf", srv["path"]], timeout=5)
                except:
                    pass
        del db["servers"][folder]
        save_db(db)
        return jsonify({"success": True, "message": "🗑️ تم الحذف"})
    else:
        return jsonify({"success": False, "message": "إجراء غير معروف"})

@app.route('/api/bot/console', methods=['GET'])
def bot_console():
    api_key = request.args.get('api_key')
    folder = request.args.get('folder')
    if not api_key or not folder:
        return jsonify({"success": False, "message": "بيانات ناقصة"}), 400
    username, _ = get_user_by_api_key(api_key)
    if not username:
        return jsonify({"success": False, "message": "API Key غير صالح"}), 401
    srv = db["servers"].get(folder)
    if not srv or srv["owner"] != username:
        return jsonify({"success": False, "message": "غير مصرح"}), 403
    log_path = os.path.join(srv["path"], "out.log")
    logs = "لا توجد مخرجات بعد"
    if os.path.exists(log_path):
        try:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.read().split('\n')
                logs = '\n'.join(lines[-500:])
        except:
            pass
    return jsonify({"success": True, "logs": logs})

@app.route('/api/bot/files/list', methods=['GET'])
def bot_files_list():
    api_key = request.args.get('api_key')
    folder = request.args.get('folder')
    path = request.args.get('path', '')
    if not api_key or not folder:
        return jsonify({"success": False, "message": "بيانات ناقصة"}), 400
    username, _ = get_user_by_api_key(api_key)
    if not username:
        return jsonify({"success": False, "message": "API Key غير صالح"}), 401
    srv = db["servers"].get(folder)
    if not srv or srv["owner"] != username:
        return jsonify({"success": False, "message": "غير مصرح"}), 403
    base_path = srv["path"]
    target_path = os.path.join(base_path, path) if path else base_path
    if '..' in target_path or not target_path.startswith(base_path):
        return jsonify({"success": False, "message": "مسار غير صالح"}), 400
    files = []
    try:
        for f in os.listdir(target_path):
            if f in ['out.log', 'server.log', 'meta.json']:
                continue
            fpath = os.path.join(target_path, f)
            stat = os.stat(fpath)
            size_bytes = stat.st_size
            if size_bytes < 1024:
                size_str = f"{size_bytes} B"
            elif size_bytes < 1024*1024:
                size_str = f"{size_bytes/1024:.1f} KB"
            else:
                size_str = f"{size_bytes/(1024*1024):.1f} MB"
            files.append({
                "name": f,
                "size": size_str,
                "is_dir": os.path.isdir(fpath),
                "path": os.path.join(path, f) if path else f
            })
    except:
        pass
    return jsonify({"success": True, "files": files, "current_path": path})

@app.route('/api/bot/files/content', methods=['GET'])
def bot_file_content():
    api_key = request.args.get('api_key')
    folder = request.args.get('folder')
    file_path = request.args.get('file_path')
    if not api_key or not folder or not file_path:
        return jsonify({"success": False, "message": "بيانات ناقصة"}), 400
    username, _ = get_user_by_api_key(api_key)
    if not username:
        return jsonify({"success": False, "message": "API Key غير صالح"}), 401
    srv = db["servers"].get(folder)
    if not srv or srv["owner"] != username:
        return jsonify({"success": False, "message": "غير مصرح"}), 403
    full_path = os.path.join(srv["path"], file_path)
    if '..' in full_path or not full_path.startswith(srv["path"]):
        return jsonify({"success": False, "message": "مسار غير صالح"}), 400
    if not os.path.exists(full_path) or os.path.isdir(full_path):
        return jsonify({"success": False, "message": "ملف غير موجود أو مجلد"}), 404
    try:
        with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        return jsonify({"success": True, "content": content})
    except:
        return jsonify({"success": False, "message": "فشل قراءة الملف"}), 500

@app.route('/api/bot/files/save', methods=['POST'])
def bot_file_save():
    data = request.get_json()
    api_key = data.get('api_key')
    folder = data.get('folder')
    file_path = data.get('file_path')
    content = data.get('content', '')
    if not api_key or not folder or not file_path:
        return jsonify({"success": False, "message": "بيانات ناقصة"}), 400
    username, _ = get_user_by_api_key(api_key)
    if not username:
        return jsonify({"success": False, "message": "API Key غير صالح"}), 401
    srv = db["servers"].get(folder)
    if not srv or srv["owner"] != username:
        return jsonify({"success": False, "message": "غير مصرح"}), 403
    full_path = os.path.join(srv["path"], file_path)
    if '..' in full_path or not full_path.startswith(srv["path"]):
        return jsonify({"success": False, "message": "مسار غير صالح"}), 400
    try:
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return jsonify({"success": True, "message": "تم الحفظ بنجاح"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/bot/files/delete', methods=['POST'])
def bot_file_delete():
    data = request.get_json()
    api_key = data.get('api_key')
    folder = data.get('folder')
    file_path = data.get('file_path')
    if not api_key or not folder or not file_path:
        return jsonify({"success": False, "message": "بيانات ناقصة"}), 400
    username, _ = get_user_by_api_key(api_key)
    if not username:
        return jsonify({"success": False, "message": "API Key غير صالح"}), 401
    srv = db["servers"].get(folder)
    if not srv or srv["owner"] != username:
        return jsonify({"success": False, "message": "غير مصرح"}), 403
    full_path = os.path.join(srv["path"], file_path)
    if '..' in full_path or not full_path.startswith(srv["path"]):
        return jsonify({"success": False, "message": "مسار غير صالح"}), 400
    try:
        if os.path.isdir(full_path):
            shutil.rmtree(full_path)
        else:
            os.remove(full_path)
        return jsonify({"success": True, "message": "تم الحذف بنجاح"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/bot/files/upload', methods=['POST'])
def bot_file_upload():
    api_key = request.form.get('api_key')
    folder = request.form.get('folder')
    file_path = request.form.get('file_path', '')
    uploaded_file = request.files.get('file')
    if not api_key or not folder or not uploaded_file:
        return jsonify({"success": False, "message": "بيانات ناقصة"}), 400
    username, _ = get_user_by_api_key(api_key)
    if not username:
        return jsonify({"success": False, "message": "API Key غير صالح"}), 401
    srv = db["servers"].get(folder)
    if not srv or srv["owner"] != username:
        return jsonify({"success": False, "message": "غير مصرح"}), 403
    target_dir = os.path.join(srv["path"], file_path) if file_path else srv["path"]
    if '..' in target_dir or not target_dir.startswith(srv["path"]):
        return jsonify({"success": False, "message": "مسار غير صالح"}), 400
    os.makedirs(target_dir, exist_ok=True)
    filename = uploaded_file.filename
    if '..' in filename:
        return jsonify({"success": False, "message": "اسم ملف غير صالح"}), 400
    full_path = os.path.join(target_dir, filename)
    uploaded_file.save(full_path)
    return jsonify({"success": True, "message": f"تم رفع {filename}"})

@app.route('/api/bot/files/create_folder', methods=['POST'])
def bot_create_folder():
    data = request.get_json()
    api_key = data.get('api_key')
    folder = data.get('folder')
    folder_name = data.get('folder_name')
    current_path = data.get('current_path', '')
    if not api_key or not folder or not folder_name:
        return jsonify({"success": False, "message": "بيانات ناقصة"}), 400
    username, _ = get_user_by_api_key(api_key)
    if not username:
        return jsonify({"success": False, "message": "API Key غير صالح"}), 401
    srv = db["servers"].get(folder)
    if not srv or srv["owner"] != username:
        return jsonify({"success": False, "message": "غير مصرح"}), 403
    target_dir = os.path.join(srv["path"], current_path, folder_name)
    if '..' in target_dir or not target_dir.startswith(srv["path"]):
        return jsonify({"success": False, "message": "مسار غير صالح"}), 400
    os.makedirs(target_dir, exist_ok=True)
    return jsonify({"success": True, "message": f"تم إنشاء المجلد {folder_name}"})

@app.route('/api/bot/install', methods=['POST'])
def bot_install():
    data = request.get_json()
    api_key = data.get('api_key')
    folder = data.get('folder')
    if not api_key or not folder:
        return jsonify({"success": False, "message": "بيانات ناقصة"}), 400
    username, _ = get_user_by_api_key(api_key)
    if not username:
        return jsonify({"success": False, "message": "API Key غير صالح"}), 401
    srv = db["servers"].get(folder)
    if not srv or srv["owner"] != username:
        return jsonify({"success": False, "message": "غير مصرح"}), 403
    req_file = os.path.join(srv["path"], "requirements.txt")
    if not os.path.exists(req_file):
        return jsonify({"success": False, "message": "requirements.txt غير موجود"}), 404
    try:
        log_path = os.path.join(srv["path"], "out.log")
        with open(log_path, "a", encoding='utf-8') as log_file:
            log_file.write(f"\n{'='*50}\n📦 بدء تثبيت المكتبات عبر API...\n{'='*50}\n")
        proc = subprocess.Popen(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            cwd=srv["path"],
            stdout=open(log_path, "a", encoding='utf-8'),
            stderr=subprocess.STDOUT
        )
        def wait_install():
            proc.wait()
            with open(log_path, "a", encoding='utf-8') as log_file:
                if proc.returncode == 0:
                    log_file.write("\n✅ تم التثبيت بنجاح!\n")
                else:
                    log_file.write("\n❌ فشل التثبيت\n")
        threading.Thread(target=wait_install, daemon=True).start()
        return jsonify({"success": True, "message": "بدأ تثبيت المكتبات"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/bot/set_startup', methods=['POST'])
def bot_set_startup():
    data = request.get_json()
    api_key = data.get('api_key')
    folder = data.get('folder')
    filename = data.get('filename')
    if not api_key or not folder or not filename:
        return jsonify({"success": False, "message": "بيانات ناقصة"}), 400
    username, _ = get_user_by_api_key(api_key)
    if not username:
        return jsonify({"success": False, "message": "API Key غير صالح"}), 401
    srv = db["servers"].get(folder)
    if not srv or srv["owner"] != username:
        return jsonify({"success": False, "message": "غير مصرح"}), 403
    file_path = os.path.join(srv["path"], filename)
    if not os.path.exists(file_path):
        return jsonify({"success": False, "message": "الملف غير موجود"}), 404
    srv["startup_file"] = filename
    save_db(db)
    return jsonify({"success": True, "message": f"تم تعيين {filename} كملف التشغيل"})

# ============== API إنشاء سيرفر للبوت ==============
@app.route('/api/bot/create_server', methods=['POST'])
def bot_create_server():
    data = request.get_json()
    api_key = data.get('api_key')
    name = data.get('name', 'خادمي').strip()
    plan_id = data.get('plan', 'free')
    storage_limit = int(data.get('storage', 100))
    ram_limit = int(data.get('ram', 256))
    cpu_limit = float(data.get('cpu', 0.5))
    if not api_key:
        return jsonify({"success": False, "message": "API Key مطلوب"}), 400
    username, user = get_user_by_api_key(api_key)
    if not username:
        return jsonify({"success": False, "message": "API Key غير صالح"}), 401
    user_srv_count = len([s for s in db["servers"].values() if s["owner"] == username])
    max_allowed = user.get("max_servers", 1)
    if user_srv_count >= max_allowed:
        return jsonify({"success": False, "message": f"لقد وصلت للحد الأقصى ({max_allowed}) من السيرفرات"})
    folder = f"{username}_{re.sub(r'[^a-zA-Z0-9]', '', name)}_{int(time.time())}"
    path = os.path.join(get_user_servers_dir(username), folder)
    os.makedirs(path, exist_ok=True)
    assigned_port = get_assigned_port()
    db["servers"][folder] = {
        "name": name,
        "owner": username,
        "path": path,
        "type": "Python",
        "status": "Stopped",
        "created_at": str(datetime.now()),
        "startup_file": "",
        "pid": None,
        "port": assigned_port,
        "plan": plan_id,
        "storage_limit": storage_limit,
        "ram_limit": ram_limit,
        "cpu_limit": cpu_limit
    }
    save_db(db)
    return jsonify({"success": True, "message": f"✅ تم إنشاء السيرفر {name}", "folder": folder, "port": assigned_port})

# ============== API المسؤول ==============
@app.route('/api/admin/users')
def admin_users():
    if "username" not in session or not is_admin(session["username"]):
        return jsonify({"success": False}), 403
    users_list = []
    for uname, udata in db["users"].items():
        users_list.append({
            "username": uname,
            "is_admin": udata.get("is_admin", False),
            "created_at": udata.get("created_at"),
            "last_login": udata.get("last_login"),
            "max_servers": udata.get("max_servers", 1),
            "expiry_days": udata.get("expiry_days", 365),
            "telegram_id": udata.get("telegram_id"),
            "api_key": udata.get("api_key")
        })
    return jsonify({"success": True, "users": users_list})

@app.route('/api/admin/delete-user', methods=['POST'])
def admin_delete_user():
    if "username" not in session or not is_admin(session["username"]):
        return jsonify({"success": False}), 403
    data = request.get_json()
    username = data.get("username", "").strip()
    if not username or username == ADMIN_USERNAME:
        return jsonify({"success": False, "message": "لا يمكن حذف هذا المستخدم"})
    if username in db["users"]:
        servers_to_delete = [fid for fid, srv in db["servers"].items() if srv["owner"] == username]
        for fid in servers_to_delete:
            srv = db["servers"][fid]
            if srv.get("pid"):
                try:
                    p = psutil.Process(srv["pid"])
                    p.terminate()
                except:
                    pass
            if os.path.exists(srv["path"]):
                try:
                    shutil.rmtree(srv["path"])
                except:
                    pass
            del db["servers"][fid]
        user_dir = os.path.join(USERS_DIR, username)
        if os.path.exists(user_dir):
            try:
                shutil.rmtree(user_dir)
            except:
                pass
        del db["users"][username]
        save_db(db)
        return jsonify({"success": True, "message": f"🗑️ تم حذف المستخدم {username}"})
    return jsonify({"success": False, "message": "المستخدم غير موجود"})

# ============== API النظام ==============
@app.route('/api/system/metrics')
def get_metrics():
    return jsonify({
        "cpu": psutil.cpu_percent(),
        "memory": psutil.virtual_memory().percent,
        "disk": psutil.disk_usage('/').percent
    })

@app.route('/api/ping', methods=['GET', 'POST'])
def ping():
    return jsonify({"status": "pong", "timestamp": str(datetime.now())})

# ============== السيرفرات (للواجهة العادية) ==============
@app.route('/api/servers')
def list_servers():
    if "username" not in session:
        return jsonify({"success": False}), 401
    user_servers = []
    total_disk_used = 0
    total_disk_limit = 0
    for folder, srv in db["servers"].items():
        if srv["owner"] == session["username"]:
            disk_used = 0
            if os.path.exists(srv["path"]):
                for root, dirs, files in os.walk(srv["path"]):
                    for f in files:
                        fp = os.path.join(root, f)
                        if os.path.exists(fp):
                            disk_used += os.path.getsize(fp)
            disk_used_mb = disk_used / (1024 * 1024)
            storage_limit = srv.get("storage_limit", 100)
            total_disk_used += disk_used_mb
            total_disk_limit += storage_limit
            uptime_str = "0 ثانية"
            if srv.get("status") == "Running" and srv.get("start_time"):
                diff = time.time() - srv["start_time"]
                days = int(diff // 86400)
                hours = int((diff % 86400) // 3600)
                mins = int((diff % 3600) // 60)
                parts = []
                if days > 0: parts.append(f"{days} يوم")
                if hours > 0: parts.append(f"{hours} ساعة")
                if mins > 0: parts.append(f"{mins} دقيقة")
                uptime_str = " و ".join(parts) if parts else "أقل من دقيقة"
            user_servers.append({
                "folder": folder,
                "title": srv["name"],
                "subtitle": f"سيرفر {srv.get('type', 'Python')}",
                "startup_file": srv.get("startup_file", ""),
                "status": srv.get("status", "Stopped"),
                "uptime": uptime_str,
                "port": srv.get("port", "N/A"),
                "plan": srv.get("plan", "free"),
                "storage_limit": storage_limit,
                "ram_limit": srv.get("ram_limit", 256),
                "cpu_limit": srv.get("cpu_limit", 0.5),
                "disk_used": round(disk_used_mb, 2)
            })
    user = db["users"].get(session["username"], {"max_servers": 1, "expiry_days": 365})
    max_srv = 1
    return jsonify({
        "success": True,
        "servers": user_servers,
        "stats": {
            "used": len(user_servers),
            "total": max_srv,
            "expiry": user.get("expiry_days", 365),
            "disk_used": round(total_disk_used, 2),
            "disk_total": total_disk_limit
        }
    })

@app.route('/api/server/add', methods=['POST'])
def add_server():
    if "username" not in session:
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    user = db["users"].get(session["username"])
    if not user:
        return jsonify({"success": False, "message": "مستخدم غير موجود"})
    user_srv_count = len([s for s in db["servers"].values() if s["owner"] == session["username"]])
    if user_srv_count >= 1:
        return jsonify({"success": False, "message": "يمكنك امتلاك خادم واحد فقط. قم بحذف الخادم الحالي أولاً."})
    data = request.get_json()
    name = data.get("name", "My Server").strip()
    plan_id = data.get("plan", "free")
    storage_limit = int(data.get("storage", 100))
    ram_limit = int(data.get("ram", 256))
    cpu_limit = float(data.get("cpu", 0.5))
    if not name:
        name = "Server_" + secrets.token_hex(2)
    folder = f"{session['username']}_{re.sub(r'[^a-zA-Z0-9]', '', name)}_{int(time.time())}"
    path = os.path.join(get_user_servers_dir(session["username"]), folder)
    os.makedirs(path, exist_ok=True)
    assigned_port = get_assigned_port()
    db["servers"][folder] = {
        "name": name,
        "owner": session["username"],
        "path": path,
        "type": "Python",
        "status": "Stopped",
        "created_at": str(datetime.now()),
        "startup_file": "",
        "pid": None,
        "port": assigned_port,
        "plan": plan_id,
        "storage_limit": storage_limit,
        "ram_limit": ram_limit,
        "cpu_limit": cpu_limit
    }
    save_db(db)
    return jsonify({"success": True, "message": f"✅ تم إنشاء الخادم {name}"})

@app.route('/api/server/action/<folder>/<action>', methods=['POST'])
def server_action(folder, action):
    if "username" not in session:
        return jsonify({"success": False}), 401
    srv = db["servers"].get(folder)
    if not srv or srv["owner"] != session["username"]:
        return jsonify({"success": False, "message": "غير مصرح"})
    if action == "start":
        if srv.get("status") == "Running":
            return jsonify({"success": False, "message": "الخادم يعمل بالفعل"})
        if start_server_process(folder):
            return jsonify({"success": True, "message": "✅ تم التشغيل"})
        else:
            return jsonify({"success": False, "message": "فشل التشغيل - تأكد من وجود ملف تشغيل"})
    elif action == "stop":
        if srv.get("pid"):
            try:
                p = psutil.Process(srv["pid"])
                if hasattr(os, 'killpg'):
                    try:
                        os.killpg(os.getpgid(p.pid), signal.SIGTERM)
                    except:
                        pass
                for child in p.children(recursive=True):
                    child.kill()
                p.kill()
            except:
                pass
        srv["status"] = "Stopped"
        srv["pid"] = None
        save_db(db)
        return jsonify({"success": True, "message": "🛑 تم الإيقاف"})
    elif action == "restart":
        restart_server(folder)
        return jsonify({"success": True, "message": "✅ تم إعادة التشغيل"})
    elif action == "delete":
        if srv.get("pid"):
            try:
                p = psutil.Process(srv["pid"])
                if hasattr(os, 'killpg'):
                    try:
                        os.killpg(os.getpgid(p.pid), signal.SIGTERM)
                    except:
                        pass
                for child in p.children(recursive=True):
                    child.kill()
                p.kill()
            except:
                pass
        if os.path.exists(srv["path"]):
            try:
                shutil.rmtree(srv["path"])
            except:
                try:
                    subprocess.run(["rm", "-rf", srv["path"]], timeout=5)
                except:
                    pass
        del db["servers"][folder]
        save_db(db)
        return jsonify({"success": True, "message": "🗑️ تم الحذف"})
    return jsonify({"success": False})

@app.route('/api/server/stats/<folder>')
def get_server_stats(folder):
    if "username" not in session:
        return jsonify({"success": False}), 401
    srv = db["servers"].get(folder)
    if not srv or srv["owner"] != session["username"]:
        return jsonify({"success": False})
    status = srv.get("status", "Stopped")
    logs = "لا توجد مخرجات بعد"
    log_path = os.path.join(srv["path"], "out.log")
    if os.path.exists(log_path):
        try:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.read().split('\n')
                logs = '\n'.join(lines[-500:])
        except:
            pass
    mem_info = "0 MB"
    if srv.get("pid") and status == "Running":
        try:
            p = psutil.Process(srv["pid"])
            mem_mb = p.memory_info().rss / (1024 * 1024)
            mem_info = f"{mem_mb:.1f} MB"
        except:
            pass
    uptime_str = "0 ثانية"
    if status == "Running" and srv.get("start_time"):
        diff = time.time() - srv["start_time"]
        days = int(diff // 86400)
        hours = int((diff % 86400) // 3600)
        mins = int((diff % 3600) // 60)
        parts = []
        if days > 0: parts.append(f"{days} يوم")
        if hours > 0: parts.append(f"{hours} ساعة")
        if mins > 0: parts.append(f"{mins} دقيقة")
        uptime_str = " و ".join(parts) if parts else "أقل من دقيقة"
    return jsonify({
        "success": True,
        "status": status,
        "logs": logs,
        "mem": mem_info,
        "uptime": uptime_str,
        "port": srv.get("port", "--"),
        "ip": get_public_ip()
    })

# ============== API الملفات ==============
@app.route('/api/files/list/<folder>')
def list_server_files(folder):
    if "username" not in session:
        return jsonify([]), 401
    srv = db["servers"].get(folder)
    if not srv or srv["owner"] != session["username"]:
        return jsonify([])
    path = srv["path"]
    files = []
    try:
        for f in os.listdir(path):
            if f in ['out.log', 'server.log', 'meta.json']:
                continue
            fpath = os.path.join(path, f)
            stat = os.stat(fpath)
            size_bytes = stat.st_size
            if size_bytes < 1024:
                size_str = f"{size_bytes} B"
            elif size_bytes < 1024*1024:
                size_str = f"{size_bytes/1024:.1f} KB"
            else:
                size_str = f"{size_bytes/(1024*1024):.1f} MB"
            files.append({"name": f, "size": size_str, "is_dir": os.path.isdir(fpath), "modified": datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')})
    except:
        pass
    return jsonify(sorted(files, key=lambda x: (not x['is_dir'], x['name'].lower())))

@app.route('/api/files/content/<folder>/<filename>')
def get_file_content(folder, filename):
    if "username" not in session:
        return jsonify({"content": ""}), 401
    srv = db["servers"].get(folder)
    if not srv or srv["owner"] != session["username"]:
        return jsonify({"content": ""})
    if '..' in filename:
        return jsonify({"content": ""})
    fpath = os.path.join(srv["path"], filename)
    if not os.path.exists(fpath) or os.path.isdir(fpath):
        return jsonify({"content": ""})
    try:
        with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
            return jsonify({"content": f.read()})
    except:
        return jsonify({"content": "[ملف ثنائي]"})

@app.route('/api/files/save/<folder>/<filename>', methods=['POST'])
def save_file_content(folder, filename):
    if "username" not in session:
        return jsonify({"success": False}), 401
    srv = db["servers"].get(folder)
    if not srv or srv["owner"] != session["username"]:
        return jsonify({"success": False})
    if '..' in filename:
        return jsonify({"success": False, "message": "اسم غير صالح"})
    data = request.get_json()
    content = data.get("content", "")
    fpath = os.path.join(srv["path"], filename)
    try:
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(content)
        return jsonify({"success": True, "message": "✅ تم الحفظ"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/files/create/<folder>', methods=['POST'])
def create_file(folder):
    if "username" not in session:
        return jsonify({"success": False}), 401
    srv = db["servers"].get(folder)
    if not srv or srv["owner"] != session["username"]:
        return jsonify({"success": False})
    data = request.get_json()
    filename = data.get("filename", "").strip()
    content = data.get("content", "")
    if not filename or '..' in filename:
        return jsonify({"success": False, "message": "اسم غير صالح"})
    fpath = os.path.join(srv["path"], filename)
    try:
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(content)
        return jsonify({"success": True, "message": f"✅ تم إنشاء {filename}"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/files/delete/<folder>', methods=['POST'])
def delete_files(folder):
    if "username" not in session:
        return jsonify({"success": False}), 401
    srv = db["servers"].get(folder)
    if not srv or srv["owner"] != session["username"]:
        return jsonify({"success": False})
    data = request.get_json() or {}
    names = data.get("names", data.get("name", []))
    if isinstance(names, str):
        names = [names]
    if not names:
        return jsonify({"success": False, "message": "لم يتم تحديد ملفات"})
    deleted = 0
    for name in names:
        if not name or '..' in name:
            continue
        fpath = os.path.join(srv["path"], name)
        try:
            if os.path.isdir(fpath):
                shutil.rmtree(fpath)
            elif os.path.exists(fpath):
                os.remove(fpath)
            deleted += 1
        except:
            pass
    if deleted > 0:
        return jsonify({"success": True, "message": f"🗑️ تم حذف {deleted} ملف"})
    else:
        return jsonify({"success": False, "message": "فشل الحذف"})

@app.route('/api/files/upload/<folder>', methods=['POST'])
def upload_files(folder):
    if "username" not in session:
        return jsonify({"success": False}), 401
    srv = db["servers"].get(folder)
    if not srv or srv["owner"] != session["username"]:
        return jsonify({"success": False})
    if not os.path.exists(srv["path"]):
        os.makedirs(srv["path"], exist_ok=True)
    files = request.files.getlist('files[]')
    if not files:
        return jsonify({"success": False, "message": "لا توجد ملفات"})
    uploaded = 0
    for f in files:
        try:
            if not f or not f.filename:
                continue
            if '..' in f.filename:
                continue
            save_path = os.path.join(srv["path"], f.filename)
            f.save(save_path)
            if f.filename.lower().endswith('.zip'):
                try:
                    with zipfile.ZipFile(save_path, 'r') as z:
                        z.extractall(srv["path"])
                except:
                    pass
            uploaded += 1
        except:
            pass
    if uploaded > 0:
        return jsonify({"success": True, "message": f"✅ تم رفع {uploaded} ملف"})
    else:
        return jsonify({"success": False, "message": "فشل الرفع"})

@app.route('/api/files/unzip/<folder>/<filename>', methods=['POST'])
def unzip_file(folder, filename):
    if "username" not in session:
        return jsonify({"success": False}), 401
    srv = db["servers"].get(folder)
    if not srv or srv["owner"] != session["username"]:
        return jsonify({"success": False})
    if '..' in filename or not filename.lower().endswith('.zip'):
        return jsonify({"success": False, "message": "ملف غير صالح"})
    fpath = os.path.join(srv["path"], filename)
    if not os.path.exists(fpath):
        return jsonify({"success": False, "message": "الملف غير موجود"})
    try:
        with zipfile.ZipFile(fpath, 'r') as z:
            z.extractall(srv["path"])
        return jsonify({"success": True, "message": "✅ تم فك الضغط"})
    except Exception as e:
        return jsonify({"success": False, "message": f"❌ فشل: {str(e)}"})

@app.route('/api/server/set-startup/<folder>', methods=['POST'])
def set_startup_file(folder):
    if "username" not in session:
        return jsonify({"success": False}), 401
    srv = db["servers"].get(folder)
    if not srv or srv["owner"] != session["username"]:
        return jsonify({"success": False})
    data = request.get_json()
    filename = data.get("filename", "").strip()
    if not filename or '..' in filename:
        return jsonify({"success": False, "message": "اسم غير صالح"})
    file_path = os.path.join(srv["path"], filename)
    if not os.path.exists(file_path):
        return jsonify({"success": False, "message": "الملف غير موجود"})
    srv["startup_file"] = filename
    save_db(db)
    return jsonify({"success": True, "message": f"✅ تم تعيين {filename} كملف التشغيل"})

@app.route('/api/server/install/<folder>', methods=['POST'])
def install_requirements(folder):
    if "username" not in session:
        return jsonify({"success": False}), 401
    srv = db["servers"].get(folder)
    if not srv or srv["owner"] != session["username"]:
        return jsonify({"success": False})
    req_file = os.path.join(srv["path"], "requirements.txt")
    if os.path.exists(req_file):
        try:
            log_path = os.path.join(srv["path"], "out.log")
            with open(log_path, "a", encoding='utf-8') as log_file:
                log_file.write(f"\n{'='*50}\n📦 بدء تثبيت المكتبات...\n{'='*50}\n")
            proc = subprocess.Popen(
                [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
                cwd=srv["path"],
                stdout=open(log_path, "a", encoding='utf-8'),
                stderr=subprocess.STDOUT
            )
            def wait_install():
                proc.wait()
                with open(log_path, "a", encoding='utf-8') as log_file:
                    if proc.returncode == 0:
                        log_file.write("\n✅ تم التثبيت بنجاح!\n")
                    else:
                        log_file.write("\n❌ فشل التثبيت\n")
            threading.Thread(target=wait_install, daemon=True).start()
            return jsonify({"success": True, "message": "📦 بدأ تثبيت المكتبات"})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)})
    return jsonify({"success": False, "message": "requirements.txt غير موجود"})

# ============== التشغيل ==============
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)