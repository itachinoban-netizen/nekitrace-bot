"""Telegram бот NoTrace — продажа доступа."""

import json, os, hashlib, logging
from pathlib import Path
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters, ConversationHandler
)

logging.basicConfig(level=logging.WARNING)

TOKEN       = "8818675950:AAGKHjMBcqV8V5OckfSeFF9LKU6AaBVPy1A"
ADMIN_ID    = 7675444496
LOG_CHAT    = 7675444496
CLIENT_CHAT = -1002519881821
PRICE_FULL  = 199
PRICE_VIP   = 99
WAIT_RECEIPT = 1

if getattr(__import__("sys"), "frozen", False):
    import sys as _s; _BASE = Path(os.path.dirname(_s.executable))
else:
    _BASE = Path(__file__).parent

USERS_FILE = Path(os.environ.get(
    "USERS_FILE_PATH",
    str(Path(os.environ.get("APPDATA", os.path.expanduser("~"))) / "DiscordApp" / "users.json")
))
BANNER_PATH = _BASE / "banner.png"

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

def find_file() -> Path | None:
    for ext in [".zip",".exe",".rar",".7z",".pdf"]:
        p = _BASE / f"client_file{ext}"
        if p.exists(): return p
    return None

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
    try:
        if BANNER_PATH.exists():
            with open(str(BANNER_PATH), "rb") as f:
                await update.message.reply_photo(
                    photo=f, caption=text,
                    parse_mode="Markdown", reply_markup=main_kb())
            return
    except Exception: pass
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_kb())

# ── /info ──────────────────────────────────────────────────────────────────

async def cmd_info(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ *О программе NoTrace*\n\n"
        "🔐 Профессиональный инструмент для безопасного удаления файлов.\n\n"
        "✅ Безвозвратное удаление данных\n"
        "✅ 3 прохода перезаписи\n"
        "✅ Доступ привязывается к вашему ПК\n\n"
        "По вопросам — @itachi_panelll",
        parse_mode="Markdown", reply_markup=main_kb()
    )

# ── Покупка: шаг 1 — показать цену ────────────────────────────────────────

async def cmd_buy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user  = update.effective_user
    uid   = user.id
    vip   = await is_client(ctx.bot, uid)
    price = PRICE_VIP if vip else PRICE_FULL
    ctx.user_data["price"] = price
    ctx.user_data["uid"]   = uid
    ctx.user_data["name"]  = f"@{user.username}" if user.username else user.first_name

    if vip:
        msg = (f"🎉 *Специальное предложение!*\n\n"
               f"Так как вы наш клиент, товар будет стоить *{price} рублей* 🔥")
    else:
        msg = (f"🛒 *Покупка доступа*\n\n"
               f"Так как вы не наш клиент и ранее не приобретали у нас товары, "
               f"для вас стоимость составит *{price} рублей*.")

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(f"💳 Купить ({price}₽)", callback_data=f"buy:{uid}:{price}")
    ]])
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)

# ── Покупка: шаг 2 — показать реквизиты ───────────────────────────────────

async def on_buy_click(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    price = parts[2] if len(parts) > 2 else "?"
    ctx.user_data["price"] = price
    ctx.user_data["uid"]   = query.from_user.id
    ctx.user_data["name"]  = f"@{query.from_user.username}" if query.from_user.username else query.from_user.first_name

    await query.edit_message_text(
        f"💳 *Реквизиты для оплаты {price} руб.:*\n\n"
        f"🇷🇺 *Озон Банк*\n"
        f"`2204320674827466`\n\n"
        f"🇺🇦 *Monobank*\n"
        f"`4441114407987245`\n\n"
        f"После оплаты нажмите кнопку ниже 👇",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("📤 Отправить чек", callback_data=f"send_receipt:{query.from_user.id}:{price}")
        ]])
    )
    return ConversationHandler.END

# ── Покупка: шаг 3 — просим прислать чек ──────────────────────────────────

