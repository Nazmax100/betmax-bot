# أضف هذا الجزء ضمن أوامر المدير في الملف
async def get_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # عدد الدائمين
        c.execute('SELECT COUNT(*) FROM authorized_users WHERE expiry_date IS NULL')
        perm_count = c.fetchone()[0]
        
        # عدد التجربة النشطين
        c.execute('SELECT COUNT(*) FROM authorized_users WHERE expiry_date > ?', (now,))
        trial_active = c.fetchone()[0]
        
        # عدد الذين انتهت تجربتهم ولم يحذفوا بعد
        c.execute('SELECT COUNT(*) FROM authorized_users WHERE expiry_date <= ?', (now,))
        expired_count = c.fetchone()[0]
        
        conn.close()
        
        stats_msg = (
            f"📊 **إحصائيات البوت الحالية:**\n\n"
            f"✅ مشتركين دائمين: {perm_count}\n"
            f"⏳ تجربة نشطة: {trial_active}\n"
            f"❌ انتهت تجربتهم: {expired_count}\n"
            f"👥 الإجمالي: {perm_count + trial_active + expired_count}"
        )
        await update.message.reply_text(stats_msg, parse_mode='Markdown')

# لا تنسَ إضافة المعالج في أسفل الكود (main)
# app.add_handler(CommandHandler("stats", get_stats))
