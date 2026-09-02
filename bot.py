"""
Telegram бот для продажи доступа к NeKit Program.

Команды:
  /start          — приветствие + кнопки (для всех)
  /buy            — купить доступ (для всех)
  /info           — информация о продукте (для всех)
  /file           — загрузить файл для выдачи клиентам (только admin)
  /adduser ...    — добавить пользователя (только admin)
  /deluser ...    — удалить пользователя (только admin)
  /listusers      — список пользователей (только admin)
  /sms @username  — отправить пароль клиенту (только admin)
  /getid          — узнать свой Telegram ID
"""

import json
import os
import hashlib
import logging
from pathlib import Path
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

logging.basicConfig(level=logging.WARNING)

TOKEN   = "8818675950:AAGKHjMBcqV8V5OckfSeFF9LKU6AaBVPy1A"
ADMIN_ID = 7675444496          # единственный администратор
LOG_CHAT = 7675444496          # чат для логов (можно поменять на ID группы)

if getattr(__import__("sys"), "frozen", False):
    import sys as _sys
    _BASE = Path(os.path.dirname(_sys.executable))
else:
    _BASE = Path(__file__).parent

USERS_FILE = Path(os.environ.get("USERS_FILE_PATH",
                  str(Path(os.environ.get("APPDATA", os.path.expanduser("~"))) / "DiscordApp" / "users.json")))
FILE_PATH  = _BASE / "client_file.zip"   # файл который выдаётся клиенту

# ── helpers ────────────────────────────────────────────────────────────────

def _load() -> dict:
    if not USERS_FILE.exists(): return {}
    try:
        return json.loads(USERS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _save(data: dict) -> None:
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    USERS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def is_admin(update: Update) -> bool:
    return update.effective_user.id == ADMIN_ID

def main_keyboard():
    """Основная клавиатура с двумя кнопками."""
    return ReplyKeyboardMarkup(
        [[KeyboardButton("🛒 Купить доступ"), KeyboardButton("ℹ️ Информация")]],
        resize_keyboard=True
    )

# ── /start ─────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    name = f"@{user.username}" if user.username else user.first_name
    await update.message.reply_text(
        f"👋 Приветствуем *{name}* в нашем боте!\n\n"
        f"🔐 Здесь вы можете приобрести доступ к нашей программе.\n"
        f"После оплаты вы получите логин и пароль для входа.\n\n"
        f"Выберите действие ниже 👇",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

# ── /buy + кнопка ──────────────────────────────────────────────────────────

async def cmd_buy(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    name = f"@{user.username}" if user.username else user.first_name
    uid  = user.id

    text = (
        "🛒 *Покупка доступа*\n\n"
        "💰 Стоимость: *уточняйте у администратора*\n\n"
        "Для оплаты свяжитесь с администратором или\n"
        "нажмите кнопку ниже для отправки заявки:"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("📩 Отправить заявку", callback_data=f"buy_request:{uid}:{name}")
    ]])
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)

