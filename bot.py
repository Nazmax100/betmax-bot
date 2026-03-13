import os
import sqlite3
import threading
import logging
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "PUT_TOKEN_HERE"
ADMIN_ID = 123456789

CHANNEL_ID = -1001234567890
CHANNEL_LINK = "https://t.me/yourchannel"

# ───────── Wakeup Server ─────────

class WakeUpHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot Running")

    def log_message(self, format, *args):
        pass


def run_server():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(('0.0.0.0', port), WakeUpHandler).serve_forever()


# ───────── Database ─────────

def init_db():
    conn = sqlite3.connect('users.db')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        expiration_date TEXT
        )
    ''')
    conn.commit()
    conn.close()


def get_conn():
    conn = sqlite3.connect('users.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# ───────── Start Menu ─────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        [InlineKeyboardButton("📝 التسجيل", callback_data="register")],
        [InlineKeyboardButton("🎁 تجربة مجانية", callback_data="trial")],
        [InlineKeyboardButton("💰 عرض الاشتراك", callback_data="offer")],
        [InlineKeyboardButton("📊 حالة اشتراكي", callback_data="status")],
        [InlineKeyboardButton("📞 تواصل مع الإدارة", callback_data="admin")]
    ]

    await update.message.reply_text(
        "👋 مرحباً بك في بوت توقعات كرة القدم ⚽",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ───────── Buttons ─────────

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    username = f"@{query.from_user.username}" if query.from_user.username else "None"

    # طلب التسجيل
    if query.data == "register":

        await query.message.reply_text(
            "📩 تم إرسال طلب التسجيل للإدارة."
        )

        await context.bot.send_message(
            ADMIN_ID,
            f"📥 طلب تسجيل جديد\nID: {user_id}\nUSER: {username}"
        )

    # تجربة مجانية
    elif query.data == "trial":

        exp = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')

        conn = get_conn()

        conn.execute(
            "INSERT OR REPLACE INTO users VALUES (?,?,?)",
            (user_id, username, exp)
        )

        conn.commit()
        conn.close()

        await query.message.reply_text(
            f"🎁 حصلت على تجربة مجانية!\n\nادخل القناة:\n{CHANNEL_LINK}"
        )

    # عرض الاشتراك
    elif query.data == "offer":

        await query.message.reply_text(
            "💰 عروض الاشتراك:\n\n"
            "7 أيام = 5$\n"
            "30 يوم = 15$\n"
            "90 يوم = 35$\n\n"
            "للاشتراك تواصل مع الإدارة."
        )

    # حالة الاشتراك
    elif query.data == "status":

        conn = get_conn()

        row = conn.execute(
            "SELECT expiration_date FROM users WHERE user_id=?",
            (user_id,)
        ).fetchone()

        conn.close()

        if not row:
            await query.message.reply_text("❌ لا يوجد اشتراك")
            return

        exp = datetime.strptime(row['expiration_date'], '%Y-%m-%d %H:%M:%S')

        if exp > datetime.now():

            remaining = (exp - datetime.now()).days

            await query.message.reply_text(
                f"✅ اشتراكك نشط\n"
                f"📅 ينتهي: {exp.strftime('%Y-%m-%d')}\n"
                f"⏳ المتبقي: {remaining} يوم"
            )

        else:
            await query.message.reply_text("❌ اشتراكك منتهي")

    # تواصل مع الإدارة
    elif query.data == "admin":

        await query.message.reply_text(
            "📞 تواصل مع الإدارة:\n@YourUsername"
        )


# ───────── Admin Commands ─────────

async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        return

    if len(context.args) < 2:
        await update.message.reply_text("/add USER_ID DAYS")
        return

    user_id = int(context.args[0])
    days = int(context.args[1])

    exp = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')

    conn = get_conn()

    conn.execute(
        "INSERT OR REPLACE INTO users VALUES (?,?,?)",
        (user_id, "None", exp)
    )

    conn.commit()
    conn.close()

    await update.message.reply_text("✅ تم تفعيل الاشتراك")

    try:
        await context.bot.send_message(
            user_id,
            f"✅ تم تفعيل اشتراكك!\n\nادخل القناة:\n{CHANNEL_LINK}"
        )
    except:
        pass


async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        return

    user_id = int(context.args[0])

    exp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = get_conn()

    conn.execute(
        "UPDATE users SET expiration_date=? WHERE user_id=?",
        (exp, user_id)
    )

    conn.commit()
    conn.close()

    await update.message.reply_text("🚫 تم إلغاء الاشتراك")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        return

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = get_conn()

    active = conn.execute(
        "SELECT COUNT(*) FROM users WHERE expiration_date > ?",
        (now,)
    ).fetchone()[0]

    inactive = conn.execute(
        "SELECT COUNT(*) FROM users WHERE expiration_date <= ?",
        (now,)
    ).fetchone()[0]

    conn.close()

    await update.message.reply_text(
        f"📊 الإحصائيات\n\n"
        f"نشط: {active}\n"
        f"منتهي: {inactive}"
    )


async def send_all(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        return

    text = " ".join(context.args)

    if not text:
        return

    conn = get_conn()

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    ids = [
        row[0] for row in conn.execute(
            "SELECT user_id FROM users WHERE expiration_date > ?",
            (now,)
        ).fetchall()
    ]

    conn.close()

    sent = 0

    for uid in ids:

        try:
            await context.bot.send_message(uid, text)
            sent += 1
        except:
            pass

    await update.message.reply_text(f"📢 تم الإرسال إلى {sent}")


# ───────── Auto remove expired users ─────────

async def check_subscriptions(context: ContextTypes.DEFAULT_TYPE):

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = get_conn()

    users = conn.execute(
        "SELECT user_id FROM users WHERE expiration_date <= ?",
        (now,)
    ).fetchall()

    conn.close()

    for u in users:

        try:
            await context.bot.ban_chat_member(CHANNEL_ID, u['user_id'])
            await context.bot.unban_chat_member(CHANNEL_ID, u['user_id'])
        except:
            pass


# ───────── Run Bot ─────────

if __name__ == "__main__":

    init_db()

    threading.Thread(target=run_server, daemon=True).start()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(CommandHandler("add", add_user))
    app.add_handler(CommandHandler("remove", remove_user))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("send", send_all))

    app.add_handler(CallbackQueryHandler(buttons))

    app.job_queue.run_repeating(check_subscriptions, interval=3600, first=10)

    logger.info("Bot started")

    app.run_polling()
