"""
Ezzzy Game Bot
==============
core.py — конфигурация и общая инфраструктура приложения.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


# ============================================================================
# ОСНОВНАЯ ИНФОРМАЦИЯ
# ============================================================================

APP_NAME = "Ezzzy Game Bot"
APP_VERSION = "1.0.0"


# ============================================================================
# ПУТИ
# ============================================================================

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"


# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================


@dataclass(frozen=True)
class Config:
    """
    Основная конфигурация приложения.

    Значения берутся из .env / переменных окружения.
    """

    bot_token: str
    owner_id: int

    database_url: str

    log_level: str

    # Экономика
    message_reward_min: int
    message_reward_max: int

    # XP
    message_xp: int

    # Антиспам
    message_reward_cooldown: int

    # Ежедневный бонус
    daily_bonus_min: int
    daily_bonus_max: int

    # Игры
    min_bet: int
    max_bet: int


_CONFIG: Config | None = None


# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================


def _get_string(
    name: str,
    default: str = "",
) -> str:
    """Получает строковую переменную окружения."""

    value = os.getenv(name)

    if value is None:
        return default

    return value.strip()


def _get_int(
    name: str,
    default: int,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    """Получает целочисленную переменную окружения."""

    raw_value = os.getenv(name)

    if raw_value is None or not raw_value.strip():
        value = default
    else:
        try:
            value = int(raw_value)
        except ValueError as exc:
            raise RuntimeError(
                f"{name} должен содержать целое число."
            ) from exc

    if minimum is not None and value < minimum:
        raise RuntimeError(
            f"{name} не может быть меньше {minimum}."
        )

    if maximum is not None and value > maximum:
        raise RuntimeError(
            f"{name} не может быть больше {maximum}."
        )

    return value


def _validate_config(config: Config) -> None:
    """Проверяет логическую корректность конфигурации."""

    if not config.bot_token:
        raise RuntimeError(
            "BOT_TOKEN не задан."
        )

    if config.owner_id < 0:
        raise RuntimeError(
            "OWNER_ID не может быть отрицательным."
        )

    if config.message_reward_min > config.message_reward_max:
        raise RuntimeError(
            "MESSAGE_REWARD_MIN не может быть больше "
            "MESSAGE_REWARD_MAX."
        )

    if config.daily_bonus_min > config.daily_bonus_max:
        raise RuntimeError(
            "DAILY_BONUS_MIN не может быть больше "
            "DAILY_BONUS_MAX."
        )

    if config.min_bet > config.max_bet:
        raise RuntimeError(
            "MIN_BET не может быть больше MAX_BET."
        )

    if config.message_xp < 0:
        raise RuntimeError(
            "MESSAGE_XP не может быть отрицательным."
        )

    if config.message_reward_min < 0:
        raise RuntimeError(
            "MESSAGE_REWARD_MIN не может быть отрицательным."
        )

    if config.message_reward_max < 0:
        raise RuntimeError(
            "MESSAGE_REWARD_MAX не может быть отрицательным."
        )


# ============================================================================
# ЗАГРУЗКА КОНФИГУРАЦИИ
# ============================================================================


def get_config() -> Config:
    """
    Возвращает единственный экземпляр конфигурации приложения.

    Конфигурация загружается лениво при первом обращении.
    """

    global _CONFIG

    if _CONFIG is not None:
        return _CONFIG

    bot_token = _get_string("BOT_TOKEN")

    if not bot_token:
        raise RuntimeError(
            "Не найден BOT_TOKEN. "
            "Добавь его в .env."
        )

    owner_id = _get_int(
        "OWNER_ID",
        default=0,
        minimum=0,
    )

    database_url = _get_string(
        "DATABASE_URL",
        default="sqlite+aiosqlite:///./data/ezzzy.db",
    )

    log_level = _get_string(
        "LOG_LEVEL",
        default="INFO",
    ).upper()

    message_reward_min = _get_int(
        "MESSAGE_REWARD_MIN",
        default=1,
        minimum=0,
    )

    message_reward_max = _get_int(
        "MESSAGE_REWARD_MAX",
        default=5,
        minimum=0,
    )

    message_xp = _get_int(
        "MESSAGE_XP",
        default=1,
        minimum=0,
    )

    message_reward_cooldown = _get_int(
        "MESSAGE_REWARD_COOLDOWN",
        default=60,
        minimum=0,
    )

    daily_bonus_min = _get_int(
        "DAILY_BONUS_MIN",
        default=100,
        minimum=0,
    )

    daily_bonus_max = _get_int(
        "DAILY_BONUS_MAX",
        default=500,
        minimum=0,
    )

    min_bet = _get_int(
        "MIN_BET",
        default=10,
        minimum=1,
    )

    max_bet = _get_int(
        "MAX_BET",
        default=1_000_000,
        minimum=1,
    )

    _CONFIG = Config(
        bot_token=bot_token,
        owner_id=owner_id,
        database_url=database_url,
        log_level=log_level,
        message_reward_min=message_reward_min,
        message_reward_max=message_reward_max,
        message_xp=message_xp,
        message_reward_cooldown=message_reward_cooldown,
        daily_bonus_min=daily_bonus_min,
        daily_bonus_max=daily_bonus_max,
        min_bet=min_bet,
        max_bet=max_bet,
    )

    _validate_config(_CONFIG)

    return _CONFIG


# ============================================================================
# ЭКОНОМИКА
# ============================================================================

CURRENCY_NAME = "арахис"
CURRENCY_SYMBOL = "🥜"


# ============================================================================
# УРОВНИ
# ============================================================================


def xp_for_level(level: int) -> int:
    """
    Возвращает необходимое количество общего XP для уровня.

    Формула намеренно нелинейная:
        XP = 100 * (level - 1)^2 + 100 * (level - 1)

    Получается:

        1 →       0 XP
        2 →     200 XP
        3 →     600 XP
        4 →   1 200 XP
        5 →   2 000 XP
        10 → 18 000 XP

    Функция централизована, поэтому позднее балансировку уровней
    можно изменить в одном месте.
    """

    if level <= 1:
        return 0

    n = level - 1

    return 100 * n * (n + 1)


def level_from_xp(xp: int) -> int:
    """
    Вычисляет уровень пользователя по общему XP.

    Расчёт выполняется без перебора тысяч уровней.
    """

    if xp <= 0:
        return 1

    level = 1

    while xp >= xp_for_level(level + 1):
        level += 1

    return level


def xp_to_next_level(xp: int) -> int:
    """
    Возвращает количество XP, оставшееся до следующего уровня.
    """

    current_level = level_from_xp(xp)
    next_level_xp = xp_for_level(current_level + 1)

    return max(
        0,
        next_level_xp - xp,
    )


# ============================================================================
# УРОВНЕВЫЕ РАЗБЛОКИРОВКИ
# ============================================================================


LEVEL_UNLOCKS: dict[int, tuple[str, ...]] = {
    1: (
        "profile",
        "stats",
        "coinflip",
        "dice",
    ),
    2: (
        "slots",
    ),
    3: (
        "roulette",
    ),
    5: (
        "football",
    ),
    7: (
        "basketball",
    ),
    10: (
        "tictactoe",
    ),
    15: (
        "blackjack",
    ),
    20: (
        "crash",
    ),
}


def get_unlocked_features(level: int) -> set[str]:
    """
    Возвращает все функции, доступные пользователю на данном уровне.
    """

    unlocked: set[str] = set()

    for required_level, features in LEVEL_UNLOCKS.items():
        if level >= required_level:
            unlocked.update(features)

    return unlocked


def is_feature_unlocked(
    level: int,
    feature: str,
) -> bool:
    """Проверяет доступность конкретной функции."""

    return feature in get_unlocked_features(level)


# ============================================================================
# RP-КОМАНДЫ
# ============================================================================


RP_ACTIONS: dict[str, dict[str, str]] = {
    "обнять": {
        "emoji": "🫂",
        "verb": "обнял",
    },
    "пожать": {
        "emoji": "🤝",
        "verb": "пожал руку",
    },
    "поцеловать": {
        "emoji": "😘",
        "verb": "поцеловал",
    },
    "пнуть": {
        "emoji": "🦵",
        "verb": "пнул",
    },
    "ударить": {
        "emoji": "👊",
        "verb": "ударил",
    },
    "погладить": {
        "emoji": "😊",
        "verb": "погладил",
    },
    "подмигнуть": {
        "emoji": "😉",
        "verb": "подмигнул",
    },
    "дать_пять": {
        "emoji": "🙌",
        "verb": "дал пять",
    },
    "поздравить": {
        "emoji": "🎉",
        "verb": "поздравил",
    },
    "пожалеть": {
        "emoji": "❤️",
        "verb": "пожалел",
    },
    "рассмешить": {
        "emoji": "😂",
        "verb": "рассмешил",
    },
    "напугать": {
        "emoji": "😱",
        "verb": "напугал",
    },
    "ткнуть": {
        "emoji": "👉",
        "verb": "ткнул",
    },
    "укусить": {
        "emoji": "🦷",
        "verb": "укусил",
    },
    "дать_подзатыльник": {
        "emoji": "🤜",
        "verb": "дал подзатыльник",
    },
    "кинуть_тапок": {
        "emoji": "🥿",
        "verb": "кинул тапок в",
    },
}


# ============================================================================
# МОДЕРАЦИЯ
# ============================================================================


MODERATION_ACTIONS = {
    "warn",
    "unwarn",
    "mute",
    "unmute",
    "ban",
    "unban",
    "kick",
    "purge",
    "setnick",
    "settag",
}


# ============================================================================
# НАСТРОЙКИ ПРОФИЛЯ
# ============================================================================

DEFAULT_PROFILE_NICK = None
DEFAULT_PROFILE_TAG = None


# ============================================================================
# ИНИЦИАЛИЗАЦИЯ ПРИЛОЖЕНИЯ
# ============================================================================


async def initialize_application() -> None:
    """
    Подготавливает окружение приложения.

    Создаёт необходимые каталоги и загружает конфигурацию.
    """

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    LOG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    get_config()


async def close_application() -> None:
    """
    Освобождает ресурсы приложения.

    Сейчас отдельные внешние ресурсы не используются.
    Функция существует как единая точка lifecycle,
    чтобы последующие расширения не меняли bot.py.
    """

    return None