async def on_buy_request(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Пользователь нажал 'Отправить заявку' — шлём чек в лог-чат админу."""
    query = update.callback_query
    await query.answer("✅ Заявка отправлена!")

    parts  = query.data.split(":")
    uid    = parts[1]
    uname  = parts[2] if len(parts) > 2 else "unknown"

    # Сообщение-чек в лог-чат
    log_text = (
        f"💳 *Новая заявка на покупку*\n\n"
        f"👤 Пользователь: {uname}\n"
        f"🆔 ID: `{uid}`\n\n"
        f"Подтвердить или отклонить?"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm:{uid}:{uname}"),
        InlineKeyboardButton("❌ Отклонить",   callback_data=f"reject:{uid}:{uname}"),
    ]])
    await ctx.bot.send_message(
        chat_id=LOG_CHAT,
        text=log_text,
        parse_mode="Markdown",
        reply_markup=kb
    )
    await query.edit_message_text(
        "✅ Ваша заявка отправлена администратору!\n"
        "Ожидайте подтверждения.",
        reply_markup=None
    )

async def on_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Админ подтвердил оплату."""
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer("⛔ Только администратор может подтверждать.")
        return
    await query.answer("✅ Оплата подтверждена!")

    parts = query.data.split(":")
    uid   = int(parts[1])
    uname = parts[2] if len(parts) > 2 else "пользователь"

    await ctx.bot.send_message(
        chat_id=uid,
        text=(
            "✅ *Ваша оплата подтверждена!*\n\n"
            "Ожидайте — администратор отправит вам данные для входа.\n"
            "Используйте /start чтобы вернуться в меню."
        ),
        parse_mode="Markdown"
    )
    await query.edit_message_text(
        f"✅ Оплата {uname} (`{uid}`) подтверждена.\n"
        f"Используйте `/sms @username` чтобы выдать доступ.",
        parse_mode="Markdown",
        reply_markup=None
    )

async def on_reject(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Админ отклонил оплату."""
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer("⛔ Только администратор.")
        return
    await query.answer("❌ Заявка отклонена.")

    parts = query.data.split(":")
    uid   = int(parts[1])
    uname = parts[2] if len(parts) > 2 else "пользователь"

    await ctx.bot.send_message(
        chat_id=uid,
        text="❌ К сожалению, ваша заявка была отклонена.\nСвяжитесь с администратором для уточнения."
    )
    await query.edit_message_text(
        f"❌ Заявка {uname} (`{uid}`) отклонена.",
        parse_mode="Markdown",
        reply_markup=None
    )

# ── /info ──────────────────────────────────────────────────────────────────

async def cmd_info(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "ℹ️ *О программе*\n\n"
        "🔐 *NeKit Program* — профессиональный инструмент для безопасного удаления файлов.\n\n"
        "✅ Безвозвратное удаление данных\n"
        "✅ 3 прохода перезаписи\n"
        "✅ Работает на Windows\n"
        "✅ Доступ привязывается к вашему ПК\n\n"
        "По вопросам — обращайтесь к администратору.",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

# ── /file (только admin) ───────────────────────────────────────────────────

async def cmd_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда для загрузки файла который будет выдаваться клиентам."""
    if not is_admin(update):
        await update.message.reply_text("⛔ Нет доступа.")
        return
    if update.message.document:
        # Скачиваем и сохраняем файл
        doc  = update.message.document
        file = await ctx.bot.get_file(doc.file_id)
        ext  = Path(doc.file_name).suffix if doc.file_name else ".zip"
        dest = _BASE / f"client_file{ext}"
        await file.download_to_drive(str(dest))
        await update.message.reply_text(
            f"✅ Файл *{doc.file_name}* сохранён.\n"
            f"Будет выдаваться клиентам командой `/sms`.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "📎 Отправь файл с командой `/file` (как документ).\n"
            "Этот файл будет выдаваться клиентам после покупки.",
            parse_mode="Markdown"
        )

# ── /sms @username (только admin) ─────────────────────────────────────────

async def cmd_sms(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Выдать доступ клиенту: /sms @username логин пароль [HWID]"""
    if not is_admin(update):
        await update.message.reply_text("⛔ Нет доступа.")
        return

    args = ctx.args
    if len(args) < 3:
        await update.message.reply_text(
            "Использование: `/sms @username логин пароль [HWID]`\n\n"
            "Пример: `/sms @john login123 pass456`\n"
            "С привязкой к ПК: `/sms @john login123 pass456 ABC123DEF456`",
            parse_mode="Markdown"
        )
        return

    target = args[0].lstrip("@")
    login  = args[1]
    pw     = args[2]
    hwid   = args[3].upper() if len(args) > 3 else None

    # Сохраняем в users.json
    users = _load()
    entry = {"hash": _hash(pw)}
    if hwid:
        entry["hwid"] = hwid
    users[login] = entry
    _save(users)

    # Ищем пользователя по username в Telegram
    # Пробуем отправить через username (работает если юзер писал боту)
    try:
        # Отправляем сообщение с данными
        msg = (
            f"🔑 *Ваши данные для входа в NeKit Program:*\n\n"
            f"👤 Логин: `{login}`\n"
            f"🔒 Пароль: `{pw}`\n"
        )
        if hwid:
            msg += f"💻 Привязан к ПК: `{hwid}`\n"
        msg += (
            f"\n📥 Скачайте программу и войдите с этими данными.\n"
            f"⚠️ Не передавайте данные третьим лицам!"
        )

        # Отправляем файл если есть
        file_sent = False
        for ext in [".zip", ".exe", ".rar", ".7z"]:
            f_path = _BASE / f"client_file{ext}"
            if f_path.exists():
                await ctx.bot.send_message(
                    chat_id=f"@{target}",
                    text=msg,
                    parse_mode="Markdown"
                )
                with open(str(f_path), "rb") as fh:
                    await ctx.bot.send_document(
                        chat_id=f"@{target}",
                        document=fh,
                        caption="📦 Программа NeKit"
                    )
                file_sent = True
                break

        if not file_sent:
            await ctx.bot.send_message(
                chat_id=f"@{target}",
                text=msg,
                parse_mode="Markdown"
            )

        await update.message.reply_text(
            f"✅ Доступ выдан пользователю @{target}\n"
            f"Логин: `{login}` | Пароль: `{pw}`" +
            (f"\nHWID: `{hwid}`" if hwid else ""),
            parse_mode="Markdown"
        )

    except Exception as e:
        await update.message.reply_text(
            f"❌ Не удалось отправить сообщение @{target}\n"
            f"Ошибка: `{e}`\n\n"
            f"Данные сохранены в базе:\n"
            f"Логин: `{login}` | Пароль: `{pw}`",
            parse_mode="Markdown"
        )

# ── /adduser (только admin) ────────────────────────────────────────────────

async def cmd_adduser(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        await update.message.reply_text("⛔ Нет доступа.")
        return
    if len(ctx.args) < 2:
        await update.message.reply_text(
            "Использование:\n"
            "`/adduser логин пароль` — без привязки\n"
            "`/adduser логин пароль HWID` — привязать к ПК",
            parse_mode="Markdown"
        )
        return

    login = ctx.args[0].strip()
    pw    = ctx.args[1].strip()
    hwid  = ctx.args[2].strip().upper() if len(ctx.args) > 2 else None

    users = _load()
    verb  = "обновлён" if login in users else "добавлен"
    entry = {"hash": _hash(pw)}
    if hwid:
        entry["hwid"] = hwid
    users[login] = entry
    _save(users)

    txt = f"✅ Пользователь *{login}* {verb}."
    if hwid:
        txt += f"\n🔒 Привязан к ПК: `{hwid}`"
    else:
        txt += "\n⚠️ Без привязки к ПК."
    await update.message.reply_text(txt, parse_mode="Markdown")

# ── /deluser (только admin) ────────────────────────────────────────────────

async def cmd_deluser(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        await update.message.reply_text("⛔ Нет доступа.")
        return
    if len(ctx.args) != 1:
        await update.message.reply_text("Использование: `/deluser логин`", parse_mode="Markdown")
        return
    login = ctx.args[0].strip()
    users = _load()
    if login not in users:
        await update.message.reply_text(f"❌ Логин `{login}` не найден.", parse_mode="Markdown")
        return
    del users[login]
    _save(users)
    await update.message.reply_text(f"🗑 Пользователь *{login}* удалён.", parse_mode="Markdown")

# ── /listusers (только admin) ──────────────────────────────────────────────

async def cmd_listusers(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        await update.message.reply_text("⛔ Нет доступа.")
        return
    users = _load()
    if not users:
        await update.message.reply_text("📋 Пользователей нет.")
        return
    lines = ["📋 *Пользователи:*\n"]
    for i, (login, entry) in enumerate(users.items(), 1):
        hwid = entry.get("hwid", "—") if isinstance(entry, dict) else "—"
        lines.append(f"{i}. `{login}` | HWID: `{hwid}`")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

# ── /getid ─────────────────────────────────────────────────────────────────

async def cmd_getid(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    await update.message.reply_text(f"Ваш ID: `{uid}`", parse_mode="Markdown")

# ── Обработка кнопок клавиатуры ────────────────────────────────────────────

async def on_keyboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    if text == "🛒 Купить доступ":
        await cmd_buy(update, ctx)
    elif text == "ℹ️ Информация":
        await cmd_info(update, ctx)

# ── /file как документ ─────────────────────────────────────────────────────

async def on_document(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Если admin присылает документ — предлагаем сохранить как client_file."""
    if not is_admin(update):
        return
    if update.message.caption and "/file" in update.message.caption:
        await cmd_file(update, ctx)

# ── Main ───────────────────────────────────────────────────────────────────

def main() -> None:
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("buy",       cmd_buy))
    app.add_handler(CommandHandler("info",      cmd_info))
    app.add_handler(CommandHandler("file",      cmd_file))
    app.add_handler(CommandHandler("sms",       cmd_sms))
    app.add_handler(CommandHandler("adduser",   cmd_adduser))
    app.add_handler(CommandHandler("deluser",   cmd_deluser))
    app.add_handler(CommandHandler("listusers", cmd_listusers))
    app.add_handler(CommandHandler("getid",     cmd_getid))

    app.add_handler(CallbackQueryHandler(on_buy_request, pattern=r"^buy_request:"))
    app.add_handler(CallbackQueryHandler(on_confirm,     pattern=r"^confirm:"))
    app.add_handler(CallbackQueryHandler(on_reject,      pattern=r"^reject:"))

    app.add_handler(MessageHandler(
        filters.Document.ALL & filters.User(ADMIN_ID),
        on_document
    ))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        on_keyboard
    ))

    print("Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()
