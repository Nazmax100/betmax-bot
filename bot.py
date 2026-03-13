import os
import sqlite3
import threading
import logging
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ───────── CONFIG ─────────
TOKEN = "7675556594:AAGQpCGTAIdQ7YPBTeePTAKGxtb25-BRL08"
ADMIN_ID = 7528722019

CHANNEL_ID = -1001234567890   # ← معرف قناتك (اختياري)

# ───────── Wakeup Server (لمنع النوم على Render/Railway) ─────────

class WakeUpHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is Running!")
    def log_message(self, format, *args):
        pass

def run_server():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(('0.0.0.0', port), WakeUpHandler).serve_forever()

# ───────── Database ─────────

def init_db():
    conn = sqlite3.connect('users.db')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
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

def is_active(user_id: int) -> bool:
    conn = get_conn()
    row = conn.execute(
        "SELECT expiration_date FROM users WHERE user_id=?", (user_id,)
    ).fetchone()
    conn.close()
    if not row:
        return False
    exp = datetime.strptime(row['expiration_date'], '%Y-%m-%d %H:%M:%S')
    return exp > datetime.now()

# ───────── /start ─────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id

    if uid == ADMIN_ID:
        text = (
            "👑 *لوحة تحكم المشرف*\n\n"
            "الأوامر المتاحة:\n"
            "➕ `/add ID DAYS` — إضافة مشترك\n"
            "➖ `/remove ID` — إلغاء اشتراك\n"
            "📊 `/stats` — الإحصائيات\n"
            "📢 `/send نص` — إرسال للجميع\n"
            "👥 `/list` — قائمة المشتركين"
        )
        await update.message.reply_text(text, parse_mode="Markdown")
        return

    keyboard = [
        [InlineKeyboardButton("📝 طلب الاشتراك", callback_data="register")],
        [InlineKeyboardButton("🎁 تجربة مجانية", callback_data="trial")],
        [InlineKeyboardButton("📊 حالة اشتراكي", callback_data="status")],
        [InlineKeyboardButton("📞 تواصل مع الإدارة", callback_data="admin")]
    ]
    await update.message.reply_text(
        f"👋 مرحباً *{user.first_name}*!\n\n"
        "⚽ *بوت توقعات كرة القدم*\n\n"
        "اختر من القائمة أدناه:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ───────── Callback Buttons ─────────

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    username = f"@{query.from_user.username}" if query.from_user.username else "بدون يوزر"

    if query.data == "register":
        try:
            await context.bot.send_message(
                ADMIN_ID,
                f"📥 طلب اشتراك جديد\n\n"
                f"🆔 ID: {user_id}\n"
                f"👤 اليوزر: {username}\n"
                f"📅 الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                f"لتفعيل الاشتراك: /add {user_id} 30"
            )
            logger.info(f"✅ Admin notified about new registration from {user_id}")
            await query.message.reply_text("📩 تم إرسال طلب اشتراكك للإدارة.\nسيتم التواصل معك قريباً ✅")
        except Exception as e:
            logger.error(f"❌ Failed to notify admin: {e}")
            await query.message.reply_text("📩 تم استلام طلبك.\nسيتم التواصل معك قريباً ✅")

    elif query.data == "trial":
        # تحقق إن كان استخدم التجربة من قبل
        conn = get_conn()
        row = conn.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,)).fetchone()
        conn.close()

        if row:
            await query.message.reply_text(
                "⚠️ لقد استخدمت التجربة المجانية من قبل.\n"
                "للاشتراك تواصل مع الإدارة: @betmax_team"
            )
            return

        # تفعيل حتى نهاية اليوم الحالي (منتصف الليل)
        end_of_day = datetime.now().replace(hour=23, minute=59, second=59)
        exp = end_of_day.strftime('%Y-%m-%d %H:%M:%S')

        conn = get_conn()
        conn.execute("INSERT OR REPLACE INTO users VALUES (?,?,?)", (user_id, username, exp))
        conn.commit()
        conn.close()

        await query.message.reply_text(
            f"🎁 *تم تفعيل تجربتك المجانية!*\n\n"
            f"⏳ تنتهي اليوم في: *11:59 مساءً*\n\n"
            "ستصلك التوقعات تلقائياً ⚽🎯",
            parse_mode="Markdown"
        )

        # إشعار الإدارة
        try:
            await context.bot.send_message(
                ADMIN_ID,
                f"🎁 تجربة مجانية مُفعَّلة\n\n"
                f"🆔 ID: {user_id}\n"
                f"👤 اليوزر: {username}\n"
                f"📅 تنتهي: {end_of_day.strftime('%Y-%m-%d 23:59')}"
            )
        except Exception as e:
            logger.error(f"Failed to notify admin about trial: {e}")

        # جدولة رسالة انتهاء الاشتراك
        seconds_until_end = (end_of_day - datetime.now()).total_seconds()
        context.job_queue.run_once(
            send_expiry_message,
            when=seconds_until_end,
            data=user_id,
            name=f"expiry_{user_id}"
        )

    elif query.data == "status":
        conn = get_conn()
        row = conn.execute(
            "SELECT expiration_date FROM users WHERE user_id=?", (user_id,)
        ).fetchone()
        conn.close()

        if not row:
            await query.message.reply_text(
                f"❌ لا يوجد اشتراك نشط.\n\n🆔 معرفك: `{user_id}`",
                parse_mode="Markdown"
            )
            return

        exp = datetime.strptime(row['expiration_date'], '%Y-%m-%d %H:%M:%S')
        if exp > datetime.now():
            remaining = (exp - datetime.now()).days
            await query.message.reply_text(
                f"✅ *اشتراكك نشط*\n\n"
                f"📅 ينتهي: *{exp.strftime('%Y-%m-%d')}*\n"
                f"⏳ المتبقي: *{remaining} يوم*",
                parse_mode="Markdown"
            )
        else:
            keyboard = [[InlineKeyboardButton("💬 تواصل مع الإدارة", url="https://t.me/betmax_team")]]
            await query.message.reply_text(
                "❌ *اشتراكك منتهٍ*\n\nللتجديد تواصل مع الإدارة 👇",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
    elif query.data == "admin":
        keyboard = [[InlineKeyboardButton("💬 تواصل مع الإدارة", url="https://t.me/betmax_team")]]
        await query.message.reply_text(
            "📞 *تواصل مع الإدارة:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

# ───────── Expiry Notification ─────────

async def send_expiry_message(context: ContextTypes.DEFAULT_TYPE):
    user_id = context.job.data
    keyboard = [[InlineKeyboardButton("💬 تواصل مع الإدارة", url="https://t.me/betmax_team")]]
    try:
        await context.bot.send_message(
            user_id,
            "⏰ *انتهت تجربتك المجانية!*\n\n"
            "نأمل أنك استمتعت بتوقعاتنا ⚽\n\n"
            "للاستمرار في استقبال التوقعات تواصل مع الإدارة 👇",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    except Exception:
        pass

# ───────── Admin: /add ─────────

async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) < 2:
        await update.message.reply_text("📝 الاستخدام:\n`/add USER_ID DAYS`", parse_mode="Markdown")
        return
    try:
        user_id = int(context.args[0])
        days = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ الـ ID وعدد الأيام يجب أن تكون أرقاماً.")
        return

    exp = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO users VALUES (?,?,?)", (user_id, "None", exp))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ تم تفعيل اشتراك `{user_id}` لمدة *{days}* يوم\n"
        f"📅 ينتهي: {exp[:10]}",
        parse_mode="Markdown"
    )
    try:
        await context.bot.send_message(
            user_id,
            f"🎉 *تم تفعيل اشتراكك!*\n\n"
            f"📅 مدة الاشتراك: *{days} يوم*\n"
            f"🗓️ ينتهي في: *{exp[:10]}*\n\n"
            "ستصلك التوقعات تلقائياً ⚽🎯",
            parse_mode="Markdown"
        )
    except Exception:
        await update.message.reply_text("⚠️ لم يتم إشعار المستخدم (لم يبدأ المحادثة)")

# ───────── Admin: /remove ─────────

async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("📝 الاستخدام:\n`/remove USER_ID`", parse_mode="Markdown")
        return
    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID غير صحيح.")
        return

    exp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_conn()
    conn.execute("UPDATE users SET expiration_date=? WHERE user_id=?", (exp, user_id))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"🚫 تم إلغاء اشتراك `{user_id}`.", parse_mode="Markdown")
    try:
        await context.bot.send_message(user_id, "❌ تم إيقاف اشتراكك.\nللتجديد تواصل مع الإدارة.")
    except Exception:
        pass

