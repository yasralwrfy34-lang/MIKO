#!/usr/bin/env python3
"""
🛡️ OMAR BRO HOST - File Protection System
حماية الملفات من التوقف المفاجئ والفقدان
"""

import os
import json
import shutil
import logging
import threading
import time
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

class FileProtectionSystem:
    """نظام حماية الملفات من التوقف المفاجئ"""
    
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.users_dir = os.path.join(base_dir, "USERS")
        self.backup_dir = os.path.join(base_dir, ".backups")
        self.protection_log = os.path.join(base_dir, "file_protection.log")
        self.is_running = True
        self.check_interval = 300  # 5 دقائق
        
        # إنشاء مجلدات الحماية
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def log_protection(self, message):
        """تسجيل عمليات الحماية"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        
        try:
            with open(self.protection_log, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except Exception as e:
            logger.error(f"❌ خطأ في تسجيل الحماية: {str(e)}")
    
    def backup_critical_files(self):
        """عمل نسخة احتياطية من الملفات الحساسة"""
        critical_files = [
            "users.json",
            "remember_tokens.json",
            "bots_config.json",
            "pids.json"
        ]
        
        try:
            for filename in critical_files:
                source = os.path.join(self.base_dir, filename)
                if os.path.exists(source):
                    backup_name = f"{filename}.backup.{int(time.time())}"
                    dest = os.path.join(self.backup_dir, backup_name)
                    
                    shutil.copy2(source, dest)
                    self.log_protection(f"✅ تم عمل نسخة احتياطية من {filename}")
                    
                    # الاحتفاظ بآخر 10 نسخ احتياطية فقط
                    self._cleanup_old_backups(filename)
                    
        except Exception as e:
            logger.error(f"❌ خطأ في النسخ الاحتياطي: {str(e)}")
            self.log_protection(f"❌ خطأ في النسخ الاحتياطي: {str(e)}")
    
    def _cleanup_old_backups(self, original_filename):
        """حذف النسخ الاحتياطية القديمة"""
        try:
            backups = [f for f in os.listdir(self.backup_dir) 
                      if f.startswith(original_filename + ".backup")]
            
            if len(backups) > 10:
                # ترتيب حسب وقت التعديل
                backups.sort(key=lambda x: os.path.getmtime(
                    os.path.join(self.backup_dir, x)))
                
                # حذف الملفات القديمة
                for old_backup in backups[:-10]:
                    os.remove(os.path.join(self.backup_dir, old_backup))
                    
        except Exception as e:
            logger.error(f"❌ خطأ في تنظيف النسخ الاحتياطية: {str(e)}")
    
    def verify_user_directories(self):
        """التحقق من سلامة مجلدات المستخدمين"""
        try:
            if not os.path.exists(self.users_dir):
                os.makedirs(self.users_dir, exist_ok=True)
                self.log_protection("✅ تم إنشاء مجلد USERS")
            
            # التحقق من وجود ملف المستخدمين
            users_file = os.path.join(self.base_dir, "users.json")
            if not os.path.exists(users_file):
                self.log_protection("⚠️ ملف المستخدمين غير موجود - سيتم إنشاؤه تلقائياً")
            
        except Exception as e:
            logger.error(f"❌ خطأ في التحقق من المجلدات: {str(e)}")
            self.log_protection(f"❌ خطأ في التحقق من المجلدات: {str(e)}")
    
    def check_disk_space(self):
        """التحقق من المساحة المتاحة على القرص"""
        try:
            stat = shutil.disk_usage(self.base_dir)
            free_gb = stat.free / (1024 ** 3)
            total_gb = stat.total / (1024 ** 3)
            
            if free_gb < 0.5:  # أقل من 500 MB
                logger.warning(f"⚠️ تحذير: المساحة الحرة أقل من 500 MB ({free_gb:.2f} GB)")
                self.log_protection(f"⚠️ تحذير: المساحة الحرة {free_gb:.2f} GB من {total_gb:.2f} GB")
            else:
                logger.info(f"✅ المساحة الحرة: {free_gb:.2f} GB من {total_gb:.2f} GB")
                
        except Exception as e:
            logger.error(f"❌ خطأ في التحقق من المساحة: {str(e)}")
    
    def start_protection(self):
        """بدء نظام الحماية"""
        logger.info("🛡️ بدء نظام حماية الملفات")
        self.log_protection("🛡️ بدء نظام حماية الملفات")
        
        while self.is_running:
            try:
                time.sleep(self.check_interval)
                
                logger.info("🔍 فحص سلامة الملفات...")
                self.backup_critical_files()
                self.verify_user_directories()
                self.check_disk_space()
                
            except KeyboardInterrupt:
                logger.info("🛑 إيقاف نظام الحماية...")
                self.is_running = False
            except Exception as e:
                logger.error(f"❌ خطأ في نظام الحماية: {str(e)}")
                time.sleep(10)
    
    def stop_protection(self):
        """إيقاف نظام الحماية"""
        self.is_running = False
        logger.info("✋ تم إيقاف نظام الحماية")
        self.log_protection("✋ تم إيقاف نظام الحماية")


def run_file_protection_daemon(base_dir):
    """تشغيل نظام الحماية كـ Daemon"""
    protection = FileProtectionSystem(base_dir)
    protection.start_protection()


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # تشغيل الحماية في خيط منفصل
    daemon_thread = threading.Thread(
        target=run_file_protection_daemon,
        args=(base_dir,),
        daemon=True
    )
    daemon_thread.start()
    
    # الحفاظ على البرنامج مشغول
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("🛑 إيقاف البرنامج...")
