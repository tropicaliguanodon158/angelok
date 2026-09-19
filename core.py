"""
Ezzzy Game Bot
==============

core.py — конфигурация и общая игровая инфраструктура.

Здесь НЕ должно быть бизнес-логики работы с БД.
Здесь хранятся:

    - конфигурация;
    - экономика;
    - уровни;
    - Battle Pass;
    - разблокировки игр;
    - обычные RP-команды;
    - 18+ RP-команды;
    - cooldown;
    - механика размера;
    - болезни;
    - ребёнок;
    - предметы кейсов;
    - теги;
    - роли модерации;
    - общие игровые ограничения.

Главный принцип:
    если игровое число/правило нужно изменить —
    сначала ищем его здесь, а не по всему проекту.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


# ============================================================================
# ОСНОВНАЯ ИНФОРМАЦИЯ
# ============================================================================

APP_NAME = "Ezzzy Game Bot"
APP_VERSION = "2.0.0"


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

    Важно:

        MESSAGE_XP = XP за КАЖДОЕ сообщение.

    Никакого cooldown для XP нет.

    MESSAGE_REWARD_COOLDOWN относится только к денежной награде
    за сообщение и НЕ влияет на XP.
    """

    bot_token: str
    owner_id: int

    database_url: str

    log_level: str

    # ----------------------------------------------------------------------
    # Экономика за сообщения
    # ----------------------------------------------------------------------

    message_reward_min: int
    message_reward_max: int

    # ----------------------------------------------------------------------
    # XP
    # ----------------------------------------------------------------------

    message_xp: int

    # ----------------------------------------------------------------------
    # Cooldown денежной награды за сообщение
    #
    # ВАЖНО:
    # этот cooldown НЕ блокирует XP.
    # ----------------------------------------------------------------------

    message_reward_cooldown: int

    # ----------------------------------------------------------------------
    # Ежедневный бонус
    # ----------------------------------------------------------------------

    daily_bonus_min: int
    daily_bonus_max: int

    # ----------------------------------------------------------------------
    # Игры
    # ----------------------------------------------------------------------

    min_bet: int
    max_bet: int


_CONFIG: Config | None = None


# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ CONFIG
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
# ЗАГРУЗКА CONFIG
# ============================================================================


def get_config() -> Config:
    """
    Возвращает единственный экземпляр конфигурации.
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
# ОБЩИЕ ЦЕНЫ
# ============================================================================

# Обычный RP.
NORMAL_RP_COST = 10

# 18+ RP.
ADULT_RP_COST = 50

# Ограбление.
ROB_COOLDOWN_HOURS = 24

# Минимальный шанс/логика ограбления реализуется в services.py.
ROB_REQUIRES_LARGER_SIZE = True


# ============================================================================
# УРОВНИ
# ============================================================================


def xp_for_level(level: int) -> int:
    """
    Возвращает необходимое общее количество XP для уровня.

    Формула:

        XP = 100 * (level - 1) * level

    Примеры:

        level 1  = 0
        level 2  = 200
        level 3  = 600
        level 4  = 1200
        level 5  = 2000
        level 10 = 9000
        level 20 = 38000

    XP начисляется за каждое сообщение.
    """

    if level <= 1:
        return 0

    n = level - 1

    return 100 * n * (n + 1)


def level_from_xp(xp: int) -> int:
    """
    Вычисляет уровень по общему XP.
    """

    if xp <= 0:
        return 1

    level = 1

    while xp >= xp_for_level(level + 1):
        level += 1

    return level


def xp_to_next_level(xp: int) -> int:
    """
    Возвращает XP до следующего уровня.
    """

    current_level = level_from_xp(xp)

    next_level_xp = xp_for_level(
        current_level + 1,
    )

    return max(
        0,
        next_level_xp - xp,
    )


# ============================================================================
# УРОВНЕВЫЕ РАЗБЛОКИРОВКИ ИГР
# ============================================================================

"""
Игры открываются по обычному уровню пользователя.

Важно:
    недостаточно просто написать уровень здесь.

    handlers.py / games.py должны вызывать:
        is_feature_unlocked(...)

