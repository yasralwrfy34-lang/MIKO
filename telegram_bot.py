#!/usr/bin/env python3
"""
MIKO HOST - بوت التحكم الكامل
- للمستخدم العادي: سيرفراتي، إنشاء سيرفر، تسجيل خروج
- للمسؤول (الأدمن): أزرار إضافية تظهر فقط لمن لديه الإيدي الصحيح
"""

import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# ========== إعدادات البوت ==========
BOT_TOKEN = "8562407588:AAF-H6hYxHV12jAXAyRzBfTjbZpGMHZgNG8"  # استبدل بتوكن البوت من BotFather
API_BASE_URL = "https://miko-t4ia.onrender.com"  # رابط موقعك

# ========== قائمة المسؤولين بالإيدي (Telegram ID) ==========
# ضع هنا أرقام تعريف التليجرام للمستخدمين الذين تريد منحهم صلاحية الإدارة
# كيف تحصل على الإيدي؟ أرسل رسالة إلى @userinfobot أو استخدم https://t.me/userinfobot
ADMIN_IDS = [
    8310269131,  # ضع إيدي حسابك هنا
    # 987654321,  # يمكنك إضافة المزيد
]

# ========== دوال مساعدة ==========
def api_request(endpoint, method="GET", data=None, params=None, files=None):
    url = f"{API_BASE_URL}{endpoint}"
    try:
        if method == "GET":
            resp = requests.get(url, params=params, timeout=30)
        elif method == "POST":
            if files:
                resp = requests.post(url, data=data, files=files, timeout=30)
            else:
                resp = requests.post(url, json=data, timeout=30)
        else:
            return None
        return resp.json() if resp else None
    except Exception as e:
        return {"success": False, "message": str(e)}

def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """التحقق من أن المستخدم مسؤول بناءً على إيدي التليجرام"""
    chat_id = update.effective_chat.id
    # 1. التحقق من القائمة اليدوية
    if chat_id in ADMIN_IDS:
        return True
    # 2. (اختياري) التحقق من قاعدة البيانات إذا أردت دعماً إضافياً
    return context.user_data.get("is_admin", False)

# ========== حالات المحادثة ==========
WAITING_FOR_API_KEY, WAITING_FOR_NEW_SERVER_NAME, WAITING_FOR_FILE_EDIT, WAITING_FOR_DELETE_USERNAME = range(4)

