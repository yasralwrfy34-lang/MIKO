#!/usr/bin/env python3
"""
بوت تلجرام بسيط للاختبار
يمكن تشغيل عدة بوتات من خلال لوحة التحكم
"""

import logging
import os
import json
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# إعداد السجل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# متغير عام لتخزين بيانات البوتات
BOTS_CONFIG_FILE = os.path.join(os.path.dirname(__file__), "bots_config.json")

def load_bots_config():
    """تحميل إعدادات البوتات من ملف JSON"""
    if os.path.exists(BOTS_CONFIG_FILE):
        with open(BOTS_CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_bots_config(config):
    """حفظ إعدادات البوتات في ملف JSON"""
    with open(BOTS_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالج أمر /start"""
    await update.message.reply_text(
        "👋 مرحباً! أنا بوت تلجرام يعمل من خلال ᗰᗴᖇO_ᕼOՏT\n\n"
        "الأوامر المتاحة:\n"
        "/start - عرض هذه الرسالة\n"
        "/help - الحصول على المساعدة\n"
        "/info - معلومات البوت"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالج أمر /help"""
    await update.message.reply_text(
        "📚 المساعدة:\n\n"
        "هذا البوت يعمل بشكل مستمر على خادم ᗰᗴᖇO_ᕼOՏT\n"
        "يمكنك إرسال أي رسالة والبوت سيرد عليك"
    )

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالج أمر /info"""
    await update.message.reply_text(
        "ℹ️ معلومات البوت:\n\n"
        "🤖 البوت: ᗰᗴᖇO_ᕼOՏT Bot\n"
        "🏠 الخادم: ᗰᗴᖇO_ᕼOՏT\n"
        "✅ الحالة: نشط ومستمر"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالج الرسائل العادية"""
    user_message = update.message.text
    await update.message.reply_text(
        f"📨 تم استقبال رسالتك:\n\n{user_message}\n\n"
        "شكراً لاستخدامك ᗰᗴᖇO_ᕼOՏT Bot!"
    )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالج الأخطاء"""
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

def run_bot(token: str) -> None:
    """تشغيل البوت باستخدام التوكن المعطى"""
    try:
        # إنشاء التطبيق
        application = Application.builder().token(token).build()

        # إضافة معالجات الأوامر
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("info", info_command))
        
        # معالج الرسائل العادية
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        # معالج الأخطاء
        application.add_error_handler(error_handler)

        # بدء البوت
        logger.info("🤖 بدء تشغيل البوت...")
        application.run_polling()
        
    except Exception as e:
        logger.error(f"❌ خطأ في تشغيل البوت: {str(e)}")

if __name__ == "__main__":
    # التوكن الافتراضي (يمكن تغييره من لوحة التحكم)
    TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8759784029:AAEEK__N5yVpepiT1NauYBldlA0f7WSAfyw")
    ADMIN_ID = os.environ.get("TELEGRAM_ADMIN_ID", "8206539702")
    run_bot(TOKEN)
