"""
Telegram Business Bot — сохраняет сообщения и уведомляет об удалении.

Установка:
    pip install python-telegram-bot==21.*

Запуск:
    python business_bot.py
"""

import logging
from telegram import Update, Message
from telegram.ext import (
    Application,
    MessageHandler,
    BusinessMessagesDeletedHandler,
    BusinessConnectionHandler,
    filters,
    ContextTypes,
)

# ─── НАСТРОЙКИ ────────────────────────────────────────────────────────────────
BOT_TOKEN = "8646265502:AAF2ETSD5ppIWhisg97Z6Iiua62yTNcfTak"
OWNER_IDS = [6767821766, 6752235800]  # Список получателей уведомлений
# ──────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Хранилище сообщений: { chat_id: { message_id: данные } }
message_store: dict[int, dict[int, dict]] = {}


def store_message(msg: Message) -> None:
    """Сохраняет сообщение в памяти."""
    chat_id = msg.chat.id
    if chat_id not in message_store:
        message_store[chat_id] = {}

    data: dict = {
        "message_id": msg.message_id,
        "from_user":  msg.from_user.full_name if msg.from_user else "Неизвестно",
        "username":   f"@{msg.from_user.username}" if (msg.from_user and msg.from_user.username) else "",
        "date":       msg.date.strftime("%d.%m.%Y %H:%M:%S") if msg.date else "—",
        "text":       msg.text or msg.caption or "",
        "photos":     [],
        "has_media":  False,
        "sticker":    None,
        "voice":      None,
        "video_note": None,
    }

    if msg.photo:
        data["photos"] = [p.file_id for p in msg.photo]
        data["has_media"] = True
    if msg.sticker:
        data["sticker"] = msg.sticker.file_id
        data["has_media"] = True
    if msg.voice:
        data["voice"] = msg.voice.file_id
        data["has_media"] = True
    if msg.video_note:
        data["video_note"] = msg.video_note.file_id
        data["has_media"] = True
    if msg.document:
        data["document"] = msg.document.file_id
        data["has_media"] = True
    if msg.video:
        data["video"] = msg.video.file_id
        data["has_media"] = True

    message_store[chat_id][msg.message_id] = data
    logger.info(f"Сохранено сообщение {msg.message_id} из чата {chat_id}")


async def notify_all(context, **kwargs):
    """Отправляет уведомление всем владельцам."""
    for owner_id in OWNER_IDS:
        try:
            await context.bot.send_message(chat_id=owner_id, **kwargs)
        except Exception as e:
            logger.error(f"Ошибка отправки владельцу {owner_id}: {e}")


async def handle_business_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.business_message
    if msg:
        store_message(msg)


async def handle_deleted_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    deleted = update.deleted_business_messages
    if not deleted:
        return

    chat_id = deleted.chat.id
    chat_title = deleted.chat.title or deleted.chat.full_name or str(chat_id)

    for msg_id in deleted.message_ids:
        saved = message_store.get(chat_id, {}).get(msg_id)

        if not saved:
            await notify_all(
                context,
                text=(
                    f"🗑 <b>Удалено сообщение</b>\n"
                    f"💬 Чат: <b>{chat_title}</b>\n"
                    f"🆔 ID: <code>{msg_id}</code>\n"
                    f"⚠️ Содержимое недоступно (сообщение пришло до запуска бота)"
                ),
                parse_mode="HTML",
            )
            continue

        sender = saved["from_user"]
        username = f" ({saved['username']})" if saved["username"] else ""
        date = saved["date"]
        text = saved["text"]

        header = (
            f"🗑 <b>Удалено сообщение!</b>\n"
            f"💬 Чат: <b>{chat_title}</b>\n"
            f"👤 От: <b>{sender}</b>{username}\n"
            f"🕐 Дата: {date}\n"
        )

        if text:
            await notify_all(context, text=header + f"\n📝 Текст:\n{text}", parse_mode="HTML")

        if saved["photos"]:
            await notify_all(context, text=header + "\n🖼 Фото:", parse_mode="HTML")
            for owner_id in OWNER_IDS:
                try:
                    await context.bot.send_photo(
                        chat_id=owner_id,
                        photo=saved["photos"][-1],
                        caption=f"Текст к фото: {text}" if text else None,
                    )
                except Exception as e:
                    logger.error(f"Ошибка отправки фото владельцу {owner_id}: {e}")

        if saved.get("sticker"):
            await notify_all(context, text=header + "\n🎭 Стикер:", parse_mode="HTML")
            for owner_id in OWNER_IDS:
                try:
                    await context.bot.send_sticker(chat_id=owner_id, sticker=saved["sticker"])
                except Exception as e:
                    logger.error(f"Ошибка: {e}")

        if saved.get("voice"):
            await notify_all(context, text=header + "\n🎤 Голосовое:", parse_mode="HTML")
            for owner_id in OWNER_IDS:
                try:
                    await context.bot.send_voice(chat_id=owner_id, voice=saved["voice"])
                except Exception as e:
                    logger.error(f"Ошибка: {e}")

        if saved.get("video_note"):
            await notify_all(context, text=header + "\n⭕ Видеосообщение:", parse_mode="HTML")
            for owner_id in OWNER_IDS:
                try:
                    await context.bot.send_video_note(chat_id=owner_id, video_note=saved["video_note"])
                except Exception as e:
                    logger.error(f"Ошибка: {e}")

        if saved.get("document"):
            await notify_all(context, text=header + "\n📎 Документ:", parse_mode="HTML")
            for owner_id in OWNER_IDS:
                try:
                    await context.bot.send_document(chat_id=owner_id, document=saved["document"])
                except Exception as e:
                    logger.error(f"Ошибка: {e}")

        if not text and not saved["has_media"]:
            await notify_all(context, text=header + "\n❓ Тип сообщения не поддерживается", parse_mode="HTML")

        logger.info(f"Уведомление отправлено: chat={chat_id}, msg_id={msg_id}")


async def handle_business_connection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = update.business_connection
    if not conn:
        return

    if conn.is_enabled:
        await notify_all(
            context,
            text=(
                f"✅ <b>Бизнес-бот подключён!</b>\n"
                f"👤 Аккаунт: <b>{conn.user.full_name}</b>\n"
                f"🆔 ID: <code>{conn.user.id}</code>"
            ),
            parse_mode="HTML",
        )
    else:
        await notify_all(context, text="❌ <b>Бизнес-бот отключён от аккаунта.</b>", parse_mode="HTML")


def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(BusinessConnectionHandler(handle_business_connection))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_business_message))
    app.add_handler(BusinessMessagesDeletedHandler(handle_deleted_messages))
    logger.info("Бот запущен...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