# ========== القوائم ==========
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض القائمة الرئيسية - تختلف حسب صلاحية المستخدم (بناءً على الإيدي)"""
    query = None
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        chat_id = query.message.chat_id
        message = query.message
    else:
        chat_id = update.effective_chat.id
        message = None

    # أزرار المستخدم العادي (تظهر للجميع)
    keyboard = [
        [InlineKeyboardButton("📁 سيرفراتي", callback_data="my_servers")],
        [InlineKeyboardButton("➕ إنشاء سيرفر جديد", callback_data="create_server")],
        [InlineKeyboardButton("🚪 تسجيل الخروج", callback_data="logout")]
    ]
    
    # إضافة أزرار المسؤول إذا كان الإيدي موجوداً في قائمة ADMIN_IDS
    if is_admin(update, context):
        keyboard.append([InlineKeyboardButton("👑 لوحة الإدارة", callback_data="admin_panel")])
        # يمكن إضافة أزرار إضافية للمسؤول هنا
    
    text = f"🔹 *القائمة الرئيسية* 🔹\nمرحباً {context.user_data.get('username', '')}!"
    if message:
        await message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

# ========== قائمة السيرفرات (لجميع المستخدمين) ==========
async def show_servers_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    result = api_request("/api/bot/servers", params={"api_key": context.user_data["api_key"]})
    if not result or not result.get("success"):
        await query.edit_message_text("❌ فشل جلب السيرفرات.")
        return
    servers = result.get("servers", [])
    if not servers:
        await query.edit_message_text("🚀 لا توجد سيرفرات حالياً.\nاستخدم 'إنشاء سيرفر جديد'.")
        return
    for srv in servers:
        status_emoji = "🟢" if srv['status'] == "Running" else "⚫"
        text = f"{status_emoji} *{srv['title']}*\n"
        text += f"📊 الحالة: {srv['status']}\n🔌 المنفذ: {srv['port']}\n💾 الخطة: {srv['plan']}\n⏱️ وقت التشغيل: {srv['uptime']}"
        keyboard = [
            [InlineKeyboardButton("▶️ تشغيل", callback_data=f"action_{srv['folder']}_start"),
             InlineKeyboardButton("⏹️ إيقاف", callback_data=f"action_{srv['folder']}_stop"),
             InlineKeyboardButton("🔄 إعادة تشغيل", callback_data=f"action_{srv['folder']}_restart")],
            [InlineKeyboardButton("🗑️ حذف", callback_data=f"action_{srv['folder']}_delete"),
             InlineKeyboardButton("🖥️ كونسول", callback_data=f"console_{srv['folder']}"),
             InlineKeyboardButton("📁 ملفات", callback_data=f"files_{srv['folder']}")],
            [InlineKeyboardButton("🔗 رابط التحكم", callback_data=f"dashboard_{srv['folder']}")]
        ]
        await query.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    await show_main_menu(update, context)

# ========== لوحة الإدارة (خاصة بالإيدي فقط) ==========
async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update, context):
        await query.edit_message_text("❌ غير مصرح: هذه اللوحة للمسؤولين فقط.")
        return
    
    # جلب إحصائيات المستخدمين
    result = api_request("/api/admin/users", params={"api_key": context.user_data["api_key"]})
    if not result or not result.get("success"):
        await query.edit_message_text("❌ فشل جلب بيانات المستخدمين.")
        return
    
    users = result.get("users", [])
    text = "👑 *لوحة إدارة MIKO HOST*\n\n"
    text += f"👥 *إجمالي المستخدمين:* {len(users)}\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n"
    for u in users[:15]:
        text += f"• `{u['username']}` | السيرفرات: {u.get('max_servers',1)} | صلاحية: {u.get('expiry_days',365)} يوم\n"
    if len(users) > 15:
        text += f"\n... و {len(users)-15} مستخدم آخر"
    
    keyboard = [
        [InlineKeyboardButton("🗑️ حذف مستخدم", callback_data="admin_delete_user")],
        [InlineKeyboardButton("📊 إحصائيات النظام", callback_data="admin_stats")],
        [InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="main_menu")]
    ]
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_delete_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update, context):
        await query.edit_message_text("❌ غير مصرح.")
        return
    await query.edit_message_text("📝 أرسل اسم المستخدم الذي تريد حذفه:")
    return WAITING_FOR_DELETE_USERNAME

async def admin_delete_user_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.strip()
    result = api_request("/api/admin/delete-user", method="POST", data={
        "api_key": context.user_data["api_key"],
        "username": username
    })
    if result and result.get("success"):
        await update.message.reply_text(f"✅ تم حذف المستخدم {username}")
    else:
        await update.message.reply_text(f"❌ فشل الحذف: {result.get('message', 'خطأ')}")
    await show_admin_panel(update, context)
    return ConversationHandler.END

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update, context):
        await query.edit_message_text("❌ غير مصرح.")
        return
    
    metrics = api_request("/api/system/metrics")
    servers_result = api_request("/api/bot/servers", params={"api_key": context.user_data["api_key"]})
    users_result = api_request("/api/admin/users", params={"api_key": context.user_data["api_key"]})
    
    total_servers = 0
    if servers_result and servers_result.get("success"):
        total_servers = len(servers_result.get("servers", []))
    
    total_users = 0
    if users_result and users_result.get("success"):
        total_users = len(users_result.get("users", []))
    
    cpu = metrics.get("cpu", "0") if metrics else "0"
    ram = metrics.get("memory", "0") if metrics else "0"
    
    text = "📊 *إحصائيات النظام*\n\n"
    text += f"🖥️ CPU: {cpu}%\n"
    text += f"💾 RAM: {ram}%\n"
    text += f"👥 إجمالي المستخدمين: {total_users}\n"
    text += f"🚀 إجمالي السيرفرات: {total_servers}\n"
    
    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]]
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

# ========== بداية البوت وتسجيل الدخول ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if context.user_data.get("api_key"):
        result = api_request("/api/bot/verify", method="POST", data={"api_key": context.user_data["api_key"]})
        if result and result.get("success"):
            context.user_data["is_admin"] = result.get("is_admin", False)
            await update.message.reply_text(f"✅ مرحباً بعودتك {result.get('username')}!")
            await show_main_menu(update, context)
            return
        else:
            context.user_data.clear()
    await update.message.reply_text(
        "🤖 *مرحباً بك في بوت MIKO HOST!*\n\nأرسل مفتاح API الخاص بك للحصول على الصلاحية المناسبة.\n"
        "يمكنك الحصول على المفتاح من موقع MIKO HOST (زر 'إنشاء API Key').",
        parse_mode="Markdown"
    )
    return WAITING_FOR_API_KEY

async def handle_api_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    api_key = update.message.text.strip()
    result = api_request("/api/bot/verify", method="POST", data={"api_key": api_key})
    if not result or not result.get("success"):
        await update.message.reply_text("❌ مفتاح API غير صالح. حاول مرة أخرى.")
        return WAITING_FOR_API_KEY
    context.user_data["api_key"] = api_key
    context.user_data["username"] = result.get("username")
    context.user_data["is_admin"] = result.get("is_admin", False)
    await update.message.reply_text(f"✅ تم التحقق بنجاح! مرحباً {result.get('username')}.")
    await show_main_menu(update, context)
    return ConversationHandler.END

async def handle_logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text("🚪 تم تسجيل الخروج. استخدم /start للدخول مجدداً.")

async def receive_server_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    result = api_request("/api/bot/create_server", method="POST", data={
        "api_key": context.user_data["api_key"],
        "name": name,
        "plan": "free",
        "storage": 100,
        "ram": 256,
        "cpu": 0.5
    })
    if result and result.get("success"):
        await update.message.reply_text(f"✅ تم إنشاء السيرفر `{name}` بنجاح!", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ فشل الإنشاء: {result.get('message', 'خطأ')}")
    await show_main_menu(update, context)
    return ConversationHandler.END

# دوال الملفات (مختصرة) - يمكن إضافة التفاصيل الكاملة حسب الحاجة
async def show_files(update: Update, context: ContextTypes.DEFAULT_TYPE, folder, path):
    query = update.callback_query
    result = api_request("/api/bot/files/list", params={
        "api_key": context.user_data["api_key"],
        "folder": folder,
        "path": path
    })
    if not result or not result.get("success"):
        await query.edit_message_text("❌ فشل جلب الملفات")
        return
    files = result.get("files", [])
    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]]
    await query.edit_message_text("📂 قائمة الملفات (يمكنك إضافة تفاصيل أكثر لاحقاً)", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    if data == "main_menu":
        await show_main_menu(update, context)
    elif data == "my_servers":
        await show_servers_list(update, context)
    elif data == "create_server":
        await query.edit_message_text("أرسل اسم السيرفر الجديد:")
        return WAITING_FOR_NEW_SERVER_NAME
    elif data == "logout":
        await handle_logout(update, context)
    elif data == "admin_panel":
        await show_admin_panel(update, context)
    elif data == "admin_delete_user":
        return await admin_delete_user_start(update, context)
    elif data == "admin_stats":
        await admin_stats(update, context)
    elif data.startswith("action_"):
        parts = data.split('_')
        folder = parts[1]
        action = parts[2]
        result = api_request("/api/bot/server/action", method="POST", data={
            "api_key": context.user_data["api_key"],
            "folder": folder,
            "action": action
        })
        msg = result.get("message", "تم التنفيذ") if result and result.get("success") else "❌ فشل"
        await query.edit_message_text(msg)
        await show_servers_list(update, context)
    elif data.startswith("console_"):
        folder = data.split('_')[1]
        result = api_request("/api/bot/console", params={"api_key": context.user_data["api_key"], "folder": folder})
        if result and result.get("success"):
            logs = result.get("logs", "لا توجد مخرجات")
            if len(logs) > 4000:
                logs = logs[-4000:] + "\n\n... (تم اقتطاع الباقي)"
            await query.edit_message_text(f"📟 *كونسول السيرفر*\n```\n{logs}\n```", parse_mode="Markdown")
        else:
            await query.edit_message_text("❌ فشل جلب الكونسول")
    elif data.startswith("dashboard_"):
        folder = data.split('_')[1]
        await query.edit_message_text(f"🔗 رابط التحكم:\n{API_BASE_URL}/dashboard?server={folder}")
    elif data.startswith("files_"):
        folder = data.split('_')[1]
        await show_files(update, context, folder, "")
    return ConversationHandler.END

# ========== تشغيل البوت ==========
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            WAITING_FOR_API_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_api_key)],
            WAITING_FOR_NEW_SERVER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_server_name)],
            WAITING_FOR_DELETE_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_delete_user_confirm)],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("🚀 بوت MIKO HOST يعمل...")
    app.run_polling()

if __name__ == "__main__":
    main()