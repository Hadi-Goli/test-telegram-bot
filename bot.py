import os
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from database import Database

# Conversation states
REGISTRATION_NAME, REGISTRATION_EMAIL = range(2)
SELECT_PRESENTER, ASK_QUESTION = range(2, 4)
ADMIN_FILTER_PRESENTER, ADMIN_FILTER_USER = range(4, 6)
ADMIN_SELECT_USER = 6

db = Database()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await db.get_user(update.effective_user.id)

    if user:
        is_admin_val = await is_admin(update.effective_user.id)
        keyboard = [
            ["پرسیدن سوال"],
            ["پنل مدیریت"] if is_admin_val else []
        ]
        keyboard = [row for row in keyboard if row]  # Remove empty rows

        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            f"خوش آمدید، {user['name']}! چه کاری می‌خواهید انجام دهید؟",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            "به ربات پرسش و پاسخ گروه کاربران لینوکس تهران خوش آمدید!\n\n"
            "لطفاً برای ادامه ثبت نام کنید.\n"
            "نام کامل شما چیست؟"
        )
        return REGISTRATION_NAME


async def registration_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    await update.message.reply_text("عالی! حالا لطفاً آدرس ایمیل خود را وارد کنید:")
    return REGISTRATION_EMAIL


async def registration_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = update.message.text
    name = context.user_data['name']

    if '@' not in email:
        await update.message.reply_text("لطفاً یک آدرس ایمیل معتبر وارد کنید:")
        return REGISTRATION_EMAIL

    # Check if this is the first admin
    first_admin_id = os.getenv("FIRST_ADMIN_ID")
    is_first_admin = first_admin_id and str(update.effective_user.id) == first_admin_id

    success = await db.register_user(update.effective_user.id, name, email, is_admin=is_first_admin)
    if success:
        is_admin_val = await is_admin(update.effective_user.id)
        keyboard = [
            ["پرسیدن سوال"],
            ["پنل مدیریت"] if is_admin_val else []
        ]
        keyboard = [row for row in keyboard if row]

        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            f"ثبت نام با موفقیت انجام شد! خوش آمدید، {name}!",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text("ثبت نام ناموفق بود. لطفاً دوباره با /start تلاش کنید.")

    return ConversationHandler.END


async def ask_question_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await db.get_user(update.effective_user.id)

    if not user:
        await update.message.reply_text("لطفاً ابتدا با استفاده از /start ثبت نام کنید.")
        return ConversationHandler.END

    presenters = await db.get_presenters()

    if not presenters:
        await update.message.reply_text(
            "هنوز ارائه‌دهنده‌ای موجود نیست. لطفاً با مدیر تماس بگیرید."
        )
        return ConversationHandler.END

    # Create schedule message
    schedule_text = "برنامه رویداد:\n\n"
    for p in presenters:
        time_str = f" ({p['start_time']} - {p['end_time']})" if p['start_time'] else ""
        title_str = f"\n📌 {p['title']}" if p['title'] else ""
        schedule_text += f"👤 {p['name']}{time_str}{title_str}\n\n"
    
    schedule_text += "از کدام ارائه‌دهنده می‌خواهید سوال بپرسید؟"

    keyboard = [[p['name']] for p in presenters]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

    await update.message.reply_text(
        schedule_text,
        reply_markup=reply_markup
    )
    return SELECT_PRESENTER


async def select_presenter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    presenter_name = update.message.text
    presenters = await db.get_presenters()
    presenter_names = [p['name'] for p in presenters]

    if presenter_name not in presenter_names:
        await update.message.reply_text("لطفاً یک ارائه‌دهنده معتبر از لیست انتخاب کنید.")
        return SELECT_PRESENTER

    context.user_data['presenter'] = presenter_name
    await update.message.reply_text(
        f"عالی! لطفاً سوال خود را برای {presenter_name} بنویسید:",
        reply_markup=ReplyKeyboardRemove()
    )
    return ASK_QUESTION