async def on_send_receipt_click(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    price = parts[2] if len(parts) > 2 else "?"
    ctx.user_data["price"] = price
    ctx.user_data["uid"]   = query.from_user.id
    ctx.user_data["name"]  = f"@{query.from_user.username}" if query.from_user.username else query.from_user.first_name

    await query.edit_message_text(
        f"📸 Пришлите скриншот чека оплаты *{price} руб.* в этот чат.\n\n"
        f"После проверки вы получите файл программы автоматически.",
        parse_mode="Markdown"
    )
    return WAIT_RECEIPT

# ── Покупка: шаг 4 — получили чек, пересылаем в лог ──────────────────────

async def on_receipt(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    user  = update.effective_user
    name  = ctx.user_data.get("name", f"@{user.username}" if user.username else user.first_name)
    uid   = user.id
    price = ctx.user_data.get("price", "?")

    log_text = (
        f"💳 *Новый чек оплаты*\n\n"
        f"👤 {name}\n"
        f"🆔 `{uid}`\n"
        f"💰 {price} руб.\n\n"
        f"Подтвердить и отправить файл клиенту?"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Подтвердить — выдать файл", callback_data=f"confirm:{uid}:{name}"),
        InlineKeyboardButton("❌ Отклонить",                  callback_data=f"reject:{uid}:{name}"),
    ]])

    try:
        if update.message.photo:
            await ctx.bot.send_photo(
                chat_id=LOG_CHAT, photo=update.message.photo[-1].file_id,
                caption=log_text, parse_mode="Markdown", reply_markup=kb)
        elif update.message.document:
            await ctx.bot.send_document(
                chat_id=LOG_CHAT, document=update.message.document.file_id,
                caption=log_text, parse_mode="Markdown", reply_markup=kb)
        else:
            await ctx.bot.send_message(
                chat_id=LOG_CHAT,
                text=log_text + f"\n\n📝 Текст: {update.message.text}",
                parse_mode="Markdown", reply_markup=kb)
    except Exception as e:
        await ctx.bot.send_message(
            chat_id=LOG_CHAT,
            text=log_text + f"\n\n⚠️ Ошибка пересылки: {e}",
            parse_mode="Markdown", reply_markup=kb)

    await update.message.reply_text(
        "✅ Чек получен! Ожидайте подтверждения.\n"
        "После проверки вы получите файл программы.\n\n"
        "По вопросам — @itachi_panelll",
        reply_markup=main_kb()
    )
    return ConversationHandler.END

# ── Подтверждение / отклонение (admin) ────────────────────────────────────

async def on_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer("⛔ Только администратор."); return
    await query.answer("✅ Подтверждено!")

    parts  = query.data.split(":")
    uid    = int(parts[1])
    uname  = parts[2] if len(parts) > 2 else "клиент"
    f_path = find_file()
    sent   = False

    if f_path:
        try:
            with open(str(f_path), "rb") as fh:
                await ctx.bot.send_document(
                    chat_id=uid, document=fh,
                    caption=(
                        "✅ *Ваша оплата подтверждена!*\n\n"
                        "📦 Вот ваш файл программы.\n"
                        "По вопросам — @itachi_panelll"
                    ),
                    parse_mode="Markdown"
                )
            sent = True
        except Exception as e:
            await ctx.bot.send_message(LOG_CHAT, f"⚠️ Не удалось отправить файл {uname}: {e}")

    if not sent:
        await ctx.bot.send_message(
            uid,
            "✅ *Оплата подтверждена!*\nФайл будет выслан вам в ближайшее время.\n@itachi_panelll",
            parse_mode="Markdown"
        )

    result_text = (
        f"✅ Оплата *{uname}* подтверждена.\n"
        f"{'📦 Файл отправлен.' if sent else '⚠️ Загрузите файл через /file'}"
    )
    try:
        await query.edit_message_caption(caption=result_text, parse_mode="Markdown", reply_markup=None)
    except Exception:
        try:
            await query.edit_message_text(text=result_text, parse_mode="Markdown", reply_markup=None)
        except Exception: pass

