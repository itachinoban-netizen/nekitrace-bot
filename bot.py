"""Telegram бот NoTrace — продажа доступа. Без ConversationHandler."""

import json, os, hashlib, logging
from pathlib import Path
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters, PreCheckoutQueryHandler
)

logging.basicConfig(level=logging.WARNING)

TOKEN        = "8818675950:AAGKHjMBcqV8V5OckfSeFF9LKU6AaBVPy1A"
ADMIN_ID     = 7675444496
LOG_CHAT     = -5391318799
CLIENT_CHAT  = -1002519881821
PRICE_FULL   = 199
PRICE_VIP    = 99
STARS_FULL   = 100
STARS_VIP    = 50

# Состояния ожидания чека
WAITING_RECEIPT = {}   # {user_id: {"price": X, "name": Y}}

if getattr(__import__("sys"), "frozen", False):
    import sys as _s; _BASE = Path(os.path.dirname(_s.executable))
else:
    _BASE = Path(__file__).parent

USERS_FILE     = Path(os.environ.get("USERS_FILE_PATH",
    str(Path(os.environ.get("APPDATA", os.path.expanduser("~"))) / "DiscordApp" / "users.json")))
FILE_ID_PATH   = _BASE / "client_file_id.txt"
BANNER_ID_PATH = _BASE / "banner_file_id.txt"
BANNER_PATH    = _BASE / "banner.png"

# ── helpers ────────────────────────────────────────────────────────────────

def _load() -> dict:
    if not USERS_FILE.exists(): return {}
    try: return json.loads(USERS_FILE.read_text(encoding="utf-8"))
    except Exception: return {}

def _save(d: dict):
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    USERS_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def is_admin(u: Update) -> bool:
    return u.effective_user.id == ADMIN_ID

def main_kb():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("🛒 Купить доступ"), KeyboardButton("ℹ️ Информация")]],
        resize_keyboard=True
    )

async def is_client(bot, uid: int) -> bool:
    try:
        m = await bot.get_chat_member(chat_id=CLIENT_CHAT, user_id=uid)
        return m.status in ("member","administrator","creator","restricted")
    except Exception: return False

def get_file_id() -> str | None:
    if FILE_ID_PATH.exists():
        v = FILE_ID_PATH.read_text(encoding="utf-8").strip()
        return v or None
    return None

def get_banner_id() -> str | None:
    if BANNER_ID_PATH.exists():
        v = BANNER_ID_PATH.read_text(encoding="utf-8").strip()
        return v or None
    return None

async def send_file_to(bot, uid: int, name: str) -> bool:
    file_id = get_file_id()
    if not file_id:
        await bot.send_message(LOG_CHAT, f"⚠️ Файл не загружен! /file чтобы загрузить.")
        return False
    try:
        await bot.send_document(
            chat_id=uid, document=file_id,
            caption="✅ Оплата получена!\n\n📦 Вот ваш файл программы.\nПо вопросам — @itachi_panelll"
        )
        return True
    except Exception as e:
        await bot.send_message(LOG_CHAT, f"⚠️ Ошибка отправки {name}: {e}")
        return False

# ── /start ─────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = f"@{user.username}" if user.username else user.first_name
    text = (
        f"👋 Приветствуем *{name}* в нашем боте!\n\n"
        f"🔐 Здесь вы можете приобрести доступ к нашей программе.\n"
        f"После оплаты вы получите файл программы.\n\n"
        f"Выберите действие ниже 👇"
    )
    banner_id = get_banner_id()
    if banner_id:
        try:
            await update.message.reply_photo(photo=banner_id, caption=text,
                parse_mode="Markdown", reply_markup=main_kb())
            return
        except Exception:
            BANNER_ID_PATH.write_text("", encoding="utf-8")
    if BANNER_PATH.exists():
        try:
            with open(str(BANNER_PATH), "rb") as f:
                msg = await update.message.reply_photo(photo=f, caption=text,
                    parse_mode="Markdown", reply_markup=main_kb())
                BANNER_ID_PATH.write_text(msg.photo[-1].file_id, encoding="utf-8")
            return
        except Exception: pass
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_kb())

# ── /info ──────────────────────────────────────────────────────────────────

async def cmd_info(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ О программе NoTrace\n\n"
        "🔐 Инструмент для безопасного удаления файлов.\n\n"
        "✅ Безвозвратное удаление данных\n"
        "✅ 3 прохода перезаписи\n"
        "✅ Доступ привязывается к вашему ПК\n\n"
        "По вопросам — @itachi_panelll",
        reply_markup=main_kb()
    )