Иначе разблокировки снова станут декоративными.
"""


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


FEATURE_DISPLAY_NAMES: dict[str, str] = {
    "profile": "Профиль",
    "stats": "Статистика",
    "coinflip": "Монетка",
    "dice": "Кости",
    "slots": "Слоты",
    "roulette": "Рулетка",
    "football": "Футбол",
    "basketball": "Баскетбол",
    "tictactoe": "Крестики-нолики",
    "blackjack": "Блэкджек",
    "crash": "Crash",
}


def get_unlocked_features(level: int) -> set[str]:
    """
    Возвращает все доступные функции.
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
    """
    Проверяет, доступна ли функция.
    """

    return feature in get_unlocked_features(level)


def get_feature_required_level(
    feature: str,
) -> int | None:
    """
    Возвращает минимальный уровень для функции.
    """

    for level, features in LEVEL_UNLOCKS.items():
        if feature in features:
            return level

    return None


# ============================================================================
# BATTLE PASS
# ============================================================================

"""
Battle Pass использует отдельный battle_pass_level.

XP Battle Pass начисляется вместе с сообщениями.

Базовый вариант:
    1 сообщение = 1 BP XP.

Награды выдаются один раз за каждый уровень.
"""

BATTLE_PASS_SEASON = 1

BATTLE_PASS_MAX_LEVEL = 30

BATTLE_PASS_XP_PER_MESSAGE = 1

BATTLE_PASS_XP_PER_LEVEL = 100


@dataclass(frozen=True)
class BattlePassReward:
    """
    Награда Battle Pass.
    """

    reward_type: str
    amount: int = 0
    item_code: str | None = None
    tag_code: str | None = None
    description: str = ""


BATTLE_PASS_REWARDS: dict[int, BattlePassReward] = {
    1: BattlePassReward(
        reward_type="peanuts",
        amount=100,
        description="🥜 100 арахиса",
    ),

    2: BattlePassReward(
        reward_type="xp",
        amount=100,
        description="⭐ 100 XP",
    ),

    3: BattlePassReward(
        reward_type="peanuts",
        amount=250,
        description="🥜 250 арахиса",
    ),

    4: BattlePassReward(
        reward_type="case",
        item_code="basic_case",
        description="📦 Обычный кейс",
    ),

    5: BattlePassReward(
        reward_type="peanuts",
        amount=500,
        description="🥜 500 арахиса",
    ),

    6: BattlePassReward(
        reward_type="xp",
        amount=250,
        description="⭐ 250 XP",
    ),

    7: BattlePassReward(
        reward_type="peanuts",
        amount=750,
        description="🥜 750 арахиса",
    ),

    8: BattlePassReward(
        reward_type="case",
        item_code="basic_case",
        description="📦 Обычный кейс",
    ),

    9: BattlePassReward(
        reward_type="peanuts",
        amount=1_000,
        description="🥜 1 000 арахиса",
    ),

    10: BattlePassReward(
        reward_type="xp",
        amount=500,
        description="⭐ 500 XP",
    ),

    11: BattlePassReward(
        reward_type="peanuts",
        amount=1_500,
        description="🥜 1 500 арахиса",
    ),

    12: BattlePassReward(
        reward_type="case",
        item_code="rare_case",
        description="💎 Редкий кейс",
    ),

    13: BattlePassReward(
        reward_type="peanuts",
        amount=2_000,
        description="🥜 2 000 арахиса",
    ),

    14: BattlePassReward(
        reward_type="xp",
        amount=750,
        description="⭐ 750 XP",
    ),

    15: BattlePassReward(
        reward_type="peanuts",
        amount=2_500,
        description="🥜 2 500 арахиса",
    ),

    16: BattlePassReward(
        reward_type="case",
        item_code="rare_case",
        description="💎 Редкий кейс",
    ),

    17: BattlePassReward(
        reward_type="peanuts",
        amount=3_000,
        description="🥜 3 000 арахиса",
    ),

    18: BattlePassReward(
        reward_type="xp",
        amount=1_000,
        description="⭐ 1 000 XP",
    ),

    19: BattlePassReward(
        reward_type="peanuts",
        amount=4_000,
        description="🥜 4 000 арахиса",
    ),

    20: BattlePassReward(
        reward_type="case",
        item_code="epic_case",
        description="🔥 Эпический кейс",
    ),

    21: BattlePassReward(
        reward_type="peanuts",
        amount=5_000,
        description="🥜 5 000 арахиса",
    ),

    22: BattlePassReward(
        reward_type="xp",
        amount=1_500,
        description="⭐ 1 500 XP",
    ),

    23: BattlePassReward(
        reward_type="peanuts",
        amount=7_500,
        description="🥜 7 500 арахиса",
    ),

    24: BattlePassReward(
        reward_type="case",
        item_code="epic_case",
        description="🔥 Эпический кейс",
    ),

    25: BattlePassReward(
        reward_type="peanuts",
        amount=10_000,
        description="🥜 10 000 арахиса",
    ),

    26: BattlePassReward(
        reward_type="xp",
        amount=2_000,
        description="⭐ 2 000 XP",
    ),

    27: BattlePassReward(
        reward_type="peanuts",
        amount=15_000,
        description="🥜 15 000 арахиса",
    ),

    28: BattlePassReward(
        reward_type="case",
        item_code="legendary_case",
        description="👑 Легендарный кейс",
    ),

    29: BattlePassReward(
        reward_type="peanuts",
        amount=25_000,
        description="🥜 25 000 арахиса",
    ),

    30: BattlePassReward(
        reward_type="tag",
        tag_code="living_legend",
        description="🏆 Тег «ЖИВАЯ ЛЕГЕНДА»",
    ),
}


