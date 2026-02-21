import os
import sqlite3
import threading
import logging
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN    = "7675556594:AAGQpCGTAIdQ7YPBTeePTAKGxtb25-BRL08"
ADMIN_ID = 7528722019

# ─── سيرفر الإيقاظ ───────────────────────────────────────────────────────────
class WakeUpHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is online")
    def log_message(self, format, *args):
        pass

def run_server():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(('0.0.0.0', port), WakeUpHandler).serve_forever()

# ─── قاعدة البيانات ───────────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect('users.db')
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        expiration_date TEXT
    )''')
    conn.commit()
    conn.close()

def get_conn():
    conn = sqlite3.connect('users.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# ─── الأوامر ──────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id  = update.effective_user.id
    username = f"@{update.effective_user.username}" if update.effective_user.username else "None"
    now      = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = get_conn()
    conn.execute('''INSERT INTO users (user_id, username, expiration_date)
                    VALUES (?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET username=excluded.username''',
                 (user_id, username, now))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"🚀 تم التسجيل\n🆔 ID: `{user_id}`\n👤 User: {username}",
        parse_mode="Markdown"
    )

async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ الاستخدام: /add @username 30")
        return

    target = context.args[0]
    try:
        days = int(context.args[1])
    except:
        await update.message.reply_text("❌ عدد الأيام يجب أن يكون رقماً")
        return

    actual_days = 36500 if days == 999 else days
    exp = (datetime.now() + timedelta(days=actual_days)).strftime('%Y-%m-%d %H:%M:%S')

    conn = get_conn()
    if target.startswith('@'):
        cur = conn.execute("UPDATE users SET expiration_date=? WHERE username=?", (exp, target))
    else:
        cur = conn.execute("UPDATE users SET expiration_date=? WHERE user_id=?", (exp, int(target)))
    conn.commit()
    conn.close()

    if cur.rowcount > 0:
        label = "دائم ♾️" if days == 999 else f"{days} يوم"
        await update.message.reply_text(f"✅ تم تفعيل {target} لمدة {label}")
    else:
        await update.message.reply_text("❌ المستخدم غير موجود، يجب أن يضغط /start أولاً")

async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("⚠️ الاستخدام: /remove @username")
        return

    target  = context.args[0]
    expired = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = get_conn()
    if target.startswith('@'):
        cur = conn.execute("UPDATE users SET expiration_date=? WHERE username=?", (expired, target))
    else:
        cur = conn.execute("UPDATE users SET expiration_date=? WHERE user_id=?", (expired, int(target)))
    conn.commit()
    conn.close()

    if cur.rowcount > 0:
        await update.message.reply_text(f"🚫 تم إلغاء اشتراك {target}")
    else:
        await update.message.reply_text("❌ المستخدم غير موجود")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    now  = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_conn()
    active   = conn.execute("SELECT COUNT(*) FROM users WHERE expiration_date > ?", (now,)).fetchone()[0]
    inactive = conn.execute("SELECT COUNT(*) FROM users WHERE expiration_date <= ?", (now,)).fetchone()[0]
    users    = conn.execute("SELECT username, user_id, expiration_date FROM users WHERE expiration_date > ?", (now,)).fetchall()
    conn.close()

    lines = [f"📊 *إحصائيات البوت*\n✅ نشط: {active} | ❌ منتهي: {inactive}\n"]
    for u in users:
        lines.append(f"👤 {u['username']} (`{u['user_id']}`) — حتى {u['expiration_date'][:10]}")

    await update.message.reply_text("\n".join(lines) if users else "لا يوجد مشتركون نشطون", parse_mode="Markdown")

async def send_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    text = " ".join(context.args).strip()
    if not text:
        await update.message.reply_text("⚠️ أرسل نصاً بعد الأمر")
        return

    conn = get_conn()
    ids  = [row[0] for row in conn.execute("SELECT user_id FROM users").fetchall()]
    conn.close()

    success, failed = 0, 0
    for uid in ids:
        try:
            await context.bot.send_message(chat_id=uid, text=text)
            success += 1
        except:
            failed += 1

    await update.message.reply_text(f"📢 تم الإرسال\n✅ نجح: {success} | ❌ فشل: {failed}")

async def my_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn    = get_conn()
    row     = conn.execute("SELECT expiration_date FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()

    if not row:
        await update.message.reply_text("❌ أنت غير مسجّل، استخدم /start أولاً")
        return

    exp = datetime.strptime(row['expiration_date'], '%Y-%m-%d %H:%M:%S')
    if exp > datetime.now():
        remaining = (exp - datetime.now()).days
        await update.message.reply_text(
            f"✅ اشتراكك نشط\n📅 ينتهي: {exp.strftime('%Y-%m-%d')}\n⏳ المتبقي: {remaining} يوم"
        )
    else:
        await update.message.reply_text("❌ اشتراكك منتهٍ، تواصل مع المدير")

# ─── التشغيل ──────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    init_db()
    threading.Thread(target=run_server, daemon=True).start()

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",  start))
    app.add_handler(CommandHandler("add",    add_user))
    app.add_handler(CommandHandler("remove", remove_user))
    app.add_handler(CommandHandler("stats",  stats))
    app.add_handler(CommandHandler("send",   send_all))
    app.add_handler(CommandHandler("status", my_status))

    logger.info("✅ Bot started!")
    app.run_polling()
