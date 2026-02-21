async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # التأكد من أن المرسل هو المدير
    if update.effective_user.id != ADMIN_ID:
        return

    try:
        # استخراج المعطيات: /add [user_id] [days]
        user_id = int(context.args[0])
        days = int(context.args[1])
        
        expiration_date = datetime.now() + timedelta(days=days)
        
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        # تحديث أو إضافة المستخدم مع تاريخ انتهاء حسب عدد الأيام
        c.execute("INSERT OR REPLACE INTO users (user_id, expiration_date) VALUES (?, ?)",
                  (user_id, expiration_date.strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
        conn.close()

        msg = f"✅ تم تفعيل الاشتراك بنجاح!\n👤 الآيدي: `{user_id}`\n⏳ المدة: {days} يوم/أيام\n📅 ينتهي في: {expiration_date.strftime('%Y-%m-%d')}"
        await update.message.reply_text(msg, parse_mode='Markdown')
        
    except (IndexError, ValueError):
        await update.message.reply_text("⚠️ خطأ! الطريقة الصحيحة:\n`/add [ID] [عدد_الأيام]`\nمثال: `/add 12345 3` للتجربة.")