def battle_pass_xp_for_level(level: int) -> int:
    """
    Необходимый BP XP для уровня.

    Уровень 1 начинается с 0 XP.
    """

    if level <= 1:
        return 0

    return (level - 1) * BATTLE_PASS_XP_PER_LEVEL


def battle_pass_level_from_xp(xp: int) -> int:
    """
    Возвращает BP уровень.
    """

    if xp <= 0:
        return 1

    level = 1

    while (
        level < BATTLE_PASS_MAX_LEVEL
        and xp >= battle_pass_xp_for_level(level + 1)
    ):
        level += 1

    return min(
        level,
        BATTLE_PASS_MAX_LEVEL,
    )


def get_battle_pass_reward(
    level: int,
) -> BattlePassReward | None:
    """
    Возвращает награду BP уровня.
    """

    return BATTLE_PASS_REWARDS.get(level)


# ============================================================================
# РАЗМЕР
# ============================================================================

"""
Размер хранится в сантиметрах.

Начальный размер:
    0.0

Изменение происходит:

    + при 18+ RP;
    + при повышении обычного уровня;
    + через некоторые предметы;
    - от болезни;
    - когда другой игрок использует на пользователе 18+ RP.

Все числа здесь.
"""

INITIAL_PENIS_SIZE = 0.0

# Бонус за повышение обычного уровня.
LEVEL_UP_SIZE_BONUS = 0.10

# Базовый рост от 18+ RP.
ADULT_RP_SIZE_GAIN_MIN = 0.10
ADULT_RP_SIZE_GAIN_MAX = 0.50

# Сколько снимается с цели при 18+ RP.
ADULT_RP_TARGET_SIZE_LOSS_MIN = 0.05
ADULT_RP_TARGET_SIZE_LOSS_MAX = 0.20

# Rubber Pussy:
RUBBER_DAILY_GROWTH_CHANCE = 0.20
RUBBER_DAILY_GROWTH_AMOUNT = 1.0

RUBBER_MASTURBATION_GAIN_MIN = 0.05
RUBBER_MASTURBATION_GAIN_MAX = 0.20


# ============================================================================
# 18+ RP
# ============================================================================

"""
Команды намеренно описываются абстрактно.

Никакой графики/эротического текста здесь нет.

Каждая команда имеет:

    key
    aliases
    emoji
    actor_modifier
    target_modifier

Дальнейшая механика применяется одинаково через rp.py.
"""