# ── Покупка ────────────────────────────────────────────────────────────────

async def cmd_buy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user  = update.effective_user
    uid   = user.id
    vip   = await is_client(ctx.bot, uid)
    price = PRICE_VIP if vip else PRICE_FULL
    stars = STARS_VIP  if vip else STARS_FULL

    msg = (
        f"🎉 *Специальное предложение!*\n\nТак как вы наш клиент, товар будет стоить *{price} рублей* 🔥"
        if vip else
        f"🛒 *Покупка доступа*\n\nТак как вы не наш клиент и ранее не приобретали у нас товары, "
        f"для вас стоимость составит *{price} рублей*."
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"💳 Купить ({price}₽)",           callback_data=f"buy:{uid}:{price}")],
        [InlineKeyboardButton(f"⭐ Оплатить звёздами ({stars} XTR)", callback_data=f"stars:{uid}:{stars}")],
    ])
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)

# ── Реквизиты ──────────────────────────────────────────────────────────────

async def on_buy_click(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    price = parts[2] if len(parts) > 2 else "?"
    uid   = query.from_user.id
    name  = f"@{query.from_user.username}" if query.from_user.username else query.from_user.first_name

    WAITING_RECEIPT[uid] = {"price": price, "name": name}

    await query.edit_message_text(
        f"💳 *Реквизиты для оплаты {price} руб.:*\n\n"
        f"🇷🇺 *Озон Банк*\n`2204320674827466`\n\n"
        f"🇺🇦 *Monobank*\n`4441114407987245`\n\n"
        f"После оплаты нажмите кнопку ниже 👇",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("📤 Отправить чек", callback_data=f"send_receipt:{uid}:{price}")
        ]])
    )

