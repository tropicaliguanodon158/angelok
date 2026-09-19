"""
Ezzzy Game Bot
==============
services.py — бизнес-логика приложения.

Здесь находятся:
    - экономика;
    - XP и уровни;
    - ежедневный бонус;
    - переводы;
    - мини-игры;
    - крестики-нолики;
    - RP;
    - профиль;
    - достижения;
    - модерация;
    - owner-команды.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html import escape
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core import (
    CURRENCY_SYMBOL,
    LEVEL_UNLOCKS,
    RP_ACTIONS,
    get_config,
    get_unlocked_features,
    level_from_xp,
    xp_for_level,
    xp_to_next_level,
)
from database import (
    Achievement,
    AsyncSessionLocal,
    ChatMember,
    EconomyTransaction,
    Game,
    ModerationAction,
    TicTacToeGame,
    User,
    UserAchievement,
    Warning,
    add_transaction,
    get_or_create_chat,
    get_or_create_member,
    get_or_create_user,
    get_top_by_balance,
    get_top_by_messages,
    get_top_by_xp,
    utcnow,
)


# ============================================================================
# RESULT OBJECTS
# ============================================================================


@dataclass
class ServiceResult:
    success: bool
    message: str
    changed: bool = False
    level_up_message: Optional[str] = None
    keyboard: Optional[InlineKeyboardMarkup] = None
    answer: Optional[str] = None
    show_alert: bool = False


# ============================================================================
# CONSTANTS
# ============================================================================


config = get_config()

MAX_PROFILE_NICK_LENGTH = 32
MAX_PROFILE_TAG_LENGTH = 32

RNG = random.SystemRandom()

GAME_FEATURES = {
    "coinflip": "coinflip",
    "dice": "dice",
    "slots": "slots",
    "roulette": "roulette",
    "football": "football",
    "basketball": "basketball",
    "tictactoe": "tictactoe",
    "blackjack": "blackjack",
    "crash": "crash",
}


# ============================================================================
# GENERAL HELPERS
# ============================================================================


def clean_name(
    user: Optional[User],
) -> str:
    """Красивое имя пользователя."""

    if user is None:
        return "Игрок"

    if user.username:
        return f"@{escape(user.username)}"

    return escape(
        user.first_name or "Игрок"
    )


def format_balance(
    amount: int,
) -> str:
    """Форматирование арахиса."""

    return f"{amount:,}".replace(",", " ")


def user_mention(
    user_id: int,
    name: str,
) -> str:
    """
    HTML mention без необходимости иметь username.
    """

    return f'<a href="tg://user?id={user_id}">{name}</a>'


async def get_member(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
) -> Optional[ChatMember]:
    """Получает профиль пользователя в группе."""

    result = await session.execute(
        select(ChatMember).where(
            ChatMember.chat_id == chat_id,
            ChatMember.user_id == user_id,
        )
    )

    return result.scalar_one_or_none()


async def ensure_member(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    username: Optional[str] = None,
    first_name: str = "Игрок",
    last_name: Optional[str] = None,
) -> ChatMember:
    """Гарантирует существование профиля."""

    await get_or_create_user(
        session=session,
        user_id=user_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
    )

    member = await get_or_create_member(
        session=session,
        chat_id=chat_id,
        user_id=user_id,
    )

    return member


def valid_bet(
    bet: int,
) -> Optional[str]:
    """Проверяет размер ставки."""

    if bet < config.min_bet:
        return (
            f"❌ Минимальная ставка — "
            f"<b>{format_balance(config.min_bet)}</b> 🥜."
        )

    if bet > config.max_bet:
        return (
            f"❌ Максимальная ставка — "
            f"<b>{format_balance(config.max_bet)}</b> 🥜."
        )

    return None


async def can_afford(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    amount: int,
) -> tuple[Optional[ChatMember], Optional[str]]:
    """Проверяет баланс."""

    member = await get_member(
        session,
        chat_id,
        user_id,
    )

    if member is None:
        member = await ensure_member(
            session,
            chat_id,
            user_id,
        )

    if member.balance < amount:
        return (
            member,
            (
                f"❌ Недостаточно арахиса.\n"
                f"Баланс: <b>{format_balance(member.balance)}</b> 🥜\n"
                f"Нужно: <b>{format_balance(amount)}</b> 🥜"
            ),
        )

    return member, None


async def change_balance(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    amount: int,
    transaction_type: str,
    description: Optional[str] = None,
) -> ChatMember:
    """Изменяет баланс и записывает операцию."""

    member = await get_member(
        session,
        chat_id,
        user_id,
    )

    if member is None:
        member = await ensure_member(
            session,
            chat_id,
            user_id,
        )

    new_balance = member.balance + amount

    if new_balance < 0:
        raise ValueError(
            "Баланс пользователя не может стать отрицательным."
        )

    member.balance = new_balance
    member.updated_at = utcnow()

    await add_transaction(
        session=session,
        chat_id=chat_id,
        user_id=user_id,
        amount=amount,
        balance_after=new_balance,
        transaction_type=transaction_type,
        description=description,
    )

    await session.flush()

    return member


# ============================================================================
# MESSAGE / XP
# ============================================================================


async def handle_message(
    session: AsyncSession,
    message: Message,
) -> ServiceResult:
    """
    Обрабатывает обычное сообщение пользователя.

    За каждое сообщение:
        - увеличивается счётчик;
        - начисляется XP;
        - арахис начисляется с cooldown;
        - проверяется новый уровень.
    """

    if not message.from_user:
        return ServiceResult(
            success=False,
            message="",
            changed=False,
        )

    user = await get_or_create_user(
        session=session,
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        is_bot=message.from_user.is_bot,
    )

    await get_or_create_chat(
        session=session,
        chat_id=message.chat.id,
        title=message.chat.title or "Telegram Chat",
        chat_type=message.chat.type,
    )

    member = await get_or_create_member(
        session=session,
        chat_id=message.chat.id,
        user_id=message.from_user.id,
    )

    old_level = member.level

    member.messages += 1
    member.xp += config.message_xp

    now = utcnow()

    reward_allowed = True

    if member.last_message_at is not None:
        elapsed = (
            now - member.last_message_at
        ).total_seconds()

        if elapsed < config.message_reward_cooldown:
            reward_allowed = False

    if reward_allowed and config.message_reward_max > 0:
        reward = RNG.randint(
            config.message_reward_min,
            config.message_reward_max,
        )

        member.balance += reward

        await add_transaction(
            session=session,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            amount=reward,
            balance_after=member.balance,
            transaction_type="message_reward",
            description="Награда за сообщение",
        )

        member.last_message_at = now

    new_level = level_from_xp(member.xp)

    if new_level > old_level:
        member.level = new_level

    member.updated_at = now

    await session.flush()

    level_up_message = None

    if new_level > old_level:
        unlocked = []

        for level in range(old_level + 1, new_level + 1):
            unlocked.extend(
                LEVEL_UNLOCKS.get(level, ())
            )

        unique_unlocks = list(
            dict.fromkeys(unlocked)
        )

        unlock_text = ""

        if unique_unlocks:
            unlock_text = (
                "\n\n🔓 <b>Открыто:</b> "
                + ", ".join(unique_unlocks)
            )

        level_up_message = (
            f"🎉 {user_mention(message.from_user.id, clean_name(user))}\n"
            f"Ты достиг <b>{new_level} уровня</b>! ⭐"
            f"{unlock_text}"
        )

    return ServiceResult(
        success=True,
        message="",
        changed=True,
        level_up_message=level_up_message,
    )


# ============================================================================
# PROFILE
# ============================================================================


async def format_profile(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
) -> str:
    """Формирует профиль."""

    member = await get_member(
        session,
        chat_id,
        user_id,
    )

    if member is None:
        member = await ensure_member(
            session,
            chat_id,
            user_id,
        )

    user = await session.get(
        User,
        user_id,
    )

    if user is None:
        return "❌ Пользователь не найден."

    name = (
        member.profile_nick
        if member.profile_nick
        else clean_name(user)
    )

    next_xp = xp_to_next_level(member.xp)
    current_level_xp = xp_for_level(member.level)
    next_level_xp = xp_for_level(member.level + 1)

    progress_total = max(
        1,
        next_level_xp - current_level_xp,
    )

    progress_current = max(
        0,
        member.xp - current_level_xp,
    )

    progress_percent = int(
        progress_current / progress_total * 100
    )

    bar_size = 10
    filled = int(
        progress_percent / 100 * bar_size
    )

    bar = (
        "🟩" * filled
        + "⬜" * (bar_size - filled)
    )

    tag = (
        f"\n🏷 Тег: <b>{escape(member.profile_tag)}</b>"
        if member.profile_tag
        else ""
    )

    return (
        f"👤 <b>{escape(name)}</b>\n"
        f"{tag}\n\n"
        f"⭐ Уровень: <b>{member.level}</b>\n"
        f"✨ XP: <b>{format_balance(member.xp)}</b>\n"
        f"{bar} {progress_percent}%\n"
        f"📈 До следующего уровня: "
        f"<b>{format_balance(next_xp)}</b> XP\n\n"
        f"🥜 Арахис: <b>{format_balance(member.balance)}</b>\n"
        f"💬 Сообщений: <b>{format_balance(member.messages)}</b>\n"
        f"🎮 Игр: <b>{format_balance(member.games_played)}</b>\n"
        f"🏆 Побед: <b>{format_balance(member.games_won)}</b>\n"
        f"💀 Поражений: <b>{format_balance(member.games_lost)}</b>"
    )


async def format_stats(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
) -> str:
    """Подробная статистика."""

    member = await get_member(
        session,
        chat_id,
        user_id,
    )

    if member is None:
        return "❌ Профиль ещё не создан."

    total_games = (
        member.games_won + member.games_lost
    )

    winrate = (
        member.games_won / total_games * 100
        if total_games
        else 0
    )

    return (
        "📊 <b>Твоя статистика</b>\n\n"
        f"💬 Сообщений: <b>{member.messages:,}</b>\n"
        f"⭐ XP: <b>{member.xp:,}</b>\n"
        f"🏅 Уровень: <b>{member.level}</b>\n"
        f"🥜 Баланс: <b>{member.balance:,}</b>\n\n"
        f"🎮 Игр: <b>{member.games_played:,}</b>\n"
        f"🏆 Побед: <b>{member.games_won:,}</b>\n"
        f"💀 Поражений: <b>{member.games_lost:,}</b>\n"
        f"📈 Винрейт: <b>{winrate:.1f}%</b>\n"
        f"💰 Выиграно: <b>{member.total_won:,}</b> 🥜\n"
        f"💸 Проиграно: <b>{member.total_lost:,}</b> 🥜"
    ).replace(",", " ")


async def balance_user(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
) -> int:
    """Возвращает баланс."""

    member = await get_member(
        session,
        chat_id,
        user_id,
    )

    return member.balance if member else 0


# ============================================================================
# DAILY BONUS
# ============================================================================


async def claim_daily_bonus(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
) -> ServiceResult:
    """Ежедневный бонус."""

    member = await get_member(
        session,
        chat_id,
        user_id,
    )

    if member is None:
        member = await ensure_member(
            session,
            chat_id,
            user_id,
        )

    now = utcnow()

    if member.last_bonus_at:
        elapsed = (
            now - member.last_bonus_at
        ).total_seconds()

        if elapsed < 86400:
            remaining = int(
                86400 - elapsed
            )

            hours = remaining // 3600
            minutes = (
                remaining % 3600
            ) // 60

            return ServiceResult(
                success=False,
                message=(
                    "⏳ Ты уже получил ежедневный бонус.\n"
                    f"Следующий будет через "
                    f"<b>{hours} ч. {minutes} мин.</b>"
                ),
            )

    amount = RNG.randint(
        config.daily_bonus_min,
        config.daily_bonus_max,
    )

    member.last_bonus_at = now

    await change_balance(
        session=session,
        chat_id=chat_id,
        user_id=user_id,
        amount=amount,
        transaction_type="daily_bonus",
        description="Ежедневный бонус",
    )

    return ServiceResult(
        success=True,
        changed=True,
        message=(
            "🎁 <b>Ежедневный бонус!</b>\n\n"
            f"Ты получил <b>+{format_balance(amount)}</b> 🥜"
        ),
    )


# ============================================================================
# LEADERBOARD
# ============================================================================


async def get_leaderboard(
    session: AsyncSession,
    chat_id: int,
) -> str:
    """Общий рейтинг."""

    by_balance = await get_top_by_balance(
        session,
        chat_id,
        10,
    )

    by_xp = await get_top_by_xp(
        session,
        chat_id,
        10,
    )

    by_messages = await get_top_by_messages(
        session,
        chat_id,
        10,
    )

    user_ids = {
        member.user_id
        for member in (
            by_balance
            + by_xp
            + by_messages
        )
    }

    users = {}

    if user_ids:
        result = await session.execute(
            select(User).where(
                User.id.in_(user_ids)
            )
        )

        users = {
            user.id: user
            for user in result.scalars().all()
        }

    def line(
        index: int,
        member: ChatMember,
        value: str,
    ) -> str:
        user = users.get(member.user_id)

        return (
            f"<b>{index}.</b> "
            f"{escape(member.profile_nick) if member.profile_nick else clean_name(user)} "
            f"— {value}"
        )

    balance_lines = [
        line(
            i,
            member,
            f"{format_balance(member.balance)} 🥜",
        )
        for i, member in enumerate(
            by_balance,
            start=1,
        )
    ]

    xp_lines = [
        line(
            i,
            member,
            f"{format_balance(member.xp)} XP",
        )
        for i, member in enumerate(
            by_xp,
            start=1,
        )
    ]

    message_lines = [
        line(
            i,
            member,
            f"{format_balance(member.messages)} 💬",
        )
        for i, member in enumerate(
            by_messages,
            start=1,
        )
    ]

    return (
        "🏆 <b>ТОП ИГРОКОВ</b>\n\n"
        "🥜 <b>По арахису</b>\n"
        + (
            "\n".join(balance_lines)
            if balance_lines
            else "Пока пусто."
        )
        + "\n\n⭐ <b>По XP</b>\n"
        + (
            "\n".join(xp_lines)
            if xp_lines
            else "Пока пусто."
        )
        + "\n\n💬 <b>По сообщениям</b>\n"
        + (
            "\n".join(message_lines)
            if message_lines
            else "Пока пусто."
        )
    )


# ============================================================================
# ECONOMY TRANSFER
# ============================================================================


async def transfer_money(
    session: AsyncSession,
    chat_id: int,
    sender_id: int,
    receiver_id: int,
    amount: int,
) -> ServiceResult:
    """Перевод арахиса."""

    if amount <= 0:
        return ServiceResult(
            False,
            "❌ Сумма должна быть положительной.",
        )

    if sender_id == receiver_id:
        return ServiceResult(
            False,
            "❌ Нельзя перевести арахис самому себе.",
        )

    sender, error = await can_afford(
        session,
        chat_id,
        sender_id,
        amount,
    )

    if error:
        return ServiceResult(
            False,
            error,
        )

    receiver = await get_member(
        session,
        chat_id,
        receiver_id,
    )

    if receiver is None:
        receiver = await ensure_member(
            session,
            chat_id,
            receiver_id,
        )

    sender_name = "Игрок"
    receiver_name = "Игрок"

    sender_user = await session.get(
        User,
        sender_id,
    )

    receiver_user = await session.get(
        User,
        receiver_id,
    )

    if sender_user:
        sender_name = clean_name(sender_user)

    if receiver_user:
        receiver_name = clean_name(receiver_user)

    await change_balance(
        session,
        chat_id,
        sender_id,
        -amount,
        "transfer_sent",
        f"Перевод пользователю {receiver_id}",
    )

    await change_balance(
        session,
        chat_id,
        receiver_id,
        amount,
        "transfer_received",
        f"Перевод от пользователя {sender_id}",
    )

    return ServiceResult(
        True,
        (
            "💸 <b>Перевод выполнен!</b>\n\n"
            f"{sender_name} → {receiver_name}\n"
            f"Сумма: <b>{format_balance(amount)}</b> 🥜"
        ),
        changed=True,
    )


# ============================================================================
# GAME COMMON
# ============================================================================


async def prepare_game(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    game_type: str,
    bet: int,
) -> tuple[Optional[ChatMember], Optional[ServiceResult]]:
    """Общая подготовка ставки."""

    error = valid_bet(bet)

    if error:
        return None, ServiceResult(
            False,
            error,
        )

    member, balance_error = await can_afford(
        session,
        chat_id,
        user_id,
        bet,
    )

    if balance_error:
        return member, ServiceResult(
            False,
            balance_error,
        )

    return member, None


async def finish_game(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    game_type: str,
    bet: int,
    result: str,
    multiplier: float,
    won: bool,
) -> int:
    """Фиксирует результат игры."""

    payout = (
        int(bet * multiplier)
        if won
        else 0
    )

    # Ставка списывается полностью.
    await change_balance(
        session,
        chat_id,
        user_id,
        -bet,
        "game_bet",
        f"Ставка: {game_type}",
    )

    if payout > 0:
        await change_balance(
            session,
            chat_id,
            user_id,
            payout,
            "game_payout",
            f"Выигрыш: {game_type}",
        )

    member = await get_member(
        session,
        chat_id,
        user_id,
    )

    if member:
        member.games_played += 1

        if won:
            member.games_won += 1
            member.total_won += max(
                0,
                payout - bet,
            )
        else:
            member.games_lost += 1
            member.total_lost += bet

    game = Game(
        chat_id=chat_id,
        user_id=user_id,
        game_type=game_type,
        bet=bet,
        result=result,
        multiplier=multiplier,
        payout=payout,
        won=won,
    )

    session.add(game)

    await session.flush()

    return payout


# ============================================================================
# COINFLIP
# ============================================================================


async def play_coinflip(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    bet: int,
) -> ServiceResult:
    """Монетка."""

    _, error = await prepare_game(
        session,
        chat_id,
        user_id,
        "coinflip",
        bet,
    )

    if error:
        return error

    result = RNG.choice(
        ["Орёл", "Решка"]
    )

    won = result == "Орёл"

    multiplier = 1.95 if won else 0

    payout = await finish_game(
        session,
        chat_id,
        user_id,
        "coinflip",
        bet,
        result,
        multiplier,
        won,
    )

    if won:
        text = (
            "🪙 <b>Орёл!</b>\n\n"
            f"🎉 Ты выиграл <b>{format_balance(payout - bet)}</b> 🥜"
        )
    else:
        text = (
            "🪙 <b>Решка!</b>\n\n"
            f"💀 Ты проиграл <b>{format_balance(bet)}</b> 🥜"
        )

    return ServiceResult(
        True,
        text,
        changed=True,
    )


# ============================================================================
# DICE
# ============================================================================


async def play_dice(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    bet: int,
) -> ServiceResult:
    """Кубики."""

    _, error = await prepare_game(
        session,
        chat_id,
        user_id,
        "dice",
        bet,
    )

    if error:
        return error

    first = RNG.randint(1, 6)
    second = RNG.randint(1, 6)

    total = first + second

    won = total >= 8

    multiplier = (
        1.8 if won else 0
    )

    payout = await finish_game(
        session,
        chat_id,
        user_id,
        "dice",
        bet,
        str(total),
        multiplier,
        won,
    )

    if won:
        text = (
            f"🎲 {first} + {second} = <b>{total}</b>\n\n"
            f"🏆 Выигрыш: <b>{format_balance(payout - bet)}</b> 🥜"
        )
    else:
        text = (
            f"🎲 {first} + {second} = <b>{total}</b>\n\n"
            f"💀 Проигрыш: <b>{format_balance(bet)}</b> 🥜"
        )

    return ServiceResult(
        True,
        text,
        changed=True,
    )


# ============================================================================
# SLOTS
# ============================================================================


async def play_slots(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    bet: int,
) -> ServiceResult:
    """Слоты."""

    _, error = await prepare_game(
        session,
        chat_id,
        user_id,
        "slots",
        bet,
    )

    if error:
        return error

    symbols = [
        "🍒",
        "🍋",
        "🍊",
        "🔔",
        "⭐",
        "💎",
        "7️⃣",
    ]

    result = [
        RNG.choice(symbols)
        for _ in range(3)
    ]

    if result[0] == result[1] == result[2]:
        if result[0] == "7️⃣":
            multiplier = 10.0
        elif result[0] == "💎":
            multiplier = 7.0
        else:
            multiplier = 5.0

        won = True

    elif (
        result[0] == result[1]
        or result[1] == result[2]
        or result[0] == result[2]
    ):
        multiplier = 2.0
        won = True

    else:
        multiplier = 0
        won = False

    payout = await finish_game(
        session,
        chat_id,
        user_id,
        "slots",
        bet,
        "".join(result),
        multiplier,
        won,
    )

    if won:
        text = (
            "🎰 <b>| "
            + " | ".join(result)
            + " |</b>\n\n"
            f"🎉 Выплата: <b>{format_balance(payout)}</b> 🥜"
        )
    else:
        text = (
            "🎰 <b>| "
            + " | ".join(result)
            + " |</b>\n\n"
            "💀 Не повезло."
        )

    return ServiceResult(
        True,
        text,
        changed=True,
    )


# ============================================================================
# ROULETTE
# ============================================================================


async def play_roulette(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    bet: int,
    choice: str,
) -> ServiceResult:
    """Рулетка."""

    _, error = await prepare_game(
        session,
        chat_id,
        user_id,
        "roulette",
        bet,
    )

    if error:
        return error

    choice = choice.lower()

    if choice not in {
        "red",
        "black",
        "green",
    }:
        return ServiceResult(
            False,
            "❌ Выбор: red, black или green.",
        )

    number = RNG.randint(
        0,
        36,
    )

    if number == 0:
        color = "green"
    elif number in {
        1, 3, 5, 7, 9, 12, 14, 16,
        18, 19, 21, 23, 25, 27, 30,
        32, 34, 36,
    }:
        color = "red"
    else:
        color = "black"

    won = color == choice

    multiplier = {
        "red": 1.95,
        "black": 1.95,
        "green": 14.0,
    }[choice] if won else 0

    payout = await finish_game(
        session,
        chat_id,
        user_id,
        "roulette",
        bet,
        f"{number}:{color}",
        multiplier,
        won,
    )

    color_emoji = {
        "red": "🔴",
        "black": "⚫",
        "green": "🟢",
    }[color]

    if won:
        text = (
            f"🎡 Выпало: <b>{number}</b> {color_emoji}\n\n"
            f"🎉 Выплата: <b>{format_balance(payout)}</b> 🥜"
        )
    else:
        text = (
            f"🎡 Выпало: <b>{number}</b> {color_emoji}\n\n"
            "💀 Проигрыш."
        )

    return ServiceResult(
        True,
        text,
        changed=True,
    )


# ============================================================================
# GUESS
# ============================================================================


async def play_guess(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    bet: int,
    number: int,
) -> ServiceResult:
    """Угадай число."""

    if number < 1 or number > 10:
        return ServiceResult(
            False,
            "❌ Число должно быть от 1 до 10.",
        )

    _, error = await prepare_game(
        session,
        chat_id,
        user_id,
        "guess",
        bet,
    )

    if error:
        return error

    generated = RNG.randint(
        1,
        10,
    )

    won = generated == number

    multiplier = 9.0 if won else 0

    payout = await finish_game(
        session,
        chat_id,
        user_id,
        "guess",
        bet,
        f"{number}:{generated}",
        multiplier,
        won,
    )

    if won:
        text = (
            f"🔢 Выпало число <b>{generated}</b>!\n\n"
            f"🎉 Ты выиграл <b>{format_balance(payout - bet)}</b> 🥜"
        )
    else:
        text = (
            f"🔢 Выпало число <b>{generated}</b>.\n\n"
            "💀 Не угадал."
        )

    return ServiceResult(
        True,
        text,
        changed=True,
    )


# ============================================================================
# CREATE GAME
# ============================================================================


async def create_game(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    game_type: str,
    bet: int,
) -> ServiceResult:
    """Универсальный вход для игр."""

    handlers = {
        "coinflip": play_coinflip,
        "dice": play_dice,
        "slots": play_slots,
    }

    handler = handlers.get(game_type)

    if handler is None:
        return ServiceResult(
            False,
            "❌ Эта игра пока запускается другим способом.",
        )

    return await handler(
        session,
        chat_id,
        user_id,
        bet,
    )


def get_game_list() -> list[str]:
    """Список доступных игр."""

    return [
        "coinflip",
        "dice",
        "slots",
        "roulette",
        "guess",
        "tictactoe",
        "football",
        "basketball",
        "blackjack",
        "crash",
    ]


# ============================================================================
# TIC TAC TOE
# ============================================================================


def ttt_keyboard(
    game: TicTacToeGame,
) -> InlineKeyboardMarkup:
    """Клавиатура крестиков-ноликов."""

    builder = InlineKeyboardBuilder()

    symbols = list(game.board)

    for position, symbol in enumerate(symbols):
        if symbol == "-":
            text = "⬜"
        elif symbol == "X":
            text = "❌"
        else:
            text = "⭕"

        builder.button(
            text=text,
            callback_data=(
                f"ttt:{game.id}:{position}"
            ),
        )

    builder.adjust(3)

    return builder.as_markup()


def ttt_winner(
    board: str,
) -> Optional[str]:
    """Определяет победителя."""

    wins = [
        (0, 1, 2),
        (3, 4, 5),
        (6, 7, 8),
        (0, 3, 6),
        (1, 4, 7),
        (2, 5, 8),
        (0, 4, 8),
        (2, 4, 6),
    ]

    for a, b, c in wins:
        if (
            board[a] != "-"
            and board[a] == board[b] == board[c]
        ):
            return board[a]

    if "-" not in board:
        return "draw"

    return None


async def start_tictactoe(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
) -> ServiceResult:
    """Создаёт игру."""

    existing = await session.execute(
        select(TicTacToeGame).where(
            TicTacToeGame.chat_id == chat_id,
            TicTacToeGame.status.in_(
                ["waiting", "playing"]
            ),
        )
    )

    games = list(existing.scalars().all())

    for game in games:
        if (
            game.player_x_id == user_id
            or game.player_o_id == user_id
        ):
            return ServiceResult(
                False,
                "❌ У тебя уже есть активная игра.",
            )

    game = TicTacToeGame(
        chat_id=chat_id,
        player_x_id=user_id,
        current_player_id=user_id,
        board="---------",
        status="waiting",
    )

    session.add(game)

    await session.flush()

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎮 Присоединиться",
                    callback_data=f"tttjoin:{game.id}",
                )
            ]
        ]
    )

    return ServiceResult(
        True,
        (
            "⭕❌ <b>Крестики-нолики</b>\n\n"
            "Игрок X создал игру.\n"
            "Нажми кнопку, чтобы присоединиться."
        ),
        changed=True,
        keyboard=keyboard,
    )


async def tictactoe_move(
    session: AsyncSession,
    game_id: int,
    user_id: int,
    position: int,
) -> ServiceResult:
    """Обрабатывает ход."""

    game = await session.get(
        TicTacToeGame,
        game_id,
    )

    if game is None:
        return ServiceResult(
            False,
            "❌ Игра не найдена.",
            answer="Игра не найдена.",
            show_alert=True,
        )

    if game.status != "playing":
        return ServiceResult(
            False,
            "❌ Игра уже завершена.",
            answer="Игра завершена.",
            show_alert=True,
        )

    if user_id != game.current_player_id:
        return ServiceResult(
            False,
            "⏳ Сейчас ход другого игрока.",
            answer="Сейчас ход другого игрока.",
            show_alert=True,
        )

    if position < 0 or position > 8:
        return ServiceResult(
            False,
            "❌ Некорректная клетка.",
            answer="Некорректная клетка.",
            show_alert=True,
        )

    board = list(game.board)

    if board[position] != "-":
        return ServiceResult(
            False,
            "❌ Эта клетка уже занята.",
            answer="Клетка занята.",
            show_alert=True,
        )

    symbol = (
        "X"
        if user_id == game.player_x_id
        else "O"
    )

    board[position] = symbol

    game.board = "".join(board)

    winner = ttt_winner(
        game.board
    )

    if winner:
        game.status = "finished"

        if winner == "draw":
            game.winner_id = None

            text = (
                "⭕❌ <b>Ничья!</b>\n\n"
                "Все клетки заняты."
            )

        else:
            winner_id = (
                game.player_x_id
                if winner == "X"
                else game.player_o_id
            )

            game.winner_id = winner_id

            text = (
                "⭕❌ <b>Игра окончена!</b>\n\n"
                f"Победил игрок "
                f"<a href=\"tg://user?id={winner_id}\">"
                f"победитель"
                f"</a> 🎉"
            )

        return ServiceResult(
            True,
            text,
            changed=True,
            keyboard=ttt_keyboard(game),
        )

    game.current_player_id = (
        game.player_o_id
        if user_id == game.player_x_id
        else game.player_x_id
    )

    current_symbol = (
        "❌"
        if game.current_player_id == game.player_x_id
        else "⭕"
    )

    text = (
        "⭕❌ <b>Крестики-нолики</b>\n\n"
        f"Ход: {current_symbol}"
    )

    return ServiceResult(
        True,
        text,
        changed=True,
        keyboard=ttt_keyboard(game),
    )


# ============================================================================
# RP
# ============================================================================


async def perform_rp(
    session: AsyncSession,
    chat_id: int,
    actor_id: int,
    action: str,
    target_id: Optional[int],
    target_name: Optional[str],
) -> ServiceResult:
    """Выполняет RP-действие."""

    normalized = action.lower()

    aliases = {
        "пожать": "пожать",
        "дать": "дать_пять",
        "пять": "дать_пять",
        "подзатыльник": "дать_подзатыльник",
        "тапок": "кинуть_тапок",
    }

    normalized = aliases.get(
        normalized,
        normalized,
    )

    action_data = RP_ACTIONS.get(
        normalized
    )

    if action_data is None:
        return ServiceResult(
            False,
            "❌ Неизвестное RP-действие.",
        )

    actor = await session.get(
        User,
        actor_id,
    )

    actor_name = clean_name(actor)

    if target_id is None:
        if target_name is None:
            return ServiceResult(
                False,
                "❌ Укажи пользователя или ответь на его сообщение.",
            )
    else:
        if target_id == actor_id:
            return ServiceResult(
                False,
                "😐 На себя это действие применить нельзя.",
            )

    if target_name is None:
        target = await session.get(
            User,
            target_id,
        )

        target_name = (
            clean_name(target)
            if target
            else "игрока"
        )

    emoji = action_data["emoji"]
    verb = action_data["verb"]

    if verb.endswith(" в"):
        text = (
            f"{emoji} {user_mention(actor_id, actor_name)} "
            f"<b>{verb}</b> {target_name}!"
        )
    else:
        text = (
            f"{emoji} {user_mention(actor_id, actor_name)} "
            f"<b>{verb}</b> {target_name}!"
        )

    return ServiceResult(
        True,
        text,
    )


# ============================================================================
# PROFILE NICK / TAG
# ============================================================================


async def set_profile_nick(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    nick: str,
) -> ServiceResult:
    """Изменяет локальный игровой ник."""

    nick = nick.strip()

    if not nick:
        return ServiceResult(
            False,
            "❌ Ник не может быть пустым.",
        )

    if len(nick) > MAX_PROFILE_NICK_LENGTH:
        return ServiceResult(
            False,
            f"❌ Максимальная длина ника — "
            f"{MAX_PROFILE_NICK_LENGTH} символа.",
        )

    if any(
        char in nick
        for char in "\n\r\t"
    ):
        return ServiceResult(
            False,
            "❌ В нике нельзя использовать переносы строк.",
        )

    member = await get_member(
        session,
        chat_id,
        user_id,
    )

    if member is None:
        member = await ensure_member(
            session,
            chat_id,
            user_id,
        )

    member.profile_nick = nick

    return ServiceResult(
        True,
        f"✏️ Твой игровой ник теперь: <b>{escape(nick)}</b>",
        changed=True,
    )


async def set_profile_tag(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    tag: str,
) -> ServiceResult:
    """Сохраняет локальный тег."""

    tag = tag.strip()

    if not tag:
        return ServiceResult(
            False,
            "❌ Тег не может быть пустым.",
        )

    if len(tag) > MAX_PROFILE_TAG_LENGTH:
        return ServiceResult(
            False,
            f"❌ Максимальная длина тега — "
            f"{MAX_PROFILE_TAG_LENGTH} символа.",
        )

    member = await get_member(
        session,
        chat_id,
        user_id,
    )

    if member is None:
        member = await ensure_member(
            session,
            chat_id,
            user_id,
        )

    member.profile_tag = tag

    return ServiceResult(
        True,
        (
            f"🏷 Твой тег сохранён: "
            f"<b>{escape(tag)}</b>"
        ),
        changed=True,
    )


# ============================================================================
# MODERATION HELPERS
# ============================================================================


async def check_admin(
    bot: Bot,
    chat_id: int,
    user_id: int,
) -> bool:
    """Проверяет администратора Telegram."""

    try:
        member = await bot.get_chat_member(
            chat_id,
            user_id,
        )

        return member.status in {
            "administrator",
            "creator",
        }

    except Exception:
        return False


async def log_moderation(
    session: AsyncSession,
    chat_id: int,
    target_user_id: int,
    moderator_id: int,
    action: str,
    reason: Optional[str] = None,
    duration: Optional[int] = None,
) -> None:
    """Записывает действие модерации."""

    session.add(
        ModerationAction(
            chat_id=chat_id,
            target_user_id=target_user_id,
            moderator_id=moderator_id,
            action=action,
            reason=reason,
            duration=duration,
        )
    )

    await session.flush()


async def check_moderation_permissions(
    bot: Bot,
    chat_id: int,
    moderator_id: int,
    target_user_id: int,
) -> Optional[ServiceResult]:
    """Проверяет права и защиту администрации."""

    if not await check_admin(
        bot,
        chat_id,
        moderator_id,
    ):
        return ServiceResult(
            False,
            "❌ Эта команда доступна только администраторам.",
        )

    try:
        target = await bot.get_chat_member(
            chat_id,
            target_user_id,
        )

        if target.status in {
            "administrator",
            "creator",
        }:
            return ServiceResult(
                False,
                "❌ Нельзя применять модерацию к администратору.",
            )

    except Exception:
        pass

    return None


# ============================================================================
# WARNINGS
# ============================================================================


async def add_warning(
    session: AsyncSession,
    chat_id: int,
    target_user_id: int,
    moderator_id: int,
    reason: str,
) -> ServiceResult:
    """Выдаёт предупреждение."""

    moderator_user = await session.get(
        User,
        moderator_id,
    )

    # Проверка Telegram admin выполняется handler/service через bot
    # в реальном действии. Здесь сохраняем запись.
    warning = Warning(
        chat_id=chat_id,
        user_id=target_user_id,
        moderator_id=moderator_id,
        reason=reason or None,
        active=True,
    )

    session.add(warning)

    await session.flush()

    result = await session.execute(
        select(Warning).where(
            Warning.chat_id == chat_id,
            Warning.user_id == target_user_id,
            Warning.active.is_(True),
        )
    )

    count = len(
        list(result.scalars().all())
    )

    return ServiceResult(
        True,
        (
            "⚠️ <b>Предупреждение выдано.</b>\n"
            f"Всего активных предупреждений: <b>{count}</b>"
            + (
                f"\nПричина: {escape(reason)}"
                if reason
                else ""
            )
        ),
        changed=True,
    )


async def remove_warning(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    moderator_id: int,
) -> ServiceResult:
    """Снимает последнее активное предупреждение."""

    result = await session.execute(
        select(Warning)
        .where(
            Warning.chat_id == chat_id,
            Warning.user_id == user_id,
            Warning.active.is_(True),
        )
        .order_by(Warning.created_at.desc())
    )

    warning = result.scalars().first()

    if warning is None:
        return ServiceResult(
            False,
            "❌ Активных предупреждений нет.",
        )

    warning.active = False

    await log_moderation(
        session,
        chat_id,
        user_id,
        moderator_id,
        "unwarn",
    )

    return ServiceResult(
        True,
        "✅ Последнее предупреждение снято.",
        changed=True,
    )


async def get_warnings(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
) -> str:
    """Список предупреждений."""

    result = await session.execute(
        select(Warning)
        .where(
            Warning.chat_id == chat_id,
            Warning.user_id == user_id,
            Warning.active.is_(True),
        )
        .order_by(Warning.created_at.desc())
    )

    warnings = list(
        result.scalars().all()
    )

    if not warnings:
        return "✅ Активных предупреждений нет."

    lines = [
        f"⚠️ <b>Активные предупреждения: {len(warnings)}</b>\n"
    ]

    for index, warning in enumerate(
        warnings,
        start=1,
    ):
        reason = (
            escape(warning.reason)
            if warning.reason
            else "Причина не указана"
        )

        lines.append(
            f"{index}. {reason}"
        )

    return "\n".join(lines)


# ============================================================================
# MUTE
# ============================================================================


async def moderate_mute(
    session: AsyncSession,
    bot: Bot,
    chat_id: int,
    target_user_id: int,
    moderator_id: int,
    duration_minutes: int,
) -> ServiceResult:
    """Выдаёт mute."""

    permission_error = await check_moderation_permissions(
        bot,
        chat_id,
        moderator_id,
        target_user_id,
    )

    if permission_error:
        return permission_error

    if duration_minutes < 1:
        return ServiceResult(
            False,
            "❌ Длительность должна быть больше нуля.",
        )

    if duration_minutes > 525600:
        return ServiceResult(
            False,
            "❌ Максимальный срок — 365 дней.",
        )

    until_date = datetime.now(
        timezone.utc
    ) + timedelta(
        minutes=duration_minutes
    )

    try:
        from aiogram.types import ChatPermissions

        await bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=target_user_id,
            permissions=ChatPermissions(
                can_send_messages=False,
                can_send_audios=False,
                can_send_documents=False,
                can_send_photos=False,
                can_send_videos=False,
                can_send_video_notes=False,
                can_send_voice_notes=False,
                can_send_polls=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False,
            ),
            until_date=until_date,
        )

    except TelegramBadRequest as exc:
        return ServiceResult(
            False,
            f"❌ Telegram не позволил выдать мут: {escape(str(exc))}",
        )

    except TelegramForbiddenError:
        return ServiceResult(
            False,
            "❌ У бота недостаточно прав для выдачи мута.",
        )

    await log_moderation(
        session,
        chat_id,
        target_user_id,
        moderator_id,
        "mute",
        duration=duration_minutes,
    )

    return ServiceResult(
        True,
        (
            "🔇 <b>Пользователь получил мут.</b>\n"
            f"⏱ Срок: <b>{duration_minutes} мин.</b>"
        ),
        changed=True,
    )


async def moderate_unmute(
    session: AsyncSession,
    bot: Bot,
    chat_id: int,
    target_user_id: int,
    moderator_id: int,
) -> ServiceResult:
    """Снимает мут."""

    permission_error = await check_moderation_permissions(
        bot,
        chat_id,
        moderator_id,
        target_user_id,
    )

    if permission_error:
        return permission_error

    try:
        from aiogram.types import ChatPermissions

        await bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=target_user_id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_audios=True,
                can_send_documents=True,
                can_send_photos=True,
                can_send_videos=True,
                can_send_video_notes=True,
                can_send_voice_notes=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
            ),
        )

    except TelegramBadRequest as exc:
        return ServiceResult(
            False,
            f"❌ Telegram отклонил действие: {escape(str(exc))}",
        )

    except TelegramForbiddenError:
        return ServiceResult(
            False,
            "❌ У бота недостаточно прав.",
        )

    await log_moderation(
        session,
        chat_id,
        target_user_id,
        moderator_id,
        "unmute",
    )

    return ServiceResult(
        True,
        "🔊 Мут снят.",
        changed=True,
    )


# ============================================================================
# BAN
# ============================================================================


async def moderate_ban(
    session: AsyncSession,
    bot: Bot,
    chat_id: int,
    target_user_id: int,
    moderator_id: int,
    reason: str,
) -> ServiceResult:
    """Бан."""

    permission_error = await check_moderation_permissions(
        bot,
        chat_id,
        moderator_id,
        target_user_id,
    )

    if permission_error:
        return permission_error

    try:
        await bot.ban_chat_member(
            chat_id=chat_id,
            user_id=target_user_id,
        )

    except TelegramBadRequest as exc:
        return ServiceResult(
            False,
            f"❌ Telegram отклонил бан: {escape(str(exc))}",
        )

    except TelegramForbiddenError:
        return ServiceResult(
            False,
            "❌ У бота недостаточно прав для бана.",
        )

    await log_moderation(
        session,
        chat_id,
        target_user_id,
        moderator_id,
        "ban",
        reason=reason or None,
    )

    return ServiceResult(
        True,
        (
            "🔨 <b>Пользователь заблокирован.</b>"
            + (
                f"\nПричина: {escape(reason)}"
                if reason
                else ""
            )
        ),
        changed=True,
    )


async def moderate_unban(
    session: AsyncSession,
    bot: Bot,
    chat_id: int,
    target_user_id: int,
    moderator_id: int,
) -> ServiceResult:
    """Разбан."""

    if not await check_admin(
        bot,
        chat_id,
        moderator_id,
    ):
        return ServiceResult(
            False,
            "❌ Только администратор может использовать эту команду.",
        )

    try:
        await bot.unban_chat_member(
            chat_id=chat_id,
            user_id=target_user_id,
            only_if_banned=True,
        )

    except TelegramBadRequest as exc:
        return ServiceResult(
            False,
            f"❌ Telegram отклонил действие: {escape(str(exc))}",
        )

    except TelegramForbiddenError:
        return ServiceResult(
            False,
            "❌ У бота недостаточно прав.",
        )

    await log_moderation(
        session,
        chat_id,
        target_user_id,
        moderator_id,
        "unban",
    )

    return ServiceResult(
        True,
        "✅ Пользователь разблокирован.",
        changed=True,
    )


# ============================================================================
# KICK
# ============================================================================


async def moderate_kick(
    session: AsyncSession,
    bot: Bot,
    chat_id: int,
    target_user_id: int,
    moderator_id: int,
    reason: str,
) -> ServiceResult:
    """Кик."""

    permission_error = await check_moderation_permissions(
        bot,
        chat_id,
        moderator_id,
        target_user_id,
    )

    if permission_error:
        return permission_error

    try:
        await bot.ban_chat_member(
            chat_id=chat_id,
            user_id=target_user_id,
        )

        await bot.unban_chat_member(
            chat_id=chat_id,
            user_id=target_user_id,
            only_if_banned=True,
        )

    except TelegramBadRequest as exc:
        return ServiceResult(
            False,
            f"❌ Telegram отклонил действие: {escape(str(exc))}",
        )

    except TelegramForbiddenError:
        return ServiceResult(
            False,
            "❌ У бота недостаточно прав.",
        )

    await log_moderation(
        session,
        chat_id,
        target_user_id,
        moderator_id,
        "kick",
        reason=reason or None,
    )

    return ServiceResult(
        True,
        (
            "👢 <b>Пользователь удалён из группы.</b>"
            + (
                f"\nПричина: {escape(reason)}"
                if reason
                else ""
            )
        ),
        changed=True,
    )


# ============================================================================
# PURGE
# ============================================================================


async def purge_messages(
    bot: Bot,
    chat_id: int,
    moderator_id: int,
    count: int,
) -> ServiceResult:
    """Удаляет сообщения."""

    if not await check_admin(
        bot,
        chat_id,
        moderator_id,
    ):
        return ServiceResult(
            False,
            "❌ Только администратор может использовать purge.",
        )

    return ServiceResult(
        True,
        (
            "🧹 Telegram не позволяет боту удалить "
            "произвольный диапазон сообщений только "
            "по количеству без знания их message_id.\n\n"
            "Используй /purge ответом на последнее сообщение, "
            "если нужна точечная очистка."
        ),
    )


# ============================================================================
# OWNER
# ============================================================================


async def is_owner(
    user_id: int,
) -> bool:
    """Проверка владельца."""

    return (
        config.owner_id != 0
        and user_id == config.owner_id
    )


async def admin_give_money(
    session: AsyncSession,
    owner_id: int,
    chat_id: int,
    target_user_id: int,
    amount: int,
) -> ServiceResult:
    """Выдача арахиса владельцем."""

    if not await is_owner(owner_id):
        return ServiceResult(
            False,
            "❌ Только владелец бота может использовать эту команду.",
        )

    if amount <= 0:
        return ServiceResult(
            False,
            "❌ Сумма должна быть положительной.",
        )

    await ensure_member(
        session,
        chat_id,
        target_user_id,
    )

    await change_balance(
        session,
        chat_id,
        target_user_id,
        amount,
        "admin_give",
        f"Выдано владельцем {owner_id}",
    )

    return ServiceResult(
        True,
        (
            "💰 Выдано: "
            f"<b>+{format_balance(amount)}</b> 🥜"
        ),
        changed=True,
    )


async def admin_take_money(
    session: AsyncSession,
    owner_id: int,
    chat_id: int,
    target_user_id: int,
    amount: int,
) -> ServiceResult:
    """Списание арахиса владельцем."""

    if not await is_owner(owner_id):
        return ServiceResult(
            False,
            "❌ Только владелец бота может использовать эту команду.",
        )

    if amount <= 0:
        return ServiceResult(
            False,
            "❌ Сумма должна быть положительной.",
        )

    member = await get_member(
        session,
        chat_id,
        target_user_id,
    )

    if member is None:
        return ServiceResult(
            False,
            "❌ Пользователь ещё не зарегистрирован.",
        )

    if member.balance < amount:
        return ServiceResult(
            False,
            "❌ У пользователя недостаточно арахиса.",
        )

    await change_balance(
        session,
        chat_id,
        target_user_id,
        -amount,
        "admin_take",
        f"Списано владельцем {owner_id}",
    )

    return ServiceResult(
        True,
        (
            "💸 Списано: "
            f"<b>{format_balance(amount)}</b> 🥜"
        ),
        changed=True,
    )


async def admin_set_balance(
    session: AsyncSession,
    owner_id: int,
    chat_id: int,
    target_user_id: int,
    amount: int,
) -> ServiceResult:
    """Устанавливает баланс."""

    if not await is_owner(owner_id):
        return ServiceResult(
            False,
            "❌ Только владелец бота.",
        )

    if amount < 0:
        return ServiceResult(
            False,
            "❌ Баланс не может быть отрицательным.",
        )

    member = await get_member(
        session,
        chat_id,
        target_user_id,
    )

    if member is None:
        member = await ensure_member(
            session,
            chat_id,
            target_user_id,
        )

    difference = amount - member.balance

    member.balance = amount

    await add_transaction(
        session,
        chat_id,
        target_user_id,
        difference,
        amount,
        "admin_set_balance",
        f"Установлено владельцем {owner_id}",
    )

    return ServiceResult(
        True,
        (
            "🥜 Баланс установлен: "
            f"<b>{format_balance(amount)}</b>"
        ),
        changed=True,
    )


async def admin_set_level(
    session: AsyncSession,
    owner_id: int,
    chat_id: int,
    target_user_id: int,
    level: int,
) -> ServiceResult:
    """Устанавливает уровень."""

    if not await is_owner(owner_id):
        return ServiceResult(
            False,
            "❌ Только владелец бота.",
        )

    if level < 1 or level > 1000:
        return ServiceResult(
            False,
            "❌ Уровень должен быть от 1 до 1000.",
        )

    member = await get_member(
        session,
        chat_id,
        target_user_id,
    )

    if member is None:
        member = await ensure_member(
            session,
            chat_id,
            target_user_id,
        )

    member.level = level
    member.xp = xp_for_level(level)

    return ServiceResult(
        True,
        (
            f"⭐ Уровень установлен: "
            f"<b>{level}</b>"
        ),
        changed=True,
    )