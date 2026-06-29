"""
Telegram Business Bot — сохраняет сообщения и уведомляет об удалении.

Установка:
    pip install python-telegram-bot==21.* aiofiles

Запуск:
    python business_bot.py

Настройка:
    1. Создай бота через @BotFather
    2. В BotFather включи: /mybots → твой бот → Bot Settings → Business Mode → Enable
    3. В настройках Telegram Business подключи бота к своему аккаунту
    4. Укажи BOT_TOKEN и OWNER_ID ниже
"""

import logging
import os
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
OWNER_ID  = 6767821766
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

    # Фото
    if msg.photo:
        data["photos"] = [p.file_id for p in msg.photo]
        data["has_media"] = True

    # Стикер
    if msg.sticker:
        data["sticker"] = msg.sticker.file_id
        data["has_media"] = True

    # Голосовое
    if msg.voice:
        data["voice"] = msg.voice.file_id
        data["has_media"] = True

    # Видеосообщение (кружок)
    if msg.video_note:
        data["video_note"] = msg.video_note.file_id
        data["has_media"] = True

    # Документ / видео
    if msg.document:
        data["document"] = msg.document.file_id
        data["has_media"] = True
    if msg.video:
        data["video"] = msg.video.file_id
        data["has_media"] = True

    message_store[chat_id][msg.message_id] = data
    logger.info(f"Сохранено сообщение {msg.message_id} из чата {chat_id}")


async def handle_business_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает входящие бизнес-сообщения — сохраняет их."""
    msg = update.business_message
    if msg:
        store_message(msg)


async def handle_deleted_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Когда сообщения удаляются — отправляет их владельцу в ЛС."""
    deleted = update.deleted_business_messages
    if not deleted:
        return

    chat_id = deleted.chat.id
    chat_title = deleted.chat.title or deleted.chat.full_name or str(chat_id)

    for msg_id in deleted.message_ids:
        saved = message_store.get(chat_id, {}).get(msg_id)

        if not saved:
            # Сообщение не было сохранено (пришло до запуска бота)
            await context.bot.send_message(
                chat_id=OWNER_ID,
                text=(
                    f"🗑 <b>Удалено сообщение</b>\n"
                    f"💬 Чат: <b>{chat_title}</b>\n"
                    f"🆔 ID сообщения: <code>{msg_id}</code>\n"
                    f"⚠️ Содержимое недоступно (сообщение пришло до запуска бота)"
                ),
                parse_mode="HTML",
            )
            continue

        sender = saved["from_user"]
        username = f" ({saved['username']})" if saved["username"] else ""
        date = saved["date"]
        text = saved["text"]

        # Заголовок уведомления
        header = (
            f"🗑 <b>Удалено сообщение!</b>\n"
            f"💬 Чат: <b>{chat_title}</b>\n"
            f"👤 От: <b>{sender}</b>{username}\n"
            f"🕐 Дата: {date}\n"
        )

        # Отправка текста
        if text:
            await context.bot.send_message(
                chat_id=OWNER_ID,
                text=header + f"\n📝 Текст:\n{text}",
                parse_mode="HTML",
            )

        # Отправка фото (все варианты размеров — берём наибольший)
        if saved["photos"]:
            await context.bot.send_message(
                chat_id=OWNER_ID,
                text=header + "\n🖼 Фото:",
                parse_mode="HTML",
            )
            await context.bot.send_photo(
                chat_id=OWNER_ID,
                photo=saved["photos"][-1],   # наибольшее разрешение
                caption=f"Текст к фото: {text}" if text else None,
            )

        # Стикер
        if saved.get("sticker"):
            await context.bot.send_message(chat_id=OWNER_ID, text=header + "\n🎭 Стикер:", parse_mode="HTML")
            await context.bot.send_sticker(chat_id=OWNER_ID, sticker=saved["sticker"])

        # Голосовое
        if saved.get("voice"):
            await context.bot.send_message(chat_id=OWNER_ID, text=header + "\n🎤 Голосовое:", parse_mode="HTML")
            await context.bot.send_voice(chat_id=OWNER_ID, voice=saved["voice"])

        # Видеосообщение (кружок)
        if saved.get("video_note"):
            await context.bot.send_message(chat_id=OWNER_ID, text=header + "\n⭕ Видеосообщение:", parse_mode="HTML")
            await context.bot.send_video_note(chat_id=OWNER_ID, video_note=saved["video_note"])

        # Документ
        if saved.get("document"):
            await context.bot.send_message(chat_id=OWNER_ID, text=header + "\n📎 Документ:", parse_mode="HTML")
            await context.bot.send_document(chat_id=OWNER_ID, document=saved["document"])

        # Если не было никакого контента (редкий случай)
        if not text and not saved["has_media"]:
            await context.bot.send_message(
                chat_id=OWNER_ID,
                text=header + "\n❓ Тип сообщения не поддерживается",
                parse_mode="HTML",
            )

        logger.info(f"Уведомление об удалении отправлено: chat={chat_id}, msg_id={msg_id}")


async def handle_business_connection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Уведомляет владельца при подключении/отключении бизнес-чата."""
    conn = update.business_connection
    if not conn:
        return

    if conn.is_enabled:
        await context.bot.send_message(
            chat_id=OWNER_ID,
            text=(
                f"✅ <b>Бизнес-бот подключён!</b>\n"
                f"👤 Аккаунт: <b>{conn.user.full_name}</b>\n"
                f"🆔 ID: <code>{conn.user.id}</code>"
            ),
            parse_mode="HTML",
        )
    else:
        await context.bot.send_message(
            chat_id=OWNER_ID,
            text="❌ <b>Бизнес-бот отключён от аккаунта.</b>",
            parse_mode="HTML",
        )


def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    # Обработчики
    app.add_handler(BusinessConnectionHandler(handle_business_connection))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_business_message))
    app.add_handler(BusinessMessagesDeletedHandler(handle_deleted_messages))

    logger.info("Бот запущен...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