async def on_send_receipt_click(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    price = parts[2] if len(parts) > 2 else "?"
    uid   = query.from_user.id
    name  = f"@{query.from_user.username}" if query.from_user.username else query.from_user.first_name

    WAITING_RECEIPT[uid] = {"price": price, "name": name}

    await query.edit_message_text(
        f"📸 Пришлите скриншот чека оплаты *{price} руб.* прямо в этот чат.\n\n"
        f"После проверки администратором вы получите файл программы.",
        parse_mode="Markdown"
    )

# ── Stars ──────────────────────────────────────────────────────────────────

async def on_stars_click(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    uid   = int(parts[1])
    stars = int(parts[2]) if len(parts) > 2 else STARS_FULL

    await ctx.bot.send_invoice(
        chat_id=uid,
        title="NoTrace — доступ к программе",
        description="Безвозвратное удаление файлов. Доступ привязан к вашему ПК.",
        payload=f"notrace:{uid}",
        currency="XTR",
        prices=[{"label": "Доступ к NoTrace", "amount": stars}],
        provider_token="",
    )

async def on_pre_checkout(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def on_successful_payment(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid   = update.effective_user.id
    name  = f"@{update.effective_user.username}" if update.effective_user.username else update.effective_user.first_name
    stars = update.message.successful_payment.total_amount

    await ctx.bot.send_message(LOG_CHAT,
        f"⭐ *Оплата звёздами*\n\n👤 {name}\n🆔 `{uid}`\n💫 {stars} XTR\n\n✅ Файл отправляется.",
        parse_mode="Markdown")

    sent = await send_file_to(ctx.bot, uid, name)
    if not sent:
        await ctx.bot.send_message(uid, "✅ Оплата получена! Файл будет выслан.\n@itachi_panelll")

# ── Получение чека ─────────────────────────────────────────────────────────

async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Все входящие сообщения — чек или кнопки клавиатуры."""
    user = update.effective_user
    uid  = user.id
    t    = (update.message.text or "").lower()

    # Кнопки клавиатуры — проверяем ПЕРВЫМИ
    if "информац" in t:
        await cmd_info(update, ctx)
        return
    if "купить" in t:
        await cmd_buy(update, ctx)
        return

    # Чек — если пользователь в состоянии ожидания
    if uid in WAITING_RECEIPT:
        info  = WAITING_RECEIPT.pop(uid)
        price = info.get("price", "?")
        name  = info.get("name", f"@{user.username}" if user.username else user.first_name)

        log_text = (
            f"💳 *Новый чек оплаты*\n\n"
            f"👤 {name}\n🆔 `{uid}`\n💰 {price} руб.\n\n"
            f"Подтвердить и отправить файл клиенту?"
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Подтвердить — выдать файл", callback_data=f"confirm:{uid}:{name}"),
            InlineKeyboardButton("❌ Отклонить",                  callback_data=f"reject:{uid}:{name}"),
        ]])

        try:
            if update.message.photo:
                await ctx.bot.send_photo(LOG_CHAT, update.message.photo[-1].file_id,
                    caption=log_text, parse_mode="Markdown", reply_markup=kb)
            elif update.message.document:
                await ctx.bot.send_document(LOG_CHAT, update.message.document.file_id,
                    caption=log_text, parse_mode="Markdown", reply_markup=kb)
            else:
                await ctx.bot.send_message(LOG_CHAT,
                    log_text + f"\n\n📝 Текст: {update.message.text}",
                    parse_mode="Markdown", reply_markup=kb)
        except Exception as e:
            await ctx.bot.send_message(LOG_CHAT,
                log_text + f"\n\n⚠️ Ошибка пересылки: {e}",
                parse_mode="Markdown", reply_markup=kb)

        await update.message.reply_text(
            "✅ Чек получен! Ожидайте подтверждения.\n"
            "После проверки вы получите файл программы.\n\nПо вопросам — @itachi_panelll",
            reply_markup=main_kb()
        )

# ── Подтверждение / отклонение ────────────────────────────────────────────

async def on_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer("⛔ Только администратор."); return
    await query.answer("✅ Подтверждено!")

    parts = query.data.split(":")
    uid   = int(parts[1])
    uname = parts[2] if len(parts) > 2 else "клиент"

    sent  = await send_file_to(ctx.bot, uid, uname)
    if not sent:
        await ctx.bot.send_message(uid,
            "✅ Оплата подтверждена! Файл будет выслан.\n@itachi_panelll")

    result = f"✅ Оплата *{uname}* подтверждена.\n" + ("📦 Файл отправлен." if sent else "⚠️ Загрузите файл через /file")
    try: await query.edit_message_caption(caption=result, parse_mode="Markdown", reply_markup=None)
    except Exception:
        try: await query.edit_message_text(result, parse_mode="Markdown", reply_markup=None)
        except Exception: pass

async def on_reject(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer("⛔ Только администратор."); return
    await query.answer("❌ Отклонено.")

    parts = query.data.split(":")
    uid   = int(parts[1])
    uname = parts[2] if len(parts) > 2 else "клиент"

    await ctx.bot.send_message(uid,
        "❌ Ваш чек не подтверждён.\nСвяжитесь с администратором — @itachi_panelll")
    result = f"❌ Заявка *{uname}* отклонена."
    try: await query.edit_message_caption(caption=result, parse_mode="Markdown", reply_markup=None)
    except Exception:
        try: await query.edit_message_text(result, parse_mode="Markdown", reply_markup=None)
        except Exception: pass

# ── /file ──────────────────────────────────────────────────────────────────

async def cmd_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔"); return
    if update.message.document:
        fid  = update.message.document.file_id
        name = update.message.document.file_name or "файл"
        FILE_ID_PATH.write_text(fid, encoding="utf-8")
        await update.message.reply_text(
            f"✅ Файл *{name}* сохранён!\nБудет выдаваться клиентам автоматически.",
            parse_mode="Markdown")
    else:
        await update.message.reply_text(
            f"📎 Отправь документ с `/file` в подписи.\n\n"
            f"Текущий файл: {'✅ загружен' if get_file_id() else '❌ не загружен'}",
            parse_mode="Markdown")

async def on_admin_doc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    cap = (update.message.caption or "").lower()
    if "/file" in cap:
        await cmd_file(update, ctx)

# ── /banner ────────────────────────────────────────────────────────────────

async def cmd_banner(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔"); return
    if update.message.photo:
        fid = update.message.photo[-1].file_id
        BANNER_ID_PATH.write_text(fid, encoding="utf-8")
        await update.message.reply_text("✅ Баннер обновлён!")
    else:
        await update.message.reply_text(
            "📸 Отправь фото с `/banner` в подписи.", parse_mode="Markdown")

async def on_admin_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    cap = (update.message.caption or "").lower()
    if "/banner" in cap:
        await cmd_banner(update, ctx)

# ── /sms ───────────────────────────────────────────────────────────────────

async def cmd_sms(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔"); return
    args = ctx.args
    if len(args) < 3:
        await update.message.reply_text(
            "Использование: `/sms @username логин пароль [HWID]`", parse_mode="Markdown"); return
    target = args[0].lstrip("@"); login = args[1]; pw = args[2]
    hwid   = args[3].upper() if len(args) > 3 else None
    users  = _load(); entry = {"hash": _hash(pw)}
    if hwid: entry["hwid"] = hwid
    users[login] = entry; _save(users)
    msg = f"🔑 *Данные для входа:*\n\n👤 Логин: `{login}`\n🔒 Пароль: `{pw}`\n"
    if hwid: msg += f"💻 HWID: `{hwid}`\n"
    msg += "\n⚠️ Не передавайте данные третьим лицам!"
    try:
        await ctx.bot.send_message(f"@{target}", msg, parse_mode="Markdown")
        await update.message.reply_text(f"✅ Данные отправлены @{target}")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: `{e}`", parse_mode="Markdown")

# ── Прочие команды ─────────────────────────────────────────────────────────

async def cmd_adduser(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): await update.message.reply_text("⛔"); return
    if len(ctx.args) < 2:
        await update.message.reply_text("`/adduser логин пароль [HWID]`", parse_mode="Markdown"); return
    login=ctx.args[0]; pw=ctx.args[1]; hwid=ctx.args[2].upper() if len(ctx.args)>2 else None
    users=_load(); entry={"hash":_hash(pw)}
    if hwid: entry["hwid"]=hwid
    users[login]=entry; _save(users)
    await update.message.reply_text(
        f"✅ *{login}* добавлен." + (f"\n🔒 HWID: `{hwid}`" if hwid else ""), parse_mode="Markdown")

async def cmd_deluser(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): await update.message.reply_text("⛔"); return
    if not ctx.args:
        await update.message.reply_text("`/deluser логин`", parse_mode="Markdown"); return
    login=ctx.args[0]; users=_load()
    if login not in users:
        await update.message.reply_text(f"❌ `{login}` не найден.", parse_mode="Markdown"); return
    del users[login]; _save(users)
    await update.message.reply_text(f"🗑 *{login}* удалён.", parse_mode="Markdown")

async def cmd_listusers(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): await update.message.reply_text("⛔"); return
    users=_load()
    if not users: await update.message.reply_text("📋 Пользователей нет."); return
    lines=["📋 *Пользователи:*\n"]
    for i,(l,e) in enumerate(users.items(),1):
        hwid=e.get("hwid","—") if isinstance(e,dict) else "—"
        lines.append(f"{i}. `{l}` | HWID: `{hwid}`")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def cmd_getid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"ID: `{update.effective_user.id}`", parse_mode="Markdown")

# ── Main ───────────────────────────────────────────────────────────────────

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Stars — первыми
    app.add_handler(PreCheckoutQueryHandler(on_pre_checkout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, on_successful_payment))

    # Команды
    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("info",      cmd_info))
    app.add_handler(CommandHandler("file",      cmd_file))
    app.add_handler(CommandHandler("banner",    cmd_banner))
    app.add_handler(CommandHandler("sms",       cmd_sms))
    app.add_handler(CommandHandler("adduser",   cmd_adduser))
    app.add_handler(CommandHandler("deluser",   cmd_deluser))
    app.add_handler(CommandHandler("listusers", cmd_listusers))
    app.add_handler(CommandHandler("getid",     cmd_getid))

    # Callback кнопки
    app.add_handler(CallbackQueryHandler(on_buy_click,         pattern=r"^buy:"))
    app.add_handler(CallbackQueryHandler(on_stars_click,       pattern=r"^stars:"))
    app.add_handler(CallbackQueryHandler(on_send_receipt_click, pattern=r"^send_receipt:"))
    app.add_handler(CallbackQueryHandler(on_confirm,           pattern=r"^confirm:"))
    app.add_handler(CallbackQueryHandler(on_reject,            pattern=r"^reject:"))

    # Документы/фото от админа с /file или /banner в подписи
    app.add_handler(MessageHandler(
        filters.Document.ALL & filters.User(ADMIN_ID) & filters.CaptionRegex(r"(?i)/file"),
        on_admin_doc))
    app.add_handler(MessageHandler(
        filters.PHOTO & filters.User(ADMIN_ID) & filters.CaptionRegex(r"(?i)/banner"),
        on_admin_photo))

    # Все остальные сообщения (текст + фото без подписи + документы без подписи)
    # Один обработчик — on_message разбирает сам
    app.add_handler(MessageHandler(
        (filters.TEXT | filters.PHOTO | filters.Document.ALL) & ~filters.COMMAND,
        on_message))

    print("Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()
