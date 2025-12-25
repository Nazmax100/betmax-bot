import sqlite3
import logging
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --- إعداد سيرفر وهمي لإرضاء منصة Render المجانية ---
class WebServerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is Running!")

def run_web_server():
    # Render يمرر منفذ (Port) تلقائياً، وإذا لم يجده يستخدم 8080
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), WebServerHandler)
    server.serve_forever()

# --- الإعدادات الأساسية ---
TOKEN = '7675556594:AAGQpCGTAIdQ7YPBTeePTAKGxtb25-BRL08'
ADMIN_ID = 7528722019 

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS authorized_users 
                 (user_id INTEGER PRIMARY KEY, username TEXT)''')
    conn.commit()
    conn.close()

# --- أوامر المدير ---
async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        if not context.args:
            await update.message.reply_text("❌ أرسل اليوزرنيم. مثال: /add user123")
            return
        target_username = context.args[0].replace('@', '').lower()
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('INSERT OR IGNORE INTO authorized_users (username) VALUES (?)', (target_username,))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ تمت إضافة {target_username}")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        if not context.args:
            await update.message.reply_text("❌ اكتب رسالتك.")
            return
        msg = " ".join(context.args)
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('SELECT user_id FROM authorized_users WHERE user_id IS NOT NULL')
        users = c.fetchall()
        conn.close()
        sent = 0
        for user in users:
            try:
                await context.bot.send_message(chat_id=user[0], text=msg, parse_mode='Markdown')
                sent += 1
            except: continue
        await update.message.reply_text(f"🚀 أرسلت إلى {sent}")

# --- أوامر المستخدمين ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username.lower() if update.effective_user.username else ""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT * FROM authorized_users WHERE username=?', (username,))
    if c.fetchone():
        c.execute('UPDATE authorized_users SET user_id=? WHERE username=?', (user_id, username))
        conn.commit()
        await update.message.reply_text("✅ تم تفعيل اشتراكك!")
    else:
        await update.message.reply_text("🚫 غير مسجل. تواصل مع الإدارة.")
    conn.close()

if __name__ == '__main__':
    init_db()
    
    # تشغيل السيرفر الوهمي في "خيط" (Thread) منفصل
    threading.Thread(target=run_web_server, daemon=True).start()
    
    # تشغيل البوت
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_user))
    app.add_handler(CommandHandler("send", broadcast))
    
    print("🚀 البوت يعمل الآن بنظام الـ Web Service المجاني...")
    app.run_polling()