@dataclass(frozen=True)
class AdultRPAction:
    key: str
    aliases: tuple[str, ...]
    emoji: str

    # Множитель роста исполнителя.
    actor_size_multiplier: float = 1.0

    # Множитель потери цели.
    target_size_multiplier: float = 1.0

    # Дополнительный плоский бонус.
    actor_flat_bonus: float = 0.0

    # Разрешает специальные предметные эффекты.
    can_use_lubricant: bool = True

    # Используется для отображения/баланса.
    description: str = ""


ADULT_RP_ACTIONS: dict[str, AdultRPAction] = {
    "взять": AdultRPAction(
        key="взять",
        aliases=("взять",),
        emoji="😈",
        actor_size_multiplier=1.00,
        target_size_multiplier=1.00,
        description="Базовое действие.",
    ),

    "прижать": AdultRPAction(
        key="прижать",
        aliases=("прижать",),
        emoji="😏",
        actor_size_multiplier=1.10,
        target_size_multiplier=1.00,
        description="Немного увеличивает рост исполнителя.",
    ),

    "доминировать": AdultRPAction(
        key="доминировать",
        aliases=("доминировать",),
        emoji="👑",
        actor_size_multiplier=1.20,
        target_size_multiplier=1.10,
        description="Усиленный вариант.",
    ),

    "проверить": AdultRPAction(
        key="проверить",
        aliases=("проверить",),
        emoji="🔎",
        actor_size_multiplier=0.90,
        target_size_multiplier=0.80,
        description="Снижает размер цели немного сильнее.",
    ),

    "испытать": AdultRPAction(
        key="испытать",
        aliases=("испытать",),
        emoji="🔥",
        actor_size_multiplier=1.30,
        target_size_multiplier=1.20,
        description="Сильное действие.",
    ),

    "пошалить": AdultRPAction(
        key="пошалить",
        aliases=("пошалить",),
        emoji="😈",
        actor_size_multiplier=1.15,
        target_size_multiplier=0.90,
        description="Средний вариант.",
    ),

    "задеть": AdultRPAction(
        key="задеть",
        aliases=("задеть",),
        emoji="😏",
        actor_size_multiplier=0.95,
        target_size_multiplier=1.15,
        description="Рискованный вариант.",
    ),

    "потроллить": AdultRPAction(
        key="потроллить",
        aliases=("потроллить",),
        emoji="😂",
        actor_size_multiplier=1.05,
        target_size_multiplier=1.05,
        description="Шуточное действие.",
    ),
}


def get_adult_rp_action(
    action: str,
) -> AdultRPAction | None:
    """
    Получает 18+ RP действие по ключу или alias.
    """

    normalized = action.strip().lower()

    for item in ADULT_RP_ACTIONS.values():
        if normalized == item.key:
            return item

        if normalized in item.aliases:
            return item

    return None


# ============================================================================
# ОБЫЧНЫЕ RP-КОМАНДЫ
# ============================================================================

"""
Ключи с underscore позволяют безопасно хранить multi-word команды.

Например:

    дать пять
    дать подзатыльник
    кинуть тапок

Парсер в rp.py будет использовать отдельную таблицу aliases,
поэтому старый баг с split(maxsplit=1) исчезает.
"""


