async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        # استلام المدخلات: /add @username days
        target_input = context.args[0]
        days = int(context.args[1])
        
        # تجهيز تاريخ الانتهاء
        if days == 999:
            exp_date = datetime.now() + timedelta(days=36500)
            status = "دائم ♾️"
        else:
            exp_date = datetime.now() + timedelta(days=days)
            status = f"{days} يوم"

        conn = sqlite3.connect('users.db')
        c = conn.cursor()

        # البحث وتحديث التاريخ بناءً على اسم المستخدم أو الآيدي
        if target_input.startswith('@'):
            c.execute("UPDATE users SET expiration_date = ? WHERE username = ?", 
                      (exp_date.strftime('%Y-%m-%d %H:%M:%S'), target_input))
        else:
            c.execute("UPDATE users SET expiration_date = ? WHERE user_id = ?", 
                      (exp_date.strftime('%Y-%m-%d %H:%M:%S'), int(target_input)))
        
        if c.rowcount > 0:
            conn.commit()
            await update.message.reply_text(f"✅ تم تفعيل اشتراك {target_input} لمدة {status}")
        else:
            await update.message.reply_text(f"❌ لم أجد مستخدم بهذا الاسم ({target_input}) في قاعدة البيانات. يجب أن يضغط المستخدم على /start أولاً.")
        
        conn.close()
    except:
        await update.message.reply_text("⚠️ الطريقة: `/add @username الأيام`\nمثال: `/add @Ahmad 3`")