# ───────── Admin: /stats ─────────

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_conn()
    active = conn.execute("SELECT COUNT(*) FROM users WHERE expiration_date > ?", (now,)).fetchone()[0]
    inactive = conn.execute("SELECT COUNT(*) FROM users WHERE expiration_date <= ?", (now,)).fetchone()[0]
    total = active + inactive
    conn.close()
    await update.message.reply_text(
        f"📊 *إحصائيات البوت:*\n\n"
        f"👥 الإجمالي: *{total}*\n"
        f"✅ نشط: *{active}*\n"
        f"🔴 منتهي: *{inactive}*",
        parse_mode="Markdown"
    )

# ───────── Admin: /list ─────────

async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_conn()
    rows = conn.execute(
        "SELECT user_id, username, expiration_date FROM users ORDER BY expiration_date DESC"
    ).fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("📭 لا يوجد مستخدمون.")
        return

    text = "👥 *قائمة المشتركين:*\n\n"
    for row in rows:
        exp = datetime.strptime(row['expiration_date'], '%Y-%m-%d %H:%M:%S')
        active = "🟢" if exp > datetime.now() else "🔴"
        days_left = (exp - datetime.now()).days
        text += (
            f"{active} `{row['user_id']}` {row['username'] or ''}\n"
            f"   📅 {exp.strftime('%Y-%m-%d')} ({max(0,days_left)} يوم)\n\n"
        )

    if len(text) > 4000:
        for i in range(0, len(text), 4000):
            await update.message.reply_text(text[i:i+4000], parse_mode="Markdown")
    else:
        await update.message.reply_text(text, parse_mode="Markdown")