RP_ACTIONS: dict[str, dict[str, object]] = {
    "обнять": {
        "aliases": ("обнять",),
        "emoji": "🫂",
        "verb": "обнял",
    },

    "пожать": {
        "aliases": ("пожать", "пожать руку"),
        "emoji": "🤝",
        "verb": "пожал руку",
    },

    "поцеловать": {
        "aliases": ("поцеловать",),
        "emoji": "😘",
        "verb": "поцеловал",
    },

    "пнуть": {
        "aliases": ("пнуть",),
        "emoji": "🦵",
        "verb": "пнул",
    },

    "ударить": {
        "aliases": ("ударить",),
        "emoji": "👊",
        "verb": "ударил",
    },

    "погладить": {
        "aliases": ("погладить",),
        "emoji": "😊",
        "verb": "погладил",
    },

    "подмигнуть": {
        "aliases": ("подмигнуть",),
        "emoji": "😉",
        "verb": "подмигнул",
    },

    "дать_пять": {
        "aliases": (
            "дать пять",
            "дать_пять",
        ),
        "emoji": "🙌",
        "verb": "дал пять",
    },

    "поздравить": {
        "aliases": ("поздравить",),
        "emoji": "🎉",
        "verb": "поздравил",
    },

    "пожалеть": {
        "aliases": ("пожалеть",),
        "emoji": "❤️",
        "verb": "пожалел",
    },

    "рассмешить": {
        "aliases": ("рассмешить",),
        "emoji": "😂",
        "verb": "рассмешил",
    },

    "напугать": {
        "aliases": ("напугать",),
        "emoji": "😱",
        "verb": "напугал",
    },

    "ткнуть": {
        "aliases": ("ткнуть",),
        "emoji": "👉",
        "verb": "ткнул",
    },

    "укусить": {
        "aliases": ("укусить",),
        "emoji": "🦷",
        "verb": "укусил",
    },

    "дать_подзатыльник": {
        "aliases": (
            "дать подзатыльник",
            "дать_подзатыльник",
        ),
        "emoji": "🤜",
        "verb": "дал подзатыльник",
    },

    "кинуть_тапок": {
        "aliases": (
            "кинуть тапок",
            "кинуть_тапок",
        ),
        "emoji": "🥿",
        "verb": "кинул тапок в",
    },
}


# ============================================================================
# RP PARSER
# ============================================================================

def get_rp_action_by_alias(
    text: str,
) -> tuple[str, dict[str, object]] | None:
    """
    Ищет RP-команду по полному alias.

    ВАЖНО:
        проверяется полный alias, а не только первое слово.

    Поэтому:

        "дать пять @user"

    корректно распознаётся как:

        дать_пять

    а не как:

        дать
    """

    normalized = " ".join(
        text.strip().lower().split()
    )

    candidates: list[
        tuple[str, dict[str, object]]
    ] = []

    for key, data in RP_ACTIONS.items():
        aliases = data.get("aliases", ())

        for alias in aliases:
            if normalized == str(alias):
                candidates.append(
                    (key, data)
                )

    if not candidates:
        return None

    return candidates[0]


# ============================================================================
# COOLDOWNS
# ============================================================================

# 18+ RP — 15 минут.
ADULT_RP_COOLDOWN_SECONDS = 15 * 60

# Дрочка — 6 часов.
MASTURBATION_COOLDOWN_SECONDS = 6 * 60 * 60

# Rubber Pussy уменьшает оба cooldown на 50%.
RUBBER_COOLDOWN_MULTIPLIER = 0.50


# ============================================================================
# БОЛЕЗНЬ
# ============================================================================

DISEASE_CONTRACT_CHANCE = 0.50

DISEASE_TICK_HOURS = 1

DISEASE_SIZE_LOSS_PER_TICK = 0.50

DISEASE_MEDICINE_COST = 500

VENEREOLOGIST_COST = 5_000

VENEREOLOGIST_CURE_CHANCE = 0.20


# ============================================================================
# РЕБЁНОК
# ============================================================================

"""
Механика полностью игровая и не содержит графического контента.

При срабатывании события:

    actor получает состояние "ребёнок";

    actor не может использовать 18+ RP;

    с баланса каждый час списывается содержание;

    через 18 часов эффект заканчивается.
"""

IMPREGNATION_CHANCE_WITHOUT_CONDOM = 0.15

IMPREGNATION_CHANCE_WITH_CONDOM = 0.05

CHILD_DURATION_HOURS = 18

CHILD_SUPPORT_PER_HOUR = 10_000

ABORT_COST = 30_000

ABORT_SUCCESS_CHANCE = 0.50


# ============================================================================
# КОНДОМ
# ============================================================================

CONDOM_ITEM_CODE = "condom"

CONDOM_DISEASE_PROTECTION_CHANCE = 0.90

CONDOM_ITEM_STACKABLE = True

CONDOM_ITEM_ONE_USE = True


