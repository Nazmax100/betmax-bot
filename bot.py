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
        self.wfile.write(b"BETMAX SYSTEM IS LIVE")

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), WebServerHandler)
    server.serve_forever()

# --- الإعدادات ---
TOKEN = '7675556594:AAGQpCGTAIdQ7YPBTeePTAKGxtb25-BRL08'
ADMIN_ID = 7528722019

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS authorized_users 
                 (user_id INTEGER PRIMARY KEY, username TEXT, expiry_date TEXT)''')
    conn.commit()
    conn.close()

# --- أوامر الإحصائيات (الجديد) ---
async def get_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        c.execute('SELECT COUNT(*) FROM authorized_users WHERE expiry_date IS NULL')
        perm = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM authorized_users WHERE expiry_date > ?', (now,))
        active_trial = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM authorized_users WHERE expiry_date <= ?', (now,))
        expired = c.fetchone()[0]
        conn.close()
        
        msg = f"📊 **إحصائيات BETMAX:**\n\n✅ دائم: {perm}\n⏳ تجربة نشطة: {active_trial}\n❌ منتهي: {expired}"
        await update.message.reply_text(msg, parse_mode='Markdown')

# --- أوامر الإدارة ---
async def add_permanent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        target = context.args[0].replace('@', '').lower() if context.args else None
        if not target: return await update.message.reply_text("❌ مثال: /add user123")
        conn = sqlite3.connect('users.db'); c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO authorized_users (username, expiry_date) VALUES (?, ?)', (target, None))
        conn.commit(); conn.close()
        await update.message.reply_text(f"✅ تم إضافة {target} كمشترك دائم.")

async def add_trial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        target = context.args[0].replace('@', '').lower() if context.args else None
        if not target: return await update.message.reply_text("❌ مثال: /trial user123")
        expiry = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S')
        conn = sqlite3.connect('users.db'); c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO authorized_users (username, expiry_date) VALUES (?, ?)', (target, expiry))
        conn.commit(); conn.close()
        await update.message.reply_text(f"⏳ {target} تجربة 3 أيام.\nتنتهي: {expiry}")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        conn = sqlite3.connect('users.db'); c = conn.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        # تنبيه المنتهيين وحذفهم
        c.execute('SELECT user_id FROM authorized_users WHERE expiry_date <= ? AND user_id IS NOT NULL', (now,))
        expired_users = c.fetchall()
        for u in expired_users:
            try: await context.bot.send_message(u[0], "⚠️ انتهت تجربتك المجانية. تواصل مع الإدارة للتجديد.")
            except: pass
            c.execute('DELETE FROM authorized_users WHERE user_id = ?', (u[0],))
        conn.commit()
        # النشر للباقين
        c.execute('SELECT user_id FROM authorized_users WHERE user_id IS NOT NULL')
        users = c.fetchall(); conn.close()
        sent = 0
        for user in users:
            try:
                if update.message.photo:
                    await context.bot.send_photo(user[0], update.message.photo[-1].file_id, caption=update.message.caption.replace('/send',''))
                else:
                    await context.bot.send_message(user[0], update.message.text.replace('/send',''))
                sent += 1
            except: continue
        await update.message.reply_text(f"🚀 تم النشر لـ {sent} مشترك.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, uname = update.effective_user.id, (update.effective_user.username or "").lower()
    if uid == ADMIN_ID: return await update.message.reply_text("👋 مدير النظام. الأوامر:\n/add\n/trial\n/stats\n/send")
    conn = sqlite3.connect('users.db'); c = conn.cursor()
    c.execute('SELECT expiry_date FROM authorized_
