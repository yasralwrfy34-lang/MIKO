"""
MongoDB Handler - إدارة قاعدة البيانات السحابية
يوفر واجهة موحدة للتعامل مع MongoDB Atlas
"""

import os
import json
import hashlib
from datetime import datetime
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError, ConnectionFailure

# ============== MONGODB CONFIGURATION ==============

# استخدم متغير البيئة أو قيمة افتراضية للاختبار المحلي
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb+srv://omar_admin:OmarHost2026@cluster0.mongodb.net/omar_host_db?retryWrites=true&w=majority')
DB_NAME = 'omar_host_db'

# متغيرات المسؤول الافتراضية (تم التحديث بناءً على طلب المستخدم)
ADMIN_USERNAME = "hossamhossam#11212"
ADMIN_PASSWORD_RAW = "hossamhossam#11212"

# ============== MONGODB CONNECTION ==============

class MongoDBHandler:
    def __init__(self):
        self.client = None
        self.db = None
        self.connected = False
        self._connect()
    
    def _connect(self):
        """الاتصال بـ MongoDB مع معالجة الأخطاء"""
        try:
            # محاولة الاتصال بـ MongoDB Atlas
            self.client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000, connectTimeoutMS=10000)
            # اختبار الاتصال
            self.client.admin.command('ping')
            self.db = self.client[DB_NAME]
            self.connected = True
            print("✅ تم الاتصال بـ MongoDB بنجاح")
            self._initialize_collections()
        except Exception as e:
            print(f"⚠️ تعذر الاتصال بـ MongoDB: {e}")
            self.connected = False
            # في حالة فشل الاتصال بـ Atlas، سيتم استخدام التخزين المحلي تلقائياً عبر الدوال الأخرى
    
    def _initialize_collections(self):
        """إنشاء المجموعات (Collections) الأساسية إذا لم تكن موجودة"""
        if self.connected:
            try:
                existing_collections = self.db.list_collection_names()
                
                # التحقق من وجود مجموعة المستخدمين
                if 'users' not in existing_collections:
                    self.db.create_collection('users')
                
                # التأكد من وجود حساب المسؤول الصحيح
                admin_hash = hashlib.sha256(ADMIN_PASSWORD_RAW.encode()).hexdigest()
                self.db['users'].update_one(
                    {"_id": ADMIN_USERNAME},
                    {"$set": {
                        "password": admin_hash,
                        "is_admin": True,
                        "created_at": str(datetime.now()),
                        "max_servers": 100,
                        "expiry_days": 3650
                    }},
                    upsert=True
                )
                
                # التحقق من وجود مجموعة الخوادم
                if 'servers' not in existing_collections:
                    self.db.create_collection('servers')
                
                # التحقق من وجود مجموعة السجلات
                if 'logs' not in existing_collections:
                    self.db.create_collection('logs')
            except Exception as e:
                print(f"❌ خطأ في تهيئة المجموعات: {e}")
    
    def load_db(self):
        """تحميل قاعدة البيانات بصيغة JSON (للتوافقية مع الكود الحالي)"""
        if not self.connected:
            return self._load_local_db()
        
        try:
            users = {}
            for user in self.db['users'].find():
                user_id = user.pop('_id')
                users[user_id] = user
            
            servers = {}
            for server in self.db['servers'].find():
                server_id = server.pop('_id')
                servers[server_id] = server
            
            logs = list(self.db['logs'].find().sort("_id", -1).limit(100))
            for log in logs:
                log.pop('_id', None)
            
            return {
                "users": users,
                "servers": servers,
                "logs": logs
            }
        except Exception as e:
            print(f"❌ خطأ في تحميل البيانات من MongoDB: {e}")
            return self._load_local_db()
    
    def save_db(self, db_data):
        """حفظ قاعدة البيانات"""
        if not self.connected:
            return self._save_local_db(db_data)
        
        try:
            # حفظ المستخدمين (تحديث فردي لتجنب حذف الكل)
            if 'users' in db_data:
                for username, user_data in db_data['users'].items():
                    user_data_copy = user_data.copy()
                    user_data_copy['_id'] = username
                    self.db['users'].replace_one({"_id": username}, user_data_copy, upsert=True)
            
            # حفظ الخوادم
            if 'servers' in db_data:
                for server_id, server_data in db_data['servers'].items():
                    server_data_copy = server_data.copy()
                    server_data_copy['_id'] = server_id
                    self.db['servers'].replace_one({"_id": server_id}, server_data_copy, upsert=True)
            
            print("✅ تم مزامنة البيانات مع MongoDB")
        except Exception as e:
            print(f"❌ خطأ في حفظ البيانات في MongoDB: {e}")
            self._save_local_db(db_data)
    
    def _load_local_db(self):
        """تحميل قاعدة البيانات من ملف JSON محلي (للطوارئ)"""
        db_file = os.path.join(os.path.dirname(__file__), "db.json")
        admin_hash = hashlib.sha256(ADMIN_PASSWORD_RAW.encode()).hexdigest()
        
        default_db = {
            "users": {
                ADMIN_USERNAME: {
                    "password": admin_hash,
                    "is_admin": True,
                    "created_at": str(datetime.now()),
                    "max_servers": 100,
                    "expiry_days": 3650
                }
            },
            "servers": {},
            "logs": []
        }
        
        if os.path.exists(db_file):
            try:
                with open(db_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # التأكد من وجود الأدمن في النسخة المحلية أيضاً
                    if ADMIN_USERNAME not in data.get("users", {}):
                        if "users" not in data: data["users"] = {}
                        data["users"][ADMIN_USERNAME] = default_db["users"][ADMIN_USERNAME]
                    return data
            except:
                pass
        
        return default_db
    
    def _save_local_db(self, db_data):
        """حفظ قاعدة البيانات في ملف JSON محلي (للطوارئ)"""
        db_file = os.path.join(os.path.dirname(__file__), "db.json")
        try:
            with open(db_file, 'w', encoding='utf-8') as f:
                json.dump(db_data, f, indent=4, ensure_ascii=False)
            print(f"✅ تم حفظ البيانات محلياً في {db_file}")
        except Exception as e:
            print(f"❌ خطأ في حفظ البيانات محلياً: {e}")
    
    def health_check(self):
        """فحص صحة الاتصال"""
        try:
            if self.client:
                self.client.admin.command('ping')
                return True
        except:
            self._connect()
        return self.connected

# إنشاء نسخة عامة من المعالج
db_handler = MongoDBHandler()