# ============================================================================
# ЛУБРИКАНТ
# ============================================================================

LUBRICANT_ITEM_CODE = "lubricant"

LUBRICANT_GROWTH_BONUS = 0.05

LUBRICANT_ITEM_STACKABLE = True

LUBRICANT_ITEM_ONE_USE = True


# ============================================================================
# DILDO
# ============================================================================

DILDO_ITEM_CODE = "dildo"

DILDO_MIN_USES = 3

DILDO_MAX_USES = 5

DILDO_DUPLICATE_COMPENSATION = 5_000

DILDO_MAX_OWNED = 1

DILDO_ITEM_ONE_USE = True


# ============================================================================
# RUBBER PUSSY
# ============================================================================

RUBBER_PUSSY_ITEM_CODE = "rubber_pussy"

RUBBER_PUSSY_COOLDOWN_MULTIPLIER = 0.50

RUBBER_PUSSY_DAILY_CHANCE = 0.20

RUBBER_PUSSY_DAILY_BONUS = 1.0

RUBBER_PUSSY_MASTURBATION_MIN = 0.05

RUBBER_PUSSY_MASTURBATION_MAX = 0.20

RUBBER_PUSSY_ITEM_ONE_USE = False

RUBBER_PUSSY_MAX_OWNED = 1


# ============================================================================
# СИЛИКОНОВЫЙ ИМПЛАНТ
# ============================================================================

SILICONE_IMPLANT_ITEM_CODE = "silicone_implant"

SILICONE_IMPLANT_BONUS = 1.0

SILICONE_IMPLANT_AUTO_USE = True

SILICONE_IMPLANT_ITEM_ONE_USE = True


# ============================================================================
# DRОЧКА
# ============================================================================

MASTURBATION_MIN_GAIN = 0.05

MASTURBATION_MAX_GAIN = 0.20

MASTURBATION_REQUIRES_RUBBER_PUSSY = False

"""
Без Rubber Pussy команда всё равно может существовать.

Разница:
    обычная дрочка:
        cooldown 6 часов;
        размер не обязан увеличиваться.

    Rubber Pussy:
        cooldown -50%;
        гарантированный случайный рост 0.05–0.20 см.
"""


# ============================================================================
# ОГРАБЛЕНИЕ
# ============================================================================

ROB_MIN_SUCCESS_CHANCE = 0.25

ROB_MAX_SUCCESS_CHANCE = 0.75

ROB_MIN_REWARD_PERCENT = 0.05

ROB_MAX_REWARD_PERCENT = 0.25

ROB_COOLDOWN_SECONDS = 24 * 60 * 60


# ============================================================================
# CASES / INVENTORY
# ============================================================================

"""
Коды предметов.

Фактические записи InventoryItem будут создаваться inventory.py.

Здесь только единый список идентификаторов и правила.
"""


CASE_BASIC = "basic_case"
CASE_RARE = "rare_case"
CASE_EPIC = "epic_case"
CASE_LEGENDARY = "legendary_case"


ITEM_LUBRICANT = "lubricant"
ITEM_DILDO = "dildo"
ITEM_RUBBER_PUSSY = "rubber_pussy"
ITEM_SILICONE_IMPLANT = "silicone_implant"
ITEM_CONDOM = "condom"


CASE_CODES = {
    CASE_BASIC,
    CASE_RARE,
    CASE_EPIC,
    CASE_LEGENDARY,
}


# ============================================================================
# TAGS
# ============================================================================

"""
Теги НЕ выставляются через /settag.

Пользователь:

    /tag

получает inline-кнопки со своими тегами.

Выдача происходит:

    - через Battle Pass;
    - через кейсы;
    - через достижения;
    - через специальные игровые события.
"""


TAG_LIVING_LEGEND = "living_legend"

TAG_DISPLAY_NAMES: dict[str, str] = {
    TAG_LIVING_LEGEND: "ЖИВАЯ ЛЕГЕНДА",
}


# ============================================================================
# МОДЕРАЦИЯ
# ============================================================================

