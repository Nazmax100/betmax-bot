import os
import sqlite3
import threading
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- الإعدادات الثابتة ---
TOKEN = '7681363991:AAH8N6Vv5Nn3q_hJ0Y8U6mN3Y8vS9mN3Y8v' #
ADMIN_ID = 7528722019 #

# --- سيرفر الويب للإيقاظ ---
class WakeUpHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot Alive")

def run_wakeup_server():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(('0.0.0.0', port), WakeUpHandler).serve_forever()

# --- إعداد قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, username TEXT, expiration_date TEXT)''')
    conn.commit()
    conn.close()

# --- الأوامر ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = f"@{update.effective_user.username}" if update.effective_user.username else "None"
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO users (user_id, username, expiration_date) VALUES (?, ?, COALESCE((SELECT expiration_date FROM users WHERE user_id=?), ?))",
              (user_id, username, user_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"🚀 تم تفعيل البوت\n🆔 آيدي: `{user_id}`\n👤 يوزر: {username}")

async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        target = context.args[0]
        days = int(context.args[1])
        exp = (datetime.now() + timedelta(days=36500 if days == 999 else days)).strftime('%Y-%m-%d %H:%M:%S')
        
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        if target.startswith('@'):
            c.execute("UPDATE users SET expiration_date = ? WHERE username = ?", (exp, target))
        else:
            c.execute("UPDATE users SET expiration_date = ? WHERE user_id = ?", (exp, int(target)))
        
        if c.rowcount > 0:
            conn.commit()
            await update.message.reply_text(f"✅ تم التفعيل لـ {target}")
        else:
            await update.message.reply_text("❌ المستخدم غير موجود بالقاعدة")
        conn.close()
    except:
        await update.message.reply_text("⚠️ `/add @username 1`")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT username, user_id FROM users WHERE expiration_date > ?", (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),))
    users = c.fetchall()
    conn.close()
    res = "📊 المشتركون:\n" + "\n".join([f"👤 {u[0]} (`{u[1]}`)" for u in users])
    await update.message.reply_text(res if users else "لا يوجد نشطين")

async def send_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    text = " ".join(context.args)
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    ids = c.fetchall()
    conn.close()
    for uid in ids:
        try: await context.bot.send_message(chat_id=uid[0], text=text)
        except: continue
    await update.message.reply_text("📢 تم الإرسال")

if __name__ == '__main__':
    init_db()
    threading.Thread(target=run_wakeup_server, daemon=True).start()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_user))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("send", send_all))
    app.run_polling()