async def on_reject(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer("⛔ Только администратор."); return
    await query.answer("❌ Отклонено.")

    parts = query.data.split(":")
    uid   = int(parts[1])
    uname = parts[2] if len(parts) > 2 else "клиент"

    await ctx.bot.send_message(
        uid,
        "❌ Ваш чек не был подтверждён.\nСвяжитесь с администратором — @itachi_panelll"
    )
    result_text = f"❌ Заявка *{uname}* отклонена."
    try:
        await query.edit_message_caption(caption=result_text, parse_mode="Markdown", reply_markup=None)
    except Exception:
        try:
            await query.edit_message_text(text=result_text, parse_mode="Markdown", reply_markup=None)
        except Exception: pass

# ── /file (admin) ──────────────────────────────────────────────────────────

async def cmd_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ Нет доступа."); return
    if update.message.document:
        doc  = update.message.document
        ext  = Path(doc.file_name).suffix if doc.file_name else ".zip"
        dest = _BASE / f"client_file{ext}"
        f    = await ctx.bot.get_file(doc.file_id)
        await f.download_to_drive(str(dest))
        await update.message.reply_text(
            f"✅ Файл *{doc.file_name}* сохранён.\nБудет выдаваться клиентам автоматически.",
            parse_mode="Markdown")
    else:
        await update.message.reply_text(
            "📎 Отправь документ с `/file` в подписи.", parse_mode="Markdown")

# ── /banner (admin) ────────────────────────────────────────────────────────

async def cmd_banner(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔"); return
    if update.message.photo:
        f = await ctx.bot.get_file(update.message.photo[-1].file_id)
        await f.download_to_drive(str(BANNER_PATH))
        await update.message.reply_text("✅ Баннер обновлён!")
    else:
        await update.message.reply_text("📸 Отправь фото с `/banner` в подписи.", parse_mode="Markdown")

# ── /sms (admin) ───────────────────────────────────────────────────────────

async def cmd_sms(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔"); return
    args = ctx.args
    if len(args) < 3:
        await update.message.reply_text(
            "Использование: `/sms @username логин пароль [HWID]`", parse_mode="Markdown"); return

    target = args[0].lstrip("@")
    login  = args[1]; pw = args[2]
    hwid   = args[3].upper() if len(args) > 3 else None

    users = _load()
    entry = {"hash": _hash(pw)}
    if hwid: entry["hwid"] = hwid
    users[login] = entry; _save(users)

    msg = (f"🔑 *Данные для входа:*\n\n👤 Логин: `{login}`\n🔒 Пароль: `{pw}`\n")
    if hwid: msg += f"💻 HWID: `{hwid}`\n"
    msg += "\n⚠️ Не передавайте данные третьим лицам!"

    try:
        await ctx.bot.send_message(f"@{target}", msg, parse_mode="Markdown")
        await update.message.reply_text(f"✅ Данные отправлены @{target}")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: `{e}`\nДанные сохранены.", parse_mode="Markdown")

# ── /adduser /deluser /listusers /getid ────────────────────────────────────

async def cmd_adduser(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): await update.message.reply_text("⛔"); return
    if len(ctx.args) < 2:
        await update.message.reply_text("`/adduser логин пароль [HWID]`", parse_mode="Markdown"); return
    login=ctx.args[0]; pw=ctx.args[1]; hwid=ctx.args[2].upper() if len(ctx.args)>2 else None
    users=_load(); entry={"hash":_hash(pw)}
    if hwid: entry["hwid"]=hwid
    users[login]=entry; _save(users)
    await update.message.reply_text(
        f"✅ *{login}* добавлен." + (f"\n🔒 HWID: `{hwid}`" if hwid else ""),
        parse_mode="Markdown")

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
        lines.append(f"{i}. `{l}` | `{hwid}`")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def cmd_getid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"ID: `{update.effective_user.id}`", parse_mode="Markdown")

# ── Клавиатура ─────────────────────────────────────────────────────────────

async def on_keyboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    t = update.message.text
    if t == "🛒 Купить доступ": await cmd_buy(update, ctx)
    elif t == "ℹ️ Информация":  await cmd_info(update, ctx)

async def on_document_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    cap = update.message.caption or ""
    if "/file" in cap:   await cmd_file(update, ctx)
    elif "/banner" in cap: await cmd_banner(update, ctx)

async def on_photo_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    cap = update.message.caption or ""
    if "/banner" in cap: await cmd_banner(update, ctx)

# ── Main ───────────────────────────────────────────────────────────────────

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(on_buy_click,         pattern=r"^buy:\d+:\d+$"),
            CallbackQueryHandler(on_send_receipt_click, pattern=r"^send_receipt:"),
        ],
        states={
            WAIT_RECEIPT: [
                MessageHandler(
                    filters.PHOTO | filters.Document.ALL | filters.TEXT & ~filters.COMMAND,
                    on_receipt
                )
            ],
        },
        fallbacks=[CommandHandler("start", cmd_start)],
        per_user=True, per_chat=True,
    )

    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("info",      cmd_info))
    app.add_handler(CommandHandler("file",      cmd_file))
    app.add_handler(CommandHandler("banner",    cmd_banner))
    app.add_handler(CommandHandler("sms",       cmd_sms))
    app.add_handler(CommandHandler("adduser",   cmd_adduser))
    app.add_handler(CommandHandler("deluser",   cmd_deluser))
    app.add_handler(CommandHandler("listusers", cmd_listusers))
    app.add_handler(CommandHandler("getid",     cmd_getid))

    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(on_confirm, pattern=r"^confirm:"))
    app.add_handler(CallbackQueryHandler(on_reject,  pattern=r"^reject:"))

    app.add_handler(MessageHandler(
        filters.Document.ALL & filters.User(ADMIN_ID), on_document_admin))
    app.add_handler(MessageHandler(
        filters.PHOTO & filters.User(ADMIN_ID), on_photo_admin))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, on_keyboard))

    print("Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()