"""
Внутренние роли бота:

    owner
    head_admin
    admin
    moderator

Иерархия:

    owner
        ↓
    head_admin
        ↓
    admin
        ↓
    moderator

OWNER:
    задаётся через OWNER_ID.

HEAD ADMIN:
    назначается owner.

ADMIN:
    назначается head admin.

MODERATOR:
    назначается head admin.

Обычные Telegram admin/creator сами по себе не становятся
внутренними ролями бота, если мы явно их не назначили.
"""


ROLE_OWNER = "owner"
ROLE_HEAD_ADMIN = "head_admin"
ROLE_ADMIN = "admin"
ROLE_MODERATOR = "moderator"


STAFF_ROLES = (
    ROLE_OWNER,
    ROLE_HEAD_ADMIN,
    ROLE_ADMIN,
    ROLE_MODERATOR,
)


ROLE_POWER: dict[str, int] = {
    ROLE_MODERATOR: 10,
    ROLE_ADMIN: 20,
    ROLE_HEAD_ADMIN: 30,
    ROLE_OWNER: 40,
}


def role_power(role: str | None) -> int:
    """
    Возвращает числовой приоритет роли.
    """

    if role is None:
        return 0

    return ROLE_POWER.get(
        role,
        0,
    )


def can_manage_role(
    actor_role: str | None,
    target_role: str,
) -> bool:
    """
    Проверяет, может ли actor назначать/снимать target_role.

    Логика:

        owner:
            head_admin

        head_admin:
            admin
            moderator

        admin:
            никого

        moderator:
            никого
    """

    if actor_role == ROLE_OWNER:
        return target_role == ROLE_HEAD_ADMIN

    if actor_role == ROLE_HEAD_ADMIN:
        return target_role in {
            ROLE_ADMIN,
            ROLE_MODERATOR,
        }

    return False


# ============================================================================
# MODERATION COMMANDS
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
}


"""
Уровень доступа по умолчанию.

Можно изменить через отдельную команду настроек модерации.

Допустимые значения:

    staff
    admin
    head_admin

Где:

    staff:
        moderator + admin + head_admin + owner

    admin:
        admin + head_admin + owner

    head_admin:
        head_admin + owner
"""


DEFAULT_MODERATION_PERMISSIONS: dict[str, str] = {
    "warn": "staff",
    "unwarn": "staff",

    "mute": "staff",
    "unmute": "staff",

    "ban": "admin",
    "unban": "admin",

    "kick": "staff",

    "purge": "staff",

    "setnick": "admin",
}


MODERATION_PERMISSION_LEVEL: dict[str, int] = {
    "staff": 10,
    "admin": 20,
    "head_admin": 30,
}


def can_use_moderation_command(
    role: str | None,
    required_access: str,
) -> bool:
    """
    Проверяет доступ к moderation-команде.
    """

    if role is None:
        return False

    if role == ROLE_OWNER:
        return True

    if required_access == "staff":
        return role in STAFF_ROLES

    if required_access == "admin":
        return role in {
            ROLE_ADMIN,
            ROLE_HEAD_ADMIN,
        }

    if required_access == "head_admin":
        return role == ROLE_HEAD_ADMIN

    return False


# ============================================================================
# PROFILE
# ============================================================================

DEFAULT_PROFILE_NICK = None

# Старое profile_tag больше не используется как источник правды.
DEFAULT_PROFILE_TAG = None


# ============================================================================
# PROFILE BUTTONS
# ============================================================================

PROFILE_BUTTON_TAGS = "profile:tags"

PROFILE_BUTTON_VENEREOLOGIST = "profile:venereologist"

PROFILE_BUTTON_ABORT = "profile:abort"


# ============================================================================
# LEADERBOARDS
# ============================================================================

TOP_DEFAULT_LIMIT = 10

TOP_MAX_LIMIT = 50

TOP_SIZE_COMMAND = "topsize"

TOP_BALANCE_COMMAND = "top"

TOP_XP_COMMAND = "topxp"


# ============================================================================
# GIVEAWAYS
# ============================================================================

