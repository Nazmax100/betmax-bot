async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ الطريقة:\n`/add @username الأيام`\nمثال: `/add @Ahmad 3`",
            parse_mode="Markdown"
        )
        return

    try:
        target_input = context.args[0]
        days = int(context.args[1])

        # تحديد تاريخ الانتهاء
        if days == 999:
            exp_date = datetime.now() + timedelta(days=36500)
            status = "دائم ♾️"
        else:
            exp_date = datetime.now() + timedelta(days=days)
            status = f"{days} يوم"

        conn = sqlite3.connect('users.db')
        c = conn.cursor()

        expiration_str = exp_date.strftime('%Y-%m-%d %H:%M:%S')

        # التحديث باليوزرنيم
        if target_input.startswith('@'):
            username = target_input.replace('@', '')
            c.execute(
                "UPDATE users SET expiration_date = ? WHERE username = ?",
                (expiration_str, username)
            )
        else:
            user_id = int(target_input)
            c.execute(
                "UPDATE users SET expiration_date = ? WHERE user_id = ?",
                (expiration_str, user_id)
            )

        if c.rowcount > 0:
            conn.commit()
            await update.message.reply_text(
                f"✅ تم تفعيل اشتراك {target_input} لمدة {status}"
            )
        else:
            await update.message.reply_text(
                f"❌ لم أجد مستخدم ({target_input}) في قاعدة البيانات.\n"
                "يجب أن يضغط المستخدم على /start أولاً."
            )

        conn.close()

    except ValueError:
        await update.message.reply_text("❌ عدد الأيام يجب أن يكون رقمًا صحيحًا.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ حدث خطأ:\n{str(e)}")
