"""
Ezzzy Game Bot
==============
Главная точка запуска Telegram-бота.

Архитектура проекта:
    bot.py       — запуск приложения, конфигурация, lifecycle
    core.py      — общие настройки, константы, вспомогательная инфраструктура
    database.py  — SQLAlchemy-модели и работа с БД
    handlers.py  — Telegram-хендлеры и команды
    services.py  — игровая логика, экономика, уровни, RP, модерация

Запуск:
    python bot.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from contextlib import suppress
from dotenv import load_dotenv

# Загружаем .env ДО импорта модулей проекта,
# которые читают конфигурацию при импорте.
load_dotenv()

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import (
    BotCommand,
    BotCommandScopeDefault,
    BotCommandScopeAllGroupChats,
)

from core import APP_NAME, APP_VERSION, close_application, initialize_application
from database import close_database, initialize_database
from handlers import register_handlers


# ============================================================================
# ОКРУЖЕНИЕ
# ============================================================================

load_dotenv()


# ============================================================================
# ЛОГИРОВАНИЕ
# ============================================================================

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format=(
        "%(asctime)s | "
        "%(levelname)-8s | "
        "%(name)s | "
        "%(message)s"
    ),
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(APP_NAME)


# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================


def get_bot_token() -> str:
    """
    Получает Telegram Bot Token из переменной окружения.

    BOT_TOKEN должен находиться в .env:

        BOT_TOKEN=123456:ABCDEF...

    Если токен отсутствует, приложение не запускается.
    """

    token = os.getenv("BOT_TOKEN", "").strip()

    if not token:
        logger.critical(
            "Не найден BOT_TOKEN. "
            "Добавь токен Telegram-бота в файл .env."
        )
        raise RuntimeError(
            "BOT_TOKEN не задан. "
            "Создай .env и добавь BOT_TOKEN=<твой_токен>."
        )

    return token


def get_owner_id() -> int:
    """
    Получает Telegram ID владельца бота.

    OWNER_ID нужен для глобальных административных функций.

    Если OWNER_ID не указан, бот всё равно сможет запуститься,
    но глобальные owner-команды будут недоступны.
    """

    raw_owner_id = os.getenv("OWNER_ID", "").strip()

    if not raw_owner_id:
        logger.warning(
            "OWNER_ID не задан. "
            "Глобальные команды владельца будут недоступны."
        )
        return 0

    try:
        owner_id = int(raw_owner_id)
    except ValueError as exc:
        raise RuntimeError(
            "OWNER_ID должен быть числом."
        ) from exc

    if owner_id < 1:
        raise RuntimeError(
            "OWNER_ID должен быть положительным числом."
        )

    return owner_id


# ============================================================================
# TELEGRAM COMMANDS
# ============================================================================


async def configure_bot_commands(bot: Bot) -> None:
    """
    Устанавливает стандартное меню команд Telegram.

    Здесь находятся только основные пользовательские команды.
    Расширенные команды будут обрабатываться handlers.py.
    """

    default_commands = [
        BotCommand(
            command="start",
            description="Запустить бота",
        ),
        BotCommand(
            command="help",
            description="Помощь и список возможностей",
        ),
        BotCommand(
            command="profile",
            description="Открыть свой профиль",
        ),
        BotCommand(
            command="stats",
            description="Посмотреть статистику",
        ),
        BotCommand(
            command="balance",
            description="Баланс арахиса",
        ),
        BotCommand(
            command="games",
            description="Мини-игры",
        ),
        BotCommand(
            command="bonus",
            description="Получить ежедневный бонус",
        ),
        BotCommand(
            command="top",
            description="Таблица лидеров",
        ),
    ]

    group_commands = [
        BotCommand(
            command="profile",
            description="Профиль игрока",
        ),
        BotCommand(
            command="stats",
            description="Статистика игрока",
        ),
        BotCommand(
            command="balance",
            description="Баланс арахиса",
        ),
        BotCommand(
            command="games",
            description="Мини-игры",
        ),
        BotCommand(
            command="bonus",
            description="Ежедневный бонус",
        ),
        BotCommand(
            command="top",
            description="Таблица лидеров",
        ),
        BotCommand(
            command="help",
            description="Помощь",
        ),
    ]

    await bot.set_my_commands(
        default_commands,
        scope=BotCommandScopeDefault(),
    )

    await bot.set_my_commands(
        group_commands,
        scope=BotCommandScopeAllGroupChats(),
    )

    logger.info("Меню команд Telegram настроено.")


# ============================================================================
# BOT INFORMATION
# ============================================================================


async def log_bot_information(bot: Bot) -> None:
    """
    Получает информацию о боте и выводит её в лог.
    """

    me = await bot.get_me()

    username = f"@{me.username}" if me.username else "без username"

    logger.info(
        "Telegram-бот авторизован: %s (%s), ID=%s",
        username,
        me.first_name,
        me.id,
    )

    logger.info(
        "%s v%s успешно подготовлен к запуску.",
        APP_NAME,
        APP_VERSION,
    )


# ============================================================================
# APPLICATION
# ============================================================================


async def create_dispatcher() -> Dispatcher:
    """
    Создаёт Dispatcher и регистрирует все обработчики.

    Вся Telegram-логика находится в handlers.py.
    """

    dispatcher = Dispatcher()

    register_handlers(dispatcher)

    logger.info("Telegram-хендлеры зарегистрированы.")

    return dispatcher


async def run_bot() -> None:
    """
    Основной жизненный цикл приложения.
    """

    token = get_bot_token()
    owner_id = get_owner_id()

    logger.info(
        "Запуск %s v%s...",
        APP_NAME,
        APP_VERSION,
    )

    if owner_id:
        logger.info(
            "Owner ID: %s",
            owner_id,
        )

    # ------------------------------------------------------------------------
    # БОТ
    # ------------------------------------------------------------------------

    bot = Bot(
        token=token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
        ),
    )

    # ------------------------------------------------------------------------
    # DISPATCHER
    # ------------------------------------------------------------------------

    dispatcher = await create_dispatcher()

    # ------------------------------------------------------------------------
    # ИНИЦИАЛИЗАЦИЯ ПРИЛОЖЕНИЯ
    # ------------------------------------------------------------------------

    await initialize_application()

    # ------------------------------------------------------------------------
    # БАЗА ДАННЫХ
    # ------------------------------------------------------------------------

    await initialize_database()

    # ------------------------------------------------------------------------
    # TELEGRAM
    # ------------------------------------------------------------------------

    await log_bot_information(bot)
    await configure_bot_commands(bot)

    logger.info("База данных успешно инициализирована.")
    logger.info("Приложение готово.")

    try:
        # Удаляем старые необработанные обновления Telegram.
        #
        # Это важно после перезапуска: бот не будет внезапно обрабатывать
        # сообщения/команды, которые накопились во время его выключения.
        await bot.delete_webhook(
            drop_pending_updates=True,
        )

        logger.info("Запуск long polling...")

        await dispatcher.start_polling(
            bot,
            allowed_updates=dispatcher.resolve_used_update_types(),
        )

    except TelegramNetworkError as exc:
        logger.exception(
            "Ошибка соединения с Telegram: %s",
            exc,
        )
        raise

    except asyncio.CancelledError:
        logger.info("Получена команда остановки приложения.")
        raise

    except Exception:
        logger.exception(
            "Критическая ошибка во время работы бота."
        )
        raise

    finally:
        # --------------------------------------------------------------------
        # ЗАКРЫТИЕ РЕСУРСОВ
        # --------------------------------------------------------------------

        logger.info("Остановка приложения...")

        with suppress(Exception):
            await close_application()

        with suppress(Exception):
            await close_database()

        with suppress(Exception):
            await bot.session.close()

        logger.info("Все ресурсы закрыты.")


# ============================================================================
# ENTRY POINT
# ============================================================================


def main() -> None:
    """
    Синхронная точка входа.

    Запуск:
        python bot.py
    """

    try:
        asyncio.run(run_bot())

    except KeyboardInterrupt:
        logger.info(
            "Бот остановлен пользователем."
        )

    except RuntimeError as exc:
        logger.critical(
            "Ошибка конфигурации: %s",
            exc,
        )
        sys.exit(1)

    except Exception:
        logger.critical(
            "Бот завершил работу из-за критической ошибки.",
            exc_info=True,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()