"""
Ezzzy Game Bot
==============
bot.py — точка запуска приложения.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from contextlib import suppress

from dotenv import load_dotenv

# .env должен быть загружен до импорта модулей проекта.
load_dotenv()

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramNetworkError
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllGroupChats,
    BotCommandScopeDefault,
)

from core import (
    APP_NAME,
    APP_VERSION,
    close_application,
    initialize_application,
)
from database import (
    close_database,
    initialize_database,
)
from handlers import register_handlers


# ============================================================================
# LOGGING
# ============================================================================

LOG_LEVEL = os.getenv(
    "LOG_LEVEL",
    "INFO",
).upper()

logging.basicConfig(
    level=getattr(
        logging,
        LOG_LEVEL,
        logging.INFO,
    ),
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
# CONFIG
# ============================================================================

def get_bot_token() -> str:
    token = os.getenv(
        "BOT_TOKEN",
        "",
    ).strip()

    if not token:
        raise RuntimeError(
            "BOT_TOKEN не задан. "
            "Добавь BOT_TOKEN=<твой_токен> в .env."
        )

    return token


def get_owner_id() -> int:
    raw_owner_id = os.getenv(
        "OWNER_ID",
        "",
    ).strip()

    if not raw_owner_id:
        logger.warning(
            "OWNER_ID не задан. "
            "Глобальные owner-функции будут недоступны."
        )
        return 0

    try:
        owner_id = int(raw_owner_id)
    except ValueError as exc:
        raise RuntimeError(
            "OWNER_ID должен быть числом."
        ) from exc

    if owner_id <= 0:
        raise RuntimeError(
            "OWNER_ID должен быть положительным числом."
        )

    return owner_id


# ============================================================================
# TELEGRAM COMMANDS
# ============================================================================

async def configure_bot_commands(
    bot: Bot,
) -> None:
    default_commands = [
        BotCommand(
            command="start",
            description="Запустить бота",
        ),
        BotCommand(
            command="help",
            description="Помощь",
        ),
        BotCommand(
            command="profile",
            description="Профиль",
        ),
        BotCommand(
            command="stats",
            description="Статистика",
        ),
        BotCommand(
            command="balance",
            description="Баланс",
        ),
        BotCommand(
            command="games",
            description="Игры",
        ),
        BotCommand(
            command="bonus",
            description="Ежедневный бонус",
        ),
        BotCommand(
            command="top",
            description="Рейтинги",
        ),
        BotCommand(
            command="battlepass",
            description="Battle Pass",
        ),
        BotCommand(
            command="tag",
            description="Мои теги",
        ),
        BotCommand(
            command="inventory",
            description="Инвентарь",
        ),
    ]

    group_commands = [
        BotCommand(
            command="profile",
            description="Профиль",
        ),
        BotCommand(
            command="stats",
            description="Статистика",
        ),
        BotCommand(
            command="balance",
            description="Баланс",
        ),
        BotCommand(
            command="games",
            description="Игры",
        ),
        BotCommand(
            command="bonus",
            description="Ежедневный бонус",
        ),
        BotCommand(
            command="top",
            description="Рейтинги",
        ),
        BotCommand(
            command="battlepass",
            description="Battle Pass",
        ),
        BotCommand(
            command="tag",
            description="Мои теги",
        ),
        BotCommand(
            command="inventory",
            description="Инвентарь",
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

    logger.info(
        "Меню команд Telegram настроено."
    )


# ============================================================================
# BOT INFORMATION
# ============================================================================

async def log_bot_information(
    bot: Bot,
) -> None:
    me = await bot.get_me()

    username = (
        f"@{me.username}"
        if me.username
        else "без username"
    )

    logger.info(
        "Telegram-бот авторизован: %s (%s), ID=%s",
        username,
        me.first_name,
        me.id,
    )

    logger.info(
        "%s v%s подготовлен к запуску.",
        APP_NAME,
        APP_VERSION,
    )


# ============================================================================
# DISPATCHER
# ============================================================================

async def create_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher()

    register_handlers(dispatcher)

    logger.info(
        "Telegram-хендлеры зарегистрированы."
    )

    return dispatcher


# ============================================================================
# APPLICATION
# ============================================================================

async def run_bot() -> None:
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

    bot = Bot(
        token=token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
        ),
    )

    dispatcher = await create_dispatcher()

    try:
        # --------------------------------------------------------------------
        # APPLICATION
        # --------------------------------------------------------------------

        await initialize_application()

        # --------------------------------------------------------------------
        # DATABASE
        # --------------------------------------------------------------------

        await initialize_database()

        # --------------------------------------------------------------------
        # TELEGRAM
        # --------------------------------------------------------------------

        await log_bot_information(bot)
        await configure_bot_commands(bot)

        logger.info(
            "База данных успешно инициализирована."
        )

        logger.info(
            "Приложение готово."
        )

        # --------------------------------------------------------------------
        # POLLING
        # --------------------------------------------------------------------

        await bot.delete_webhook(
            drop_pending_updates=True,
        )

        logger.info(
            "Запуск long polling..."
        )

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
        logger.info(
            "Получена команда остановки приложения."
        )
        raise

    except Exception:
        logger.exception(
            "Критическая ошибка во время работы бота."
        )
        raise

    finally:
        logger.info(
            "Остановка приложения..."
        )

        with suppress(Exception):
            await close_application()

        with suppress(Exception):
            await close_database()

        with suppress(Exception):
            await bot.session.close()

        logger.info(
            "Все ресурсы закрыты."
        )


# ============================================================================
# ENTRY POINT
# ============================================================================

def main() -> None:
    try:
        asyncio.run(
            run_bot()
        )

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