#!/usr/bin/env python3
"""
مشغل بوت تلجرام - يتم تشغيله كعملية منفصلة
"""

import sys
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# إعداد السجل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالج أمر /start"""
    await update.message.reply_text(
        "👋 مرحباً! أنا بوت تلجرام يعمل من خلال ZAEM BRO HOST\n\n"
        "الأوامر المتاحة:\n"
        "/start - عرض هذه الرسالة\n"
        "/help - الحصول على المساعدة\n"
        "/info - معلومات البوت"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالج أمر /help"""
    await update.message.reply_text(
        "📚 المساعدة:\n\n"
        "هذا البوت يعمل بشكل مستمر على خادم ZAEM BRO HOST\n"
        "يمكنك إرسال أي رسالة والبوت سيرد عليك"
    )

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالج أمر /info"""
    await update.message.reply_text(
        "ℹ️ معلومات البوت:\n\n"
        "🤖 البوت: ZAEM BRO HOST Bot\n"
        "🏠 الخادم: ZAEM BRO HOST\n"
        "✅ الحالة: نشط ومستمر"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالج الرسائل العادية"""
    user_message = update.message.text
    await update.message.reply_text(
        f"📨 تم استقبال رسالتك:\n\n{user_message}\n\n"
        "شكراً لاستخدامك mero_host!"
    )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالج الأخطاء"""
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

def run_bot(token: str, bot_name: str) -> None:
    """تشغيل البوت باستخدام التوكن المعطى"""
    try:
        print("\n" + "═"*60)
        print(f" 🤖 [mero HOST] - جاري تشغيل البوت: {bot_name}")
        print(" 🚀 يتم الآن الاتصال بخوادم تلجرام...")
        print("═"*60 + "\n")
        
        logger.info(f"🤖 بدء تشغيل البوت: {bot_name}")
        
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
        print("\n" + "✨"*20)
        print(f" ✅ البوت {bot_name} جاهز الآن!")
        print(" 📡 الحالة: نشط وينتظر الرسائل...")
        print(" ✨ استمتع بخدمة ZAEM BRO HOST ✨")
        print("✨"*20 + "\n")
        
        logger.info(f"✅ البوت {bot_name} جاهز وينتظر الرسائل...")
        application.run_polling()
        
    except Exception as e:
        logger.error(f"❌ خطأ في تشغيل البوت {bot_name}: {str(e)}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("استخدام: python telegram_bot_runner.py <TOKEN> [BOT_NAME]")
        sys.exit(1)
    
    token = sys.argv[1]
    bot_name = sys.argv[2] if len(sys.argv) > 2 else "telegram_bot"
    
    run_bot(token, bot_name)
