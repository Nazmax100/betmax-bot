import sqlite3
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --- الإعدادات ---
TOKEN = '7675556594:AAGQpCGTAIdQ7YPBTeePTAKGxtb25-BRL08'
ADMIN_ID = 7528722019 

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    # تخزين رقم المستخدم واسمه
    c.execute('''CREATE TABLE IF NOT EXISTS authorized_users 
                 (user_id INTEGER PRIMARY KEY, username TEXT)''')
    conn.commit()
    conn.close()

# --- أوامر المدير فقط ---

# 1. إضافة مستخدم يدوياً عبر اليوزرنيم
async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        if not context.args:
            await update.message.reply_text("❌ أرسل اليوزرنيم بعد الأمر. مثال: /add mohamed_123")
            return
        
        target_username = context.args[0].replace('@', '').lower()
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        # هنا سيتم إضافة اليوزرنيم للقائمة، وعندما يدخل المستخدم يضغط start سيتعرف عليه البوت
        c.execute('INSERT OR IGNORE INTO authorized_users (username) VALUES (?)', (target_username,))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ تمت إضافة {target_username} للقائمة. اطلب منه الآن الدخول للبوت وضغط /start")

# 2. إرسال بوست "خام" بدون مقدمات
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        if not context.args:
            await update.message.reply_text("❌ اكتب رسالتك بعد الأمر.")
            return
        
        message_to_send = " ".join(context.args)
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('SELECT user_id FROM authorized_users WHERE user_id IS NOT NULL')
        users = c.fetchall()
        conn.close()

        sent_count = 0
        for user in users:
            try:
                # إرسال الرسالة كما هي بالضبط
                await context.bot.send_message(chat_id=user[0], text=message_to_send, parse_mode='Markdown')
                sent_count += 1
            except: continue
        await update.message.reply_text(f"🚀 تم إرسال الرسالة إلى {sent_count} مشترك.")

# --- أوامر المستخدمين ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username.lower() if update.effective_user.username else ""
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    # التحقق هل اليوزرنيم مضاف مسبقاً من طرفك
    c.execute('SELECT * FROM authorized_users WHERE username=?', (username,))
    row = c.fetchone()
    
    if row:
        # تحديث بياناته برقم الـ ID لكي يستلم الرسائل
        c.execute('UPDATE authorized_users SET user_id=? WHERE username=?', (user_id, username))
        conn.commit()
        await update.message.reply_text("✅ تم تفعيل اشتراكك بنجاح! ستصلك التوقعات هنا.")
    else:
        await update.message.reply_text("🚫 عذراً، أنت غير مسجل في قائمة المسموح لهم. يرجى التواصل مع الإدارة.")
    conn.close()

if __name__ == '__main__':
    init_db()
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_user))
    app.add_handler(CommandHandler("send", broadcast))
    
    app.run_polling()
