import os
import sqlite3
import threading
import logging
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ─── إعداد السجلات ───────────────────────────────────────────────────────────
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─── الإعدادات (استخدم متغيرات البيئة دائماً) ────────────────────────────────
TOKEN    = "7675556594:AAGQpCGTAIdQ7YPBTeePTAKGxtb25-BRL08"
ADMIN_ID = 7528722019

DB_PATH  = os.environ.get("DB_PATH", "users.db")

# ─── سيرفر الإيقاظ ───────────────────────────────────────────────────────────
class WakeUpHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is online")

    def log_message(self, format, *args):
        pass  # إخفاء سجلات HTTP غير الضرورية

def run_wakeup_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), WakeUpHandler)
    logger.info(f"Wake-up server running on port {port}")
    server.serve_forever()

# ─── قاعدة البيانات ───────────────────────────────────────────────────────────
def get_conn():
    """إنشاء اتصال آمن بقاعدة البيانات."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_conn() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id        INTEGER PRIMARY KEY,
                username       TEXT,
                expiration_date TEXT NOT NULL,
                created_at     TEXT DEFAULT (datetime('now'))
            )
        ''')
    logger.info("Database initialized.")

# ─── مساعد للتحقق من الصلاحيات ───────────────────────────────────────────────
def is_admin(update: Update) -> bool:
    return update.effective_user.id == ADMIN_ID

# ─── الأوامر ──────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    user_id = user.id
    username = f"@{user.username}" if user.username else "None"

    with get_conn() as conn:
        # الحفاظ على تاريخ الانتهاء إن وُجد مسبقاً
        conn.execute('''
            INSERT INTO users (user_id, username, expiration_date)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET username = excluded.username
        ''', (user_id, username, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

    await update.message.reply_text(
        f"🚀 *تم تفعيل البوت*\n"
        f"🆔 ID: `{user_id}`\n"
        f"👤 User: {username}",
        parse_mode="Markdown"
    )
    logger.info(f"New user: {username} ({user_id})")


async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    if len(context.args) < 2:
        await update.message.reply_text("⚠️ الاستخدام: `/add @username 30`", parse_mode="Markdown")
        return

    target = context.args[0]
    try:
        days = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ عدد الأيام يجب أن يكون رقماً.")
        return

    # 999 = اشتراك دائم (100 سنة)
    actual_days = 36500 if days == 999 else days
    exp = (datetime.now() + timedelta(days=actual_days)).strftime('%Y-%m-%d %H:%M:%S')

    with get_conn() as conn:
        if target.startswith('@'):
            cur = conn.execute(
                "UPDATE users SET expiration_date = ? WHERE username = ?", (exp, target)
            )
        else:
            try:
                cur = conn.execute(
                    "UPDATE users SET expiration_date = ? WHERE user_id = ?", (exp, int(target))
                )
            except ValueError:
                await update.message.reply_text("❌ المعرّف يجب أن يكون رقماً أو @username.")
                return

        if cur.rowcount > 0:
            label = "دائم ♾️" if days == 999 else f"{days} يوم"
            await update.message.reply_text(f"✅ تم تفعيل {target} لمدة {label}")
            logger.info(f"Admin added {target} for {days} days.")
        else:
            await update.message.reply_text("❌ المستخدم غير موجود. يجب أن يبدأ بـ /start أولاً.")


async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر جديد: إلغاء اشتراك مستخدم."""
    if not is_admin(update):
        return

    if not context.args:
        await update.message.reply_text("⚠️ الاستخدام: `/remove @username`", parse_mode="Markdown")
        return

    target = context.args[0]
    expired = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    with get_conn() as conn:
        if target.startswith('@'):
            cur = conn.execute(
                "UPDATE users SET expiration_date = ? WHERE username = ?", (expired, target)
            )
        else:
            cur = conn.execute(
                "UPDATE users SET expiration_date = ? WHERE user_id = ?", (expired, int(target))
            )

        if cur.rowcount > 0:
            await update.message.reply_text(f"🚫 تم إلغاء اشتراك {target}.")
        else:
            await update.message.reply_text("❌ المستخدم غير موجود.")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with get_conn() as conn:
        active   = conn.execute("SELECT COUNT(*) FROM users WHERE expiration_date > ?", (now,)).fetchone()[0]
        inactive = conn.execute("SELECT COUNT(*) FROM users WHERE expiration_date <= ?", (now,)).fetchone()[0]
        users    = conn.execute(
            "SELECT username, user_id, expiration_date FROM users WHERE expiration_date > ? ORDER BY expiration_date",
            (now,)
        ).fetchall()

    lines = [f"📊 *إحصائيات البوت*\n✅ نشط: {active} | ❌ منتهي: {inactive}\n"]
    for u in users:
        exp_date = u['expiration_date'][:10]
        lines.append(f"👤 {u['username']} (`{u['user_id']}`) — حتى {exp_date}")

    await update.message.reply_text("\n".join(lines) if users else "لا يوجد مشتركون نشطون.", parse_mode="Markdown")


async def send_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    text = " ".join(context.args).strip()
    if not text:
        await update.message.reply_text("⚠️ أرسل نصاً بعد الأمر.")
        return

    with get_conn() as conn:
        ids = [row[0] for row in conn.execute("SELECT user_id FROM users").fetchall()]

    success, failed = 0, 0
    for uid in ids:
        try:
            await context.bot.send_message(chat_id=uid, text=text)
            success += 1
        except Exception as e:
            logger.warning(f"Failed to send to {uid}: {e}")
            failed += 1

    await update.message.reply_text(f"📢 تم الإرسال\n✅ نجح: {success} | ❌ فشل: {failed}")


async def my_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر جديد: يتيح للمستخدم معرفة تاريخ انتهاء اشتراكه."""
    user_id = update.effective_user.id
    with get_conn() as conn:
        row = conn.execute(
            "SELECT expiration_date FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()

    if not row:
        await update.message.reply_text("❌ أنت غير مسجّل. استخدم /start أولاً.")
        return

    exp = datetime.strptime(row['expiration_date'], '%Y-%m-%d %H:%M:%S')
    if exp > datetime.now():
        remaining = (exp - datetime.now()).days
        await update.message.reply_text(
            f"✅ اشتراكك نشط\n📅 ينتهي: {exp.strftime('%Y-%m-%d')}\n⏳ المتبقي: {remaining} يوم"
        )
    else:
        await update.message.reply_text("❌ اشتراكك منتهٍ. تواصل مع المدير.")


# ─── نقطة البداية ─────────────────────────────────────────────────────────────
if __name__ == '__main__':


    init_db()
    threading.Thread(target=run_wakeup_server, daemon=True).start()

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",  start))
    app.add_handler(CommandHandler("add",    add_user))
    app.add_handler(CommandHandler("remove", remove_user))
    app.add_handler(CommandHandler("stats",  stats))
    app.add_handler(CommandHandler("send",   send_all))
    app.add_handler(CommandHandler("status", my_status))

    logger.info("Bot started.")
    app.run_polling()