"""
Giveaway может иметь:

    peanuts
    inventory_item
    external

external означает:
    приз не находится в базе бота;
    победитель определяется автоматически;
    выдача выполняется вручную организатором.
"""


GIVEAWAY_PRIZE_PEANUTS = "peanuts"

GIVEAWAY_PRIZE_ITEM = "item"

GIVEAWAY_PRIZE_EXTERNAL = "external"

GIVEAWAY_PRIZE_TYPES = {
    GIVEAWAY_PRIZE_PEANUTS,
    GIVEAWAY_PRIZE_ITEM,
    GIVEAWAY_PRIZE_EXTERNAL,
}


# ============================================================================
# GAMES
# ============================================================================

GAME_COINFLIP = "coinflip"
GAME_DICE = "dice"
GAME_SLOTS = "slots"
GAME_ROULETTE = "roulette"
GAME_FOOTBALL = "football"
GAME_BASKETBALL = "basketball"
GAME_TICTACTOE = "tictactoe"
GAME_BLACKJACK = "blackjack"
GAME_CRASH = "crash"


# PvP игры.
PVP_GAMES = {
    GAME_FOOTBALL,
    GAME_BASKETBALL,
    GAME_TICTACTOE,
}


# ============================================================================
# FOOTBALL
# ============================================================================

FOOTBALL_MIN_BET = 10

FOOTBALL_MULTIPLIER = 2.0


# ============================================================================
# BASKETBALL
# ============================================================================

BASKETBALL_MIN_BET = 10

BASKETBALL_MULTIPLIER = 2.0


# ============================================================================
# TICTACTOE
# ============================================================================

TICTACTOE_MIN_BET = 10

TICTACTOE_WIN_MULTIPLIER = 2.0

TICTACTOE_DRAW_REFUND = True


# ============================================================================
# СТАТИСТИКА
# ============================================================================

STAT_MESSAGE_XP = "message_xp"

STAT_GAME_WIN = "game_win"

STAT_GAME_LOSS = "game_loss"

STAT_GAME_DRAW = "game_draw"

STAT_RP = "rp"

STAT_ADULT_RP = "adult_rp"


# ============================================================================
# РЕГИСТРАЦИЯ НОВОГО ПОЛЬЗОВАТЕЛЯ
# ============================================================================

DEFAULT_LEVEL = 1

DEFAULT_XP = 0

DEFAULT_BALANCE = 0

DEFAULT_MESSAGES = 0

DEFAULT_GAMES_PLAYED = 0

DEFAULT_GAMES_WON = 0

DEFAULT_GAMES_LOST = 0

DEFAULT_TOTAL_WON = 0

DEFAULT_TOTAL_LOST = 0

DEFAULT_BATTLE_PASS_XP = 0

DEFAULT_BATTLE_PASS_LEVEL = 1

DEFAULT_BATTLE_PASS_SEASON = BATTLE_PASS_SEASON


# ============================================================================
# ЗНАЧЕНИЯ ДЛЯ РАЗМЕРА
# ============================================================================

MIN_PENIS_SIZE = 0.0


def clamp_penis_size(
    value: float,
) -> float:
    """
    Не позволяет размеру стать отрицательным.

    Округляем до сотых, чтобы не получить:

        1.9999999997
    """

    return round(
        max(
            MIN_PENIS_SIZE,
            value,
        ),
        2,
    )


# ============================================================================
# ПРОВЕРКИ
# ============================================================================


def is_valid_bet(
    amount: int,
) -> bool:
    """
    Проверяет допустимость ставки.
    """

    config = get_config()

    return (
        config.min_bet
        <= amount
        <= config.max_bet
    )


def is_staff_role(
    role: str | None,
) -> bool:
    """
    Проверяет наличие staff-роли.
    """

    return role in STAFF_ROLES


# ============================================================================
# ИНИЦИАЛИЗАЦИЯ ПРИЛОЖЕНИЯ
# ============================================================================


async def initialize_application() -> None:
    """
    Подготавливает окружение приложения.

    Создаёт необходимые каталоги
    и загружает конфигурацию.
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

    Пока внешних ресурсов здесь нет.
    """

    return None