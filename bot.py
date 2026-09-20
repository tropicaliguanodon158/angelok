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
    BotCommandScopeAllChatAdministrators,
    BotCommandScopeAllGroupChats,
    BotCommandScopeDefault,
)

from core import (
    APP_NAME,
    APP_VERSION,
    close_application,
    get_config,
    initialize_application,
)
from database import (
    AsyncSessionLocal,
    Giveaway,
    close_database,
    initialize_database,
    utcnow,
)
from handlers import register_handlers
from services import finish_giveaway


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
            command="inventory",
            description="Инвентарь",
        ),
        BotCommand(
            command="tag",
            description="Мои теги",
        ),
        BotCommand(
            command="battlepass",
            description="Battle Pass",
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
            description="Рейтинги",
        ),
        BotCommand(
            command="topsize",
            description="Топ по размеру",
        ),
        BotCommand(
            command="coinflip",
            description="Монетка",
        ),
        BotCommand(
            command="dice",
            description="Кости",
        ),
        BotCommand(
            command="slots",
            description="Слоты",
        ),
        BotCommand(
            command="roulette",
            description="Рулетка",
        ),
        BotCommand(
            command="guess",
            description="Угадай число",
        ),
        BotCommand(
            command="football",
            description="Футбол",
        ),
        BotCommand(
            command="basketball",
            description="Баскетбол",
        ),
        BotCommand(
            command="ttt",
            description="Крестики-нолики",
        ),
        BotCommand(
            command="blackjack",
            description="Блэкджек",
        ),
        BotCommand(
            command="crash",
            description="Crash",
        ),
        BotCommand(
            command="pay",
            description="Перевод арахиса",
        ),
        BotCommand(
            command="masturbate",
            description="Мастурбация",
        ),
        BotCommand(
            command="rob",
            description="Ограбить игрока",
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
            command="inventory",
            description="Инвентарь",
        ),
        BotCommand(
            command="tag",
            description="Мои теги",
        ),
        BotCommand(
            command="battlepass",
            description="Battle Pass",
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
            command="topsize",
            description="Топ по размеру",
        ),
        BotCommand(
            command="coinflip",
            description="Монетка",
        ),
        BotCommand(
            command="dice",
            description="Кости",
        ),
        BotCommand(
            command="slots",
            description="Слоты",
        ),
        BotCommand(
            command="roulette",
            description="Рулетка",
        ),
        BotCommand(
            command="guess",
            description="Угадай число",
        ),
        BotCommand(
            command="football",
            description="Футбол",
        ),
        BotCommand(
            command="basketball",
            description="Баскетбол",
        ),
        BotCommand(
            command="ttt",
            description="Крестики-нолики",
        ),
        BotCommand(
            command="blackjack",
            description="Блэкджек",
        ),
        BotCommand(
            command="crash",
            description="Crash",
        ),
        BotCommand(
            command="help",
            description="Помощь",
        ),
    ]

    admin_commands = [
        BotCommand(
            command="warn",
            description="Выдать предупреждение",
        ),
        BotCommand(
            command="unwarn",
            description="Снять предупреждение",
        ),
        BotCommand(
            command="warnings",
            description="Предупреждения",
        ),
        BotCommand(
            command="mute",
            description="Заглушить",
        ),
        BotCommand(
            command="unmute",
            description="Снять мут",
        ),
        BotCommand(
            command="ban",
            description="Заблокировать",
        ),
        BotCommand(
            command="unban",
            description="Разблокировать",
        ),
        BotCommand(
            command="kick",
            description="Исключить",
        ),
        BotCommand(
            command="purge",
            description="Удалить сообщения",
        ),
        BotCommand(
            command="setnick",
            description="Изменить ник",
        ),
        BotCommand(
            command="setrole",
            description="Назначить роль",
        ),
        BotCommand(
            command="delrole",
            description="Снять роль",
        ),
        BotCommand(
            command="setperm",
            description="Настроить права",
        ),
        BotCommand(
            command="give",
            description="Выдать арахис",
        ),
        BotCommand(
            command="take",
            description="Забрать арахис",
        ),
        BotCommand(
            command="setbalance",
            description="Установить баланс",
        ),
        BotCommand(
            command="setlevel",
            description="Установить уровень",
        ),
        BotCommand(
            command="giveaway",
            description="Создать розыгрыш",
        ),
        BotCommand(
            command="giveaway_join",
            description="Войти в розыгрыш",
        ),
        BotCommand(
            command="giveaway_finish",
            description="Завершить розыгрыш",
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

    await bot.set_my_commands(
        admin_commands,
        scope=BotCommandScopeAllChatAdministrators(),
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
# GIVEAWAY SCHEDULER
# ============================================================================

GIVEAWAY_CHECK_INTERVAL = 15


async def process_expired_giveaways(
    bot: Bot,
) -> None:
    """
    Автоматически завершает просроченные розыгрыши.

    Проверка выполняется регулярно, поэтому giveaway завершится
    даже если после его окончания в чате никто ничего не напишет.
    """

    while True:
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Giveaway).where(
                        Giveaway.status == "active",
                        Giveaway.ends_at <= utcnow(),
                    ).order_by(
                        Giveaway.ends_at.asc(),
                        Giveaway.id.asc(),
                    ).limit(100)
                )

                giveaways = list(
                    result.scalars().all()
                )

                for giveaway in giveaways:
                    service_result = await finish_giveaway(
                        session=session,
                        giveaway_id=giveaway.id,
                        chat_id=giveaway.chat_id,
                    )

                    if not service_result.success:
                        logger.warning(
                            "Не удалось автоматически завершить "
                            "giveaway id=%s: %s",
                            giveaway.id,
                            service_result.message,
                        )

                        await session.rollback()
                        continue

                    await session.commit()

                    if not service_result.message:
                        continue

                    try:
                        await bot.send_message(
                            giveaway.chat_id,
                            service_result.message,
                        )
                    except TelegramNetworkError:
                        logger.exception(
                            "Сетевая ошибка при отправке результата "
                            "giveaway id=%s.",
                            giveaway.id,
                        )
                    except Exception:
                        logger.exception(
                            "Не удалось отправить результат "
                            "giveaway id=%s в чат %s.",
                            giveaway.id,
                            giveaway.chat_id,
                        )

        except asyncio.CancelledError:
            raise

        except Exception:
            logger.exception(
                "Ошибка фоновой обработки giveaway."
            )

        await asyncio.sleep(
            GIVEAWAY_CHECK_INTERVAL
        )


# ============================================================================
# APPLICATION
# ============================================================================

async def run_bot() -> None:
    token = get_bot_token()

    # Загружает и валидирует конфигурацию до создания Bot.
    config = get_config()

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

    giveaway_task: asyncio.Task | None = None

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

        await log_bot_information(
            bot
        )

        await configure_bot_commands(
            bot
        )

        logger.info(
            "База данных успешно инициализирована."
        )

        logger.info(
            "Приложение готово."
        )

        # --------------------------------------------------------------------
        # GIVEAWAY BACKGROUND TASK
        # --------------------------------------------------------------------

        giveaway_task = asyncio.create_task(
            process_expired_giveaways(
                bot
            ),
            name="giveaway-expiration-worker",
        )

        logger.info(
            "Фоновая обработка giveaway запущена."
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

        if giveaway_task is not None:
            giveaway_task.cancel()

            with suppress(
                asyncio.CancelledError,
                Exception,
            ):
                await giveaway_task

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