async def receive_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question = update.message.text
    presenter:str = context.user_data['presenter']
    user = await db.get_user(update.effective_user.id)

    success = await db.add_question(
        update.effective_user.id,
        user['name'],
        presenter,
        question
    )
    presenter_hashtag = "#" + presenter.split(" ")[-1]

    if success:
        # Send to channel
        channel_id = os.getenv("QUESTIONS_CHANNEL_ID")
        if channel_id:
            try:
                await context.bot.send_message(
                    chat_id=channel_id,
                    text=f"❓ سوال جدید\n\n👤 از: {user['name']}\n🎤 برای: {presenter}\n\n📝 سوال:\n{question}\n  {presenter_hashtag}"
                )
            except Exception as e:
                print(f"Failed to send to channel: {e}")

        is_admin_val = await is_admin(update.effective_user.id)
        keyboard = [
            ["پرسیدن سوال"],
            ["پنل مدیریت"] if is_admin_val else []
        ]
        keyboard = [row for row in keyboard if row]

        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "سوال شما با موفقیت ثبت شد!",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text("ثبت سوال ناموفق بود. لطفاً دوباره تلاش کنید.")

    return ConversationHandler.END


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        await update.message.reply_text("شما دسترسی مدیریت ندارید.")
        return

    keyboard = [
        ["مشاهده همه سوالات"],
        ["فیلتر بر اساس ارائه‌دهنده"],
        ["فیلتر بر اساس کاربر"],
        ["افزودن ارائه‌دهنده"],
        ["مدیریت کاربران"],
        ["بازگشت به منوی اصلی"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "پنل مدیریت - یک گزینه را انتخاب کنید:",
        reply_markup=reply_markup
    )


async def view_all_questions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return

    questions = await db.get_questions()

    if not questions:
        await update.message.reply_text("هنوز سوالی ثبت نشده است.")
        return

    response = "همه سوالات:\n\n"
    for q in questions:
        response += f"شناسه: {q['id']}\n"
        response += f"از طرف: {q['user_name']}\n"
        response += f"به: {q['presenter_name']}\n"
        response += f"سوال: {q['question']}\n"
        response += f"زمان: {q['created_at']}\n"
        response += "-" * 40 + "\n\n"

    # Split long messages
    if len(response) > 4000:
        for i in range(0, len(response), 4000):
            await update.message.reply_text(response[i:i+4000])
    else:
        await update.message.reply_text(response)


async def filter_by_presenter_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return ConversationHandler.END

    presenters = await db.get_presenters()

    if not presenters:
        await update.message.reply_text("ارائه‌دهنده‌ای موجود نیست.")
        return ConversationHandler.END

    keyboard = [[p['name']] for p in presenters]
    keyboard.append(["لغو"])
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

    await update.message.reply_text(
        "یک ارائه‌دهنده را برای فیلتر کردن سوالات انتخاب کنید:",
        reply_markup=reply_markup
    )
    return ADMIN_FILTER_PRESENTER


async def filter_by_presenter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "لغو":
        await admin_panel(update, context)
        return ConversationHandler.END

    presenter = update.message.text
    questions = await db.get_questions(presenter_name=presenter)

    if not questions:
        await update.message.reply_text(f"سوالی برای {presenter} وجود ندارد.")
    else:
        response = f"سوالات برای {presenter}:\n\n"
        for q in questions:
            response += f"شناسه: {q['id']}\n"
            response += f"از طرف: {q['user_name']}\n"
            response += f"سوال: {q['question']}\n"
            response += f"زمان: {q['created_at']}\n"
            response += "-" * 40 + "\n\n"

        if len(response) > 4000:
            for i in range(0, len(response), 4000):
                await update.message.reply_text(response[i:i+4000])
        else:
            await update.message.reply_text(response)

    await admin_panel(update, context)
    return ConversationHandler.END


async def filter_by_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return ConversationHandler.END

    await update.message.reply_text(
        "نام کاربر (یا بخشی از آن) را برای فیلتر کردن سوالات وارد کنید:",
        reply_markup=ReplyKeyboardRemove()
    )
    return ADMIN_FILTER_USER


async def filter_by_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.message.text
    questions = await db.get_questions(user_name=user_name)

    if not questions:
        await update.message.reply_text(f"سوالی از کاربران با نام '{user_name}' یافت نشد.")
    else:
        response = f"سوالات کاربران با نام '{user_name}':\n\n"
        for q in questions:
            response += f"شناسه: {q['id']}\n"
            response += f"از طرف: {q['user_name']}\n"
            response += f"به: {q['presenter_name']}\n"
            response += f"سوال: {q['question']}\n"
            response += f"زمان: {q['created_at']}\n"
            response += "-" * 40 + "\n\n"

        if len(response) > 4000:
            for i in range(0, len(response), 4000):
                await update.message.reply_text(response[i:i+4000])
        else:
            await update.message.reply_text(response)

    await admin_panel(update, context)
    return ConversationHandler.END


async def add_presenter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        await update.message.reply_text("شما دسترسی مدیریت ندارید.")
        return

    await update.message.reply_text(
        "لطفاً نام ارائه‌دهنده را ارسال کنید (فرمت: نام۱، نام۲، نام۳ برای چند مورد):",
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data['awaiting_presenter'] = True


async def receive_presenter_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('awaiting_presenter'):
        return

    presenter_names = [name.strip() for name in update.message.text.split(',')]
    added = []

    for name in presenter_names:
        if await db.add_presenter(name):
            added.append(name)

    if added:
        await update.message.reply_text(f"ارائه‌دهنده(ها) اضافه شدند: {', '.join(added)}")
    else:
        await update.message.reply_text("افزودن ارائه‌دهنده ناموفق بود یا قبلاً وجود دارند.")

    context.user_data['awaiting_presenter'] = False
    await admin_panel(update, context)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await db.get_user(update.effective_user.id)

    if user:
        is_admin_val = await is_admin(update.effective_user.id)
        keyboard = [
            ["پرسیدن سوال"],
            ["پنل مدیریت"] if is_admin_val else []
        ]
        keyboard = [row for row in keyboard if row]

        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "عملیات لغو شد.",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            "عملیات لغو شد. برای شروع از /start استفاده کنید.",
            reply_markup=ReplyKeyboardRemove()
        )

    return ConversationHandler.END


async def manage_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        await update.message.reply_text("شما دسترسی مدیریت ندارید.")
        return

    users = await db.get_all_users()

    if not users:
        await update.message.reply_text("هنوز کاربری ثبت نام نکرده است.")
        await admin_panel(update, context)
        return

    response = "کاربران ثبت نام شده:\n\n"
    for user in users:
        admin_badge = " [مدیر]" if user['is_admin'] else ""
        response += f"نام: {user['name']}{admin_badge}\n"
        response += f"ایمیل: {user['email']}\n"
        response += f"شناسه: {user['telegram_id']}\n"
        response += "-" * 40 + "\n\n"

    if len(response) > 4000:
        for i in range(0, len(response), 4000):
            await update.message.reply_text(response[i:i+4000])
    else:
        await update.message.reply_text(response)

    keyboard = [
        ["ارتقاء کاربر به مدیر"],
        ["تنزل مدیر به کاربر"],
        ["بازگشت به پنل مدیریت"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "یک عملیات را انتخاب کنید:",
        reply_markup=reply_markup
    )


async def promote_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return ConversationHandler.END

    users = await db.get_all_users()
    non_admin_users = [u for u in users if not u['is_admin']]

    if not non_admin_users:
        await update.message.reply_text("کاربری برای ارتقاء وجود ندارد.")
        await admin_panel(update, context)
        return ConversationHandler.END

    response = "کاربران غیر مدیر (شناسه تلگرام را برای ارتقاء ارسال کنید):\n\n"
    for user in non_admin_users:
        response += f"{user['name']} - شناسه: {user['telegram_id']}\n"

    await update.message.reply_text(response, reply_markup=ReplyKeyboardRemove())
    return ADMIN_SELECT_USER


async def promote_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        telegram_id = int(update.message.text)
        if await db.set_admin(telegram_id, True):
            user = await db.get_user(telegram_id)
            await update.message.reply_text(f"{user['name']} با موفقیت به مدیر ارتقاء یافت!")
        else:
            await update.message.reply_text("ارتقاء کاربر ناموفق بود. کاربر یافت نشد.")
    except ValueError:
        await update.message.reply_text("شناسه نامعتبر است. لطفاً یک شناسه عددی تلگرام ارسال کنید.")
        return ADMIN_SELECT_USER

    await admin_panel(update, context)
    return ConversationHandler.END


async def demote_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return ConversationHandler.END

    users = await db.get_all_users()
    admin_users = [u for u in users if u['is_admin']]

    if not admin_users:
        await update.message.reply_text("کاربر مدیری برای تنزل وجود ندارد.")
        await admin_panel(update, context)
        return ConversationHandler.END

    response = "کاربران مدیر (شناسه تلگرام را برای تنزل ارسال کنید):\n\n"
    for user in admin_users:
        response += f"{user['name']} - شناسه: {user['telegram_id']}\n"

    await update.message.reply_text(response, reply_markup=ReplyKeyboardRemove())
    return ADMIN_SELECT_USER


async def demote_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        telegram_id = int(update.message.text)
        if await db.set_admin(telegram_id, False):
            user = await db.get_user(telegram_id)
            await update.message.reply_text(f"{user['name']} با موفقیت از مدیریت تنزل یافت.")
        else:
            await update.message.reply_text("تنزل کاربر ناموفق بود. کاربر یافت نشد.")
    except ValueError:
        await update.message.reply_text("شناسه نامعتبر است. لطفاً یک شناسه عددی تلگرام ارسال کنید.")
        return ADMIN_SELECT_USER

    await admin_panel(update, context)
    return ConversationHandler.END


async def is_admin(telegram_id: int) -> bool:
    return await db.is_admin(telegram_id)


def setup_handlers(application: Application):
    # Registration conversation
    registration_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            REGISTRATION_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, registration_name)],
            REGISTRATION_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, registration_email)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Ask question conversation
    question_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^پرسیدن سوال$"), ask_question_start)],
        states={
            SELECT_PRESENTER: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_presenter)],
            ASK_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_question)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Admin filter by presenter conversation
    filter_presenter_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^فیلتر بر اساس ارائه‌دهنده$"), filter_by_presenter_start)],
        states={
            ADMIN_FILTER_PRESENTER: [MessageHandler(filters.TEXT & ~filters.COMMAND, filter_by_presenter)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Admin filter by user conversation
    filter_user_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^فیلتر بر اساس کاربر$"), filter_by_user_start)],
        states={
            ADMIN_FILTER_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, filter_by_user)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Admin promote user conversation
    promote_user_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^ارتقاء کاربر به مدیر$"), promote_user_start)],
        states={
            ADMIN_SELECT_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, promote_user)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Admin demote user conversation
    demote_user_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^تنزل مدیر به کاربر$"), demote_user_start)],
        states={
            ADMIN_SELECT_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, demote_user)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(registration_conv)
    application.add_handler(question_conv)
    application.add_handler(filter_presenter_conv)
    application.add_handler(filter_user_conv)
    application.add_handler(promote_user_conv)
    application.add_handler(demote_user_conv)

    application.add_handler(MessageHandler(filters.Regex("^پنل مدیریت$"), admin_panel))
    application.add_handler(MessageHandler(filters.Regex("^مشاهده همه سوالات$"), view_all_questions))
    application.add_handler(MessageHandler(filters.Regex("^افزودن ارائه‌دهنده$"), add_presenter))
    application.add_handler(MessageHandler(filters.Regex("^مدیریت کاربران$"), manage_users))
    application.add_handler(MessageHandler(filters.Regex("^بازگشت به پنل مدیریت$"), admin_panel))
    application.add_handler(MessageHandler(filters.Regex("^بازگشت به منوی اصلی$"), start))

    # Handler for receiving presenter names
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_presenter_name))
