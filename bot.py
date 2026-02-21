import sqlite3
import logging
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

# --- سيرفر وهمي لمنع النوم ---
class WebServerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"BETMAX SYSTEM ACTIVE")

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), WebServerHandler)
    server.serve_forever()

# --- الإعدادات ---
TOKEN = '7675556594:AAGQpCGTAIdQ7YPBTeePTAKGxtb25-BRL08'
ADMIN_ID = 7528722019 #

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS authorized_users 
                 (user_id INTEGER PRIMARY KEY, 
                  username TEXT, 
                  expiry_date TEXT)''')
    conn.commit()
    conn.close()

# --- أوامر المدير ---

async def add_permanent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        if not context.args:
            await update.message.reply_text("❌ أرسل اليوزرنيم.")
            return
        target = context.args[0].replace('@', '').lower()
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO authorized_users (username, expiry_date) VALUES (?, ?)', (target, None))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ تم إضافة {target} كمشترك دائم.")

async def add_trial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        if not context.args:
            await update.message.reply_text("❌ أرسل اليوزرنيم.")
            return
        target = context.args[0].replace('@', '').lower()
        expiry = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S')
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO authorized_users (username, expiry_date) VALUES (?, ?)', (target, expiry))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"⏳ تم إضافة {target} تجربة لمدة 3 أيام.\nينتهي في: {expiry}")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        now_dt = datetime.now()
        now_str = now_dt.strftime('%Y-%m-%d %H:%M:%S')

        # 1. التعامل مع المنتهية صلاحيتهم قبل الإرسال
        c.execute('SELECT user_id, username FROM authorized_users WHERE expiry_date <= ? AND user_id IS NOT NULL', (now_str,))
        expired_users = c.fetchall()
        for u_id, u_name in expired_users:
            try:
                await context.bot.send_message(chat_id=u_id, text="⚠️ انتهت مدة تجربتك المجانية.\nللاستمرار في استلام التوقعات، يرجى التواصل مع الإدارة لتفعيل الاشتراك الدائم.")
            except: pass
            # حذف المشترك المنتهي من القاعدة
            c.execute('DELETE FROM authorized_users WHERE user_id = ?', (u_id,))
        
        conn.commit()

        # 2. جلب المشتركين المتبقين (الدائمين والنشطين)
        c.execute('SELECT user_id FROM authorized_users WHERE user_id IS NOT NULL')
        users = c.fetchall()
        conn.close()

        sent = 0
        for user in users:
            try:
                if update.message.photo:
                    await context.bot.send_photo(chat_id=user[0], photo=update.message.photo[-1].file_id, caption=update.message.caption.replace('/send', ''))
                else:
                    text_to_send = update.message.text.replace('/send', '').strip()
                    await context.bot.send_message(chat_id=user[0], text=text_to_send)
                sent += 1
            except: continue
        await update.message.reply_text(f"🚀 تم النشر لـ {sent} مشترك.\n(تم تنبيه وحذف الحسابات المنتهية تلقائياً)")

# --- أوامر المشتركين ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username.lower() if update.effective_user.username else ""
    if user_id == ADMIN_ID:
        await update.message.reply_text("👋 مدير النظام. الأوامر: /add, /trial, /send")
        return

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT expiry_date FROM authorized_users WHERE username=?', (username,))
    row = c.fetchone()
    
    if row:
        expiry_str = row[0]
        if expiry_str is None:
            c.execute('UPDATE authorized_users SET user_id=? WHERE username=?', (user_id, username))
            conn.commit()
            await update.message.reply_text("✅ تم تفعيل اشتراكك الدائم!")
        else:
            expiry = datetime.strptime(expiry_str, '%Y-%m-%d %H:%M:%S')
            if datetime.now() < expiry:
                c.execute('UPDATE authorized_users SET user_id=? WHERE username=?', (user_id, username))
                conn.commit()
                await update.message.reply_text(f"✅ تم تفعيل تجربتك! تنتهي في: {expiry_str}")
            else:
                await update.message.reply_text("⌛ انتهت مدة تجربتك المجانية. تواصل مع الإدارة.")
    else:
        await update.message.reply_text("🚫 غير مسجل.")
    conn.close()

if __name__ == '__main__':
    init_db()
    threading.Thread(target=run_web_server, daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_permanent))
    app.add_handler(CommandHandler("trial", add_trial))
    app.add_handler(MessageHandler(filters.PHOTO | filters.TEXT & filters.Caption(pattern=r'^/send'), broadcast))
    app.add_handler(CommandHandler("send", broadcast))
    app.run_polling()