# ───────── Admin: /send ─────────

async def send_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    # أخذ النص الكامل بعد /send مع الحفاظ على التنسيق والفراغات
    full_text = update.message.text
    if "\n" in full_text:
        text = full_text.split("\n", 1)[1] if full_text.startswith("/send") else full_text
        first_line = full_text.split("\n")[0]
        after_cmd = first_line[5:].strip()  # ما بعد /send في السطر الأول
        if after_cmd:
            text = after_cmd + "\n" + "\n".join(full_text.split("\n")[1:])
        else:
            text = "\n".join(full_text.split("\n")[1:])
    else:
        text = full_text[5:].strip()  # إزالة /send فقط

    if not text:
        await update.message.reply_text("📝 الاستخدام:\n`/send نص التوقع هنا`", parse_mode="Markdown")
        return

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_conn()
    ids = [row[0] for row in conn.execute(
        "SELECT user_id FROM users WHERE expiration_date > ?", (now,)
    ).fetchall()]
    conn.close()

    if not ids:
        await update.message.reply_text("📭 لا يوجد مشتركون نشطون.")
        return

    progress = await update.message.reply_text(f"📤 جاري الإرسال إلى {len(ids)} مشترك...")
    sent = 0
    failed = 0
    for uid in ids:
        try:
            # إرسال الرسالة بنفس التنسيق تماماً بدون أي إضافات
            await context.bot.copy_message(
                chat_id=uid,
                from_chat_id=update.effective_chat.id,
                message_id=update.message.message_id
            )
            sent += 1
        except Exception:
            failed += 1

    await progress.edit_text(
        f"✅ *تم الإرسال!*\n\n"
        f"📨 وصل إلى: *{sent}* مشترك\n"
        f"❌ فشل: *{failed}*",
        parse_mode="Markdown"
    )

# ───────── Auto Remove Expired (كل ساعة) ─────────

async def check_subscriptions(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_conn()
    users = conn.execute(
        "SELECT user_id FROM users WHERE expiration_date <= ?", (now,)
    ).fetchall()
    conn.close()
    for u in users:
        keyboard = [[InlineKeyboardButton("💬 تواصل مع الإدارة", url="https://t.me/betmax_team")]]
        try:
            await context.bot.send_message(
                u['user_id'],
                "⏰ *انتهى اشتراكك!*\n\n"
                "للتجديد تواصل مع الإدارة 👇",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        except Exception:
            pass
        # طرد من القناة
        try:
            await context.bot.ban_chat_member(CHANNEL_ID, u['user_id'])
            await context.bot.unban_chat_member(CHANNEL_ID, u['user_id'])
        except Exception:
            pass

# ───────── Main ─────────

if __name__ == "__main__":
    init_db()
    threading.Thread(target=run_server, daemon=True).start()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_user))
    app.add_handler(CommandHandler("remove", remove_user))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("list", list_users))
    app.add_handler(CommandHandler("send", send_all))
    app.add_handler(CallbackQueryHandler(buttons))

    if app.job_queue:
        app.job_queue.run_repeating(check_subscriptions, interval=3600, first=10)

    logger.info("✅ Bot started successfully!")
    app.run_polling(drop_pending_updates=True)
