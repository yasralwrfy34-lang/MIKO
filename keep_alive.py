#!/usr/bin/env python3
"""
🔥 OMAR BRO HOST - Advanced Keep-Alive System
منع الموقع والملفات من التوقف أو الدخول في وضع النوم
"""

import os
import time
import requests
import threading
import logging
from datetime import datetime

# إعداد السجل
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

class AdvancedKeepAlive:
    """نظام Keep-Alive متقدم مع حماية من التوقف المفاجئ"""
    
    def __init__(self):
        self.site_url = os.environ.get("RENDER_EXTERNAL_URL", "")
        self.is_running = True
        self.last_ping_time = datetime.now()
        self.ping_interval = 300  # 5 دقائق
        self.max_retries = 3
        self.retry_delay = 5
        
    def format_url(self):
        """تنسيق رابط الموقع بشكل صحيح"""
        if not self.site_url:
            return None
        if not self.site_url.startswith("http"):
            return f"https://{self.site_url}"
        return self.site_url
    
    def ping_server(self):
        """إرسال طلب Ping للموقع"""
        url = self.format_url()
        if not url:
            logger.warning("⚠️ لم يتم العثور على رابط الموقع")
            return False
        
        try:
            response = requests.get(
                f"{url}/api/ping",
                headers={
                    "User-Agent": "OMAR-BRO-HOST-KEEP-ALIVE/1.0",
                    "X-Keep-Alive": "true"
                },
                timeout=15,
                verify=False
            )
            
            if response.status_code == 200:
                self.last_ping_time = datetime.now()
                logger.info(f"✅ Ping ناجح: {url}/api/ping")
                return True
            else:
                logger.warning(f"⚠️ استجابة غير متوقعة: {response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            logger.error("❌ انتهاء المهلة الزمنية (Timeout)")
            return False
        except requests.exceptions.ConnectionError:
            logger.error("❌ فشل الاتصال بالموقع")
            return False
        except Exception as e:
            logger.error(f"❌ خطأ في الـ Ping: {str(e)}")
            return False
    
    def ping_with_retry(self):
        """إرسال Ping مع إعادة محاولة"""
        for attempt in range(self.max_retries):
            if self.ping_server():
                return True
            
            if attempt < self.max_retries - 1:
                logger.info(f"🔄 إعادة محاولة {attempt + 1}/{self.max_retries - 1}...")
                time.sleep(self.retry_delay)
        
        logger.error("❌ فشلت جميع محاولات الـ Ping")
        return False
    
    def start(self):
        """بدء نظام Keep-Alive"""
        logger.info("🚀 بدء نظام OMAR BRO HOST Keep-Alive")
        logger.info(f"📍 رابط الموقع: {self.format_url()}")
        logger.info(f"⏱️ فترة الـ Ping: {self.ping_interval} ثانية")
        
        while self.is_running:
            try:
                time.sleep(self.ping_interval)
                logger.info(f"📡 إرسال Ping في {datetime.now().strftime('%H:%M:%S')}")
                self.ping_with_retry()
                
            except KeyboardInterrupt:
                logger.info("🛑 إيقاف نظام Keep-Alive...")
                self.is_running = False
            except Exception as e:
                logger.error(f"❌ خطأ غير متوقع: {str(e)}")
                time.sleep(10)
    
    def stop(self):
        """إيقاف نظام Keep-Alive"""
        self.is_running = False
        logger.info("✋ تم إيقاف نظام Keep-Alive")


def run_keep_alive_daemon():
    """تشغيل Keep-Alive كـ Daemon في الخلفية"""
    keep_alive = AdvancedKeepAlive()
    keep_alive.start()


if __name__ == "__main__":
    # تشغيل Keep-Alive في خيط منفصل
    daemon_thread = threading.Thread(target=run_keep_alive_daemon, daemon=True)
    daemon_thread.start()
    
    # الحفاظ على البرنامج مشغول
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("🛑 إيقاف البرنامج...")
