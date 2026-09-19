"""
Ezzzy Game Bot
==============

services.py — бизнес-логика приложения.

Основные подсистемы:

    - экономика;
    - XP / уровни;
    - Battle Pass;
    - профили;
    - теги;
    - рейтинги;
    - ежедневный бонус;
    - переводы;
    - мини-игры;
    - крестики-нолики;
    - football / basketball;
    - RP;
    - размер;
    - rob;
    - болезнь;
    - беременность / ребёнок;
    - инвентарь;
    - кейсы;
    - модерация;
    - staff roles;
    - owner-команды.

ВАЖНО:

Telegram handlers должны заниматься Telegram-взаимодействием,
а эта таблица — бизнес-логикой и изменением состояния БД.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html import escape
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
)
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core import (
    ADULT_RP_COST,
    CURRENCY_SYMBOL,
    LEVEL_UNLOCKS,
    NORMAL_RP_COST,
    RP_ACTIONS,
    get_config,
    level_from_xp,
    xp_for_level,
    xp_to_next_level,
)

from database import (
    Achievement,
    AsyncSessionLocal,
    BattlePassRewardClaim,
    ChatMember,
    EconomyTransaction,
    Game,
    Giveaway,
    GiveawayParticipant,
    InventoryItem,
    ModPermission,
    ModerationAction,
    StaffMember,
    Tag,
    TicTacToeGame,
    User,
    UserAchievement,
    UserItem,
    UserTag,
    Warning,
    add_transaction,
    get_inventory_item,
    get_or_create_chat,
    get_or_create_member,
    get_or_create_user,
    get_tag_by_code,
    get_top_by_balance,
    get_top_by_messages,
    get_top_by_penis_size,
    get_top_by_xp,
    get_user_items,
    get_user_tags,
    utcnow,
)


# ============================================================================
# RESULT
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

RNG = random.SystemRandom()

MAX_PROFILE_NICK_LENGTH = 32

STAFF_OWNER = "owner"
STAFF_HEAD_ADMIN = "head_admin"
STAFF_ADMIN = "admin"
STAFF_MODERATOR = "moderator"

STAFF_POWER = {
    STAFF_OWNER: 40,
    STAFF_HEAD_ADMIN: 30,
    STAFF_ADMIN: 20,
    STAFF_MODERATOR: 10,
}

PERMISSION_STAFF = "staff"
PERMISSION_ADMIN = "admin"
PERMISSION_HEAD_ADMIN = "head_admin"

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

BP_XP_PER_LEVEL = 100
BP_MAX_LEVEL = 30

SIZE_LEVEL_REWARD = 0.10

ADULT_RP_COOLDOWN = 15 * 60
MASTURBATION_COOLDOWN = 6 * 60 * 60
ROB_COOLDOWN = 24 * 60 * 60

DISEASE_TICK_INTERVAL = 60 * 60
DISEASE_SIZE_LOSS = 0.5
DISEASE_MEDICINE_COST = 500
VENEREOLOGIST_COST = 5000

CHILD_DURATION = 18 * 60 * 60
CHILD_SUPPORT_COST = 10_000
ABORT_COST = 30_000

NORMAL_RP_COST_VALUE = 10
ADULT_RP_COST_VALUE = 50


# ============================================================================
# GENERAL HELPERS
# ============================================================================


def clean_name(user: Optional[User]) -> str:
    if user is None:
        return "Игрок"

    if user.username:
        return f"@{escape(user.username)}"

    return escape(user.first_name or "Игрок")


def format_balance(amount: int) -> str:
    return f"{amount:,}".replace(",", " ")


def user_mention(
    user_id: int,
    name: str,
) -> str:
    return f'<a href="tg://user?id={user_id}">{name}</a>'


def now_utc() -> datetime:
    return utcnow()


async def get_member(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
) -> Optional[ChatMember]:
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
    is_bot: bool = False,
) -> ChatMember:

    await get_or_create_user(
        session=session,
        user_id=user_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
        is_bot=is_bot,
    )

    member = await get_or_create_member(
        session=session,
        chat_id=chat_id,
        user_id=user_id,
    )

    return member


def valid_bet(bet: int) -> Optional[str]:
    if bet < config.min_bet:
        return (
            "❌ Минимальная ставка — "
            f"<b>{format_balance(config.min_bet)}</b> 🥜."
        )

    if bet > config.max_bet:
        return (
            "❌ Максимальная ставка — "
            f"<b>{format_balance(config.max_bet)}</b> 🥜."
        )

    return None


async def can_afford(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    amount: int,
) -> tuple[Optional[ChatMember], Optional[str]]:

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
                "❌ Недостаточно арахиса.\n"
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
# TARGET RESOLUTION
# ============================================================================


async def resolve_target(
    session: AsyncSession,
    chat_id: int,
    target_user_id: Optional[int] = None,
    target_username: Optional[str] = None,
    fallback_user_id: Optional[int] = None,
) -> Optional[User]:

    if target_user_id is not None:
        return await session.get(
            User,
            target_user_id,
        )

    if target_username:
        username = target_username.lstrip("@").lower()

        result = await session.execute(
            select(User).where(
                User.username.ilike(username)
            )
        )

        user = result.scalar_one_or_none()

        if user:
            return user

    if fallback_user_id is not None:
        return await session.get(
            User,
            fallback_user_id,
        )

    return None


# ============================================================================
# MESSAGE / XP / BATTLE PASS
# ============================================================================


async def _process_battle_pass(
    session: AsyncSession,
    member: ChatMember,
) -> list[str]:

    old_level = member.battle_pass_level

    member.battle_pass_xp += 1

    new_level = min(
        BP_MAX_LEVEL,
        (member.battle_pass_xp // BP_XP_PER_LEVEL) + 1,
    )

    if new_level <= old_level:
        return []

    member.battle_pass_level = new_level

    rewards: list[str] = []

    # Награды берутся из core.BATTLE_PASS_REWARDS,
    # если такая структура присутствует.
    try:
        from core import BATTLE_PASS_REWARDS
    except ImportError:
        BATTLE_PASS_REWARDS = {}

    for level in range(
        old_level + 1,
        new_level + 1,
    ):
        reward = BATTLE_PASS_REWARDS.get(level)

        if reward is None:
            continue

        reward_code = getattr(
            reward,
            "code",
            None,
        ) or getattr(
            reward,
            "reward_code",
            None,
        )

        if not reward_code:
            reward_code = str(reward)

        existing = await session.execute(
            select(BattlePassRewardClaim).where(
                BattlePassRewardClaim.chat_id == member.chat_id,
                BattlePassRewardClaim.user_id == member.user_id,
                BattlePassRewardClaim.season == member.battle_pass_season,
                BattlePassRewardClaim.level == level,
            )
        )

        if existing.scalar_one_or_none():
            continue

        session.add(
            BattlePassRewardClaim(
                chat_id=member.chat_id,
                user_id=member.user_id,
                season=member.battle_pass_season,
                level=level,
                reward_code=str(reward_code),
            )
        )

        rewards.append(
            f"уровень {level}: {escape(str(reward_code))}"
        )

    return rewards


async def handle_message(
    session: AsyncSession,
    message: Message,
) -> ServiceResult:

    if not message.from_user:
        return ServiceResult(
            success=False,
            message="",
        )

    if message.from_user.is_bot:
        return ServiceResult(
            success=False,
            message="",
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

    now = utcnow()

    old_level = member.level

    # ------------------------------------------------------------------------
    # MESSAGE XP
    # ------------------------------------------------------------------------

    member.messages += 1

    # 1 сообщение = +1 XP.
    # Никакого cooldown.
    member.xp += config.message_xp

    new_level = level_from_xp(
        member.xp
    )

    if new_level > old_level:
        member.level = new_level

    # ------------------------------------------------------------------------
    # BATTLE PASS
    # ------------------------------------------------------------------------

    # 1 сообщение = +1 BP XP.
    # Также без cooldown.
    bp_rewards = await _process_battle_pass(
        session,
        member,
    )

    # ------------------------------------------------------------------------
    # MESSAGE REWARD
    # ------------------------------------------------------------------------

    reward_allowed = True

    if member.last_message_at is not None:
        elapsed = (
            now - member.last_message_at
        ).total_seconds()

        if elapsed < config.message_reward_cooldown:
            reward_allowed = False

    if (
        reward_allowed
        and config.message_reward_max > 0
    ):
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

    # ------------------------------------------------------------------------
    # LEVEL SIZE
    # ------------------------------------------------------------------------

    level_up_message = None

    if new_level > old_level:

        levels_gained = new_level - old_level

        member.penis_size = round(
            max(
                0.0,
                member.penis_size
                + SIZE_LEVEL_REWARD * levels_gained,
            ),
            2,
        )

        unlocked: list[str] = []

        for level in range(
            old_level + 1,
            new_level + 1,
        ):
            unlocked.extend(
                LEVEL_UNLOCKS.get(
                    level,
                    (),
                )
            )

        unique_unlocks = list(
            dict.fromkeys(unlocked)
        )

        unlock_text = ""

        if unique_unlocks:
            unlock_text = (
                "\n\n🔓 <b>Открыто:</b>\n"
                + "\n".join(
                    f"• {escape(str(item))}"
                    for item in unique_unlocks
                )
            )

        level_up_message = (
            f"🎉 {user_mention("
                message.from_user.id,
                clean_name(user),
            )}\n"
            f"Ты достиг <b>{new_level} уровня</b>! ⭐\n"
            f"📏 Размер: <b>{member.penis_size:.2f} см</b>"
            f"{unlock_text}"
        )

    # ------------------------------------------------------------------------
    # BP MESSAGE
    # ------------------------------------------------------------------------

    if bp_rewards:
        bp_text = (
            "\n\n🎫 <b>Battle Pass</b>\n"
            f"Уровень: <b>{member.battle_pass_level}</b>"
        )

        if member.battle_pass_level >= BP_MAX_LEVEL:
            bp_text += (
                "\n🏆 <b>ЖИВАЯ ЛЕГЕНДА</b>"
            )

        if level_up_message:
            level_up_message += bp_text
        else:
            level_up_message = (
                f"🎫 {user_mention("
                    message.from_user.id,
                    clean_name(user),
                )}"
                f"{bp_text}"
            )

    member.updated_at = now

    await session.flush()

    return ServiceResult(
        success=True,
        message="",
        changed=True,
        level_up_message=level_up_message,
    )


# ============================================================================
# PROFILE
# ============================================================================


async def _selected_tag(
    session: AsyncSession,
    member: ChatMember,
) -> Optional[Tag]:

    if member.selected_tag_id is None:
        return None

    return await session.get(
        Tag,
        member.selected_tag_id,
    )


async def format_profile(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
) -> str:

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

    current_xp = xp_for_level(
        member.level
    )

    next_xp = xp_for_level(
        member.level + 1
    )

    progress_total = max(
        1,
        next_xp - current_xp,
    )

    progress_current = max(
        0,
        member.xp - current_xp,
    )

    progress_percent = min(
        100,
        int(
            progress_current
            / progress_total
            * 100
        ),
    )

    filled = int(
        progress_percent / 100 * 10
    )

    bar = (
        "🟩" * filled
        + "⬜" * (10 - filled)
    )

    tag = await _selected_tag(
        session,
        member,
    )

    tag_text = (
        f"\n🏷 Тег: <b>{escape(tag.name)}</b>"
        if tag
        else ""
    )

    disease_text = (
        "\n🦠 Болезнь: <b>есть</b>"
        if member.has_disease
        else ""
    )

    child_text = (
        "\n👶 Ребёнок: <b>есть</b>"
        if member.has_child
        else ""
    )

    return (
        f"👤 <b>{escape(name)}</b>\n"
        f"{tag_text}\n\n"
        f"⭐ Уровень: <b>{member.level}</b>\n"
        f"✨ XP: <b>{format_balance(member.xp)}</b>\n"
        f"{bar} {progress_percent}%\n"
        f"📈 До следующего уровня: "
        f"<b>{format_balance(xp_to_next_level(member.xp))}</b> XP\n\n"
        f"🎫 Battle Pass: "
        f"<b>{member.battle_pass_level}/{BP_MAX_LEVEL}</b>\n"
        f"🎫 BP XP: <b>{member.battle_pass_xp}</b>\n\n"
        f"🥜 Арахис: <b>{format_balance(member.balance)}</b>\n"
        f"📏 Размер: <b>{member.penis_size:.2f} см</b>\n"
        f"💬 Сообщений: <b>{format_balance(member.messages)}</b>\n"
        f"🎮 Игр: <b>{format_balance(member.games_played)}</b>\n"
        f"🏆 Побед: <b>{format_balance(member.games_won)}</b>\n"
        f"💀 Поражений: <b>{format_balance(member.games_lost)}</b>"
        f"{disease_text}"
        f"{child_text}"
    )


async def format_stats(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
) -> str:

    member = await get_member(
        session,
        chat_id,
        user_id,
    )

    if member is None:
        return "❌ Профиль ещё не создан."

    total_games = (
        member.games_won
        + member.games_lost
    )

    winrate = (
        member.games_won
        / total_games
        * 100
        if total_games
        else 0
    )

    return (
        "📊 <b>Твоя статистика</b>\n\n"
        f"💬 Сообщений: <b>{format_balance(member.messages)}</b>\n"
        f"⭐ XP: <b>{format_balance(member.xp)}</b>\n"
        f"🏅 Уровень: <b>{member.level}</b>\n"
        f"🎫 BP: <b>{member.battle_pass_level}</b>\n"
        f"🥜 Баланс: <b>{format_balance(member.balance)}</b>\n"
        f"📏 Размер: <b>{member.penis_size:.2f} см</b>\n\n"
        f"🎮 Игр: <b>{format_balance(member.games_played)}</b>\n"
        f"🏆 Побед: <b>{format_balance(member.games_won)}</b>\n"
        f"💀 Поражений: <b>{format_balance(member.games_lost)}</b>\n"
        f"📈 Винрейт: <b>{winrate:.1f}%</b>\n"
        f"💰 Выиграно: <b>{format_balance(member.total_won)}</b> 🥜\n"
        f"💸 Проиграно: <b>{format_balance(member.total_lost)}</b> 🥜"
    )


async def balance_user(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
) -> int:

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
                False,
                (
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
        True,
        (
            "🎁 <b>Ежедневный бонус!</b>\n\n"
            f"Ты получил <b>+{format_balance(amount)}</b> 🥜"
        ),
        changed=True,
    )


# ============================================================================
# LEADERBOARD
# ============================================================================


async def get_leaderboard(
    session: AsyncSession,
    chat_id: int,
) -> str:

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

    by_size = await get_top_by_penis_size(
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
            + by_size
        )
    }

    users: dict[int, User] = {}

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

        user = users.get(
            member.user_id
        )

        name = (
            escape(member.profile_nick)
            if member.profile_nick
            else clean_name(user)
        )

        return (
            f"<b>{index}.</b> "
            f"{name} — {value}"
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

    size_lines = [
        line(
            i,
            member,
            f"{member.penis_size:.2f} см 📏",
        )
        for i, member in enumerate(
            by_size,
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
        + "\n\n📏 <b>По размеру</b>\n"
        + (
            "\n".join(size_lines)
            if size_lines
            else "Пока пусто."
        )
    )


# ============================================================================
# TRANSFER
# ============================================================================


async def transfer_money(
    session: AsyncSession,
    chat_id: int,
    sender_id: int,
    receiver_id: int,
    amount: int,
) -> ServiceResult:

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

    sender_user = await session.get(
        User,
        sender_id,
    )

    receiver_user = await session.get(
        User,
        receiver_id,
    )

    sender_name = clean_name(
        sender_user
    )

    receiver_name = clean_name(
        receiver_user
    )

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
# GAMES COMMON
# ============================================================================


def game_unlocked(
    member: ChatMember,
    game_type: str,
) -> bool:

    required_level = 1

    for level, features in LEVEL_UNLOCKS.items():
        if game_type in features:
            required_level = min(
                required_level,
                level,
            )

    # Более надёжный поиск по таблице unlocks.
    found_level = None

    for level, features in LEVEL_UNLOCKS.items():
        if game_type in features:
            found_level = level
            break

    if found_level is None:
        return True

    return member.level >= found_level


async def prepare_game(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    game_type: str,
    bet: int,
) -> tuple[
    Optional[ChatMember],
    Optional[ServiceResult],
]:

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

    if member is not None:
        required_level = None

        for level, features in LEVEL_UNLOCKS.items():
            if game_type in features:
                required_level = level
                break

        if (
            required_level is not None
            and member.level < required_level
        ):
            return (
                member,
                ServiceResult(
                    False,
                    (
                        f"🔒 Игра откроется на "
                        f"<b>{required_level} уровне</b>.\n"
                        f"Твой уровень: <b>{member.level}</b>."
                    ),
                ),
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

    payout = (
        int(
            bet * multiplier
        )
        if won
        else 0
    )

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

    session.add(
        Game(
            chat_id=chat_id,
            user_id=user_id,
            game_type=game_type,
            bet=bet,
            result=result,
            multiplier=multiplier,
            payout=payout,
            won=won,
            status="finished",
        )
    )

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
            f"🎉 Ты выиграл "
            f"<b>{format_balance(payout - bet)}</b> 🥜"
        )
    else:
        text = (
            "🪙 <b>Решка!</b>\n\n"
            f"💀 Ты проиграл "
            f"<b>{format_balance(bet)}</b> 🥜"
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

    multiplier = 1.8 if won else 0

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
            f"🎲 {first} + {second} = "
            f"<b>{total}</b>\n\n"
            f"🏆 Выигрыш: "
            f"<b>{format_balance(payout - bet)}</b> 🥜"
        )
    else:
        text = (
            f"🎲 {first} + {second} = "
            f"<b>{total}</b>\n\n"
            f"💀 Проигрыш: "
            f"<b>{format_balance(bet)}</b> 🥜"
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

    if (
        result[0]
        == result[1]
        == result[2]
    ):
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

    text = (
        "🎰 <b>| "
        + " | ".join(result)
        + " |</b>\n\n"
    )

    if won:
        text += (
            f"🎉 Выплата: "
            f"<b>{format_balance(payout)}</b> 🥜"
        )
    else:
        text += "💀 Не повезло."

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
        1, 3, 5, 7, 9,
        12, 14, 16, 18,
        19, 21, 23, 25,
        27, 30, 32, 34,
        36,
    }:
        color = "red"

    else:
        color = "black"

    won = color == choice

    multiplier = (
        {
            "red": 1.95,
            "black": 1.95,
            "green": 14.0,
        }[choice]
        if won
        else 0
    )

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
            f"🎡 Выпало: "
            f"<b>{number}</b> {color_emoji}\n\n"
            f"🎉 Выплата: "
            f"<b>{format_balance(payout)}</b> 🥜"
        )
    else:
        text = (
            f"🎡 Выпало: "
            f"<b>{number}</b> {color_emoji}\n\n"
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
            f"🔢 Выпало число "
            f"<b>{generated}</b>!\n\n"
            f"🎉 Ты выиграл "
            f"<b>{format_balance(payout - bet)}</b> 🥜"
        )
    else:
        text = (
            f"🔢 Выпало число "
            f"<b>{generated}</b>.\n\n"
            "💀 Не угадал."
        )

    return ServiceResult(
        True,
        text,
        changed=True,
    )


# ============================================================================
# FOOTBALL
# ============================================================================


async def play_football(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    bet: int,
) -> ServiceResult:

    _, error = await prepare_game(
        session,
        chat_id,
        user_id,
        "football",
        bet,
    )

    if error:
        return error

    result = RNG.choice(
        [
            "⚽ Гол!",
            "🧤 Вратарь отбил!",
            "🥅 Штанга!",
            "⚽ Красивый гол!",
        ]
    )

    won = result in {
        "⚽ Гол!",
        "⚽ Красивый гол!",
    }

    multiplier = 2.0 if won else 0

    payout = await finish_game(
        session,
        chat_id,
        user_id,
        "football",
        bet,
        result,
        multiplier,
        won,
    )

    if won:
        text = (
            f"⚽ <b>{result}</b>\n\n"
            f"🏆 Выплата: "
            f"<b>{format_balance(payout)}</b> 🥜"
        )
    else:
        text = (
            f"⚽ <b>{result}</b>\n\n"
            "💀 Ставка проиграна."
        )

    return ServiceResult(
        True,
        text,
        changed=True,
    )


# ============================================================================
# BASKETBALL
# ============================================================================


async def play_basketball(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    bet: int,
) -> ServiceResult:

    _, error = await prepare_game(
        session,
        chat_id,
        user_id,
        "basketball",
        bet,
    )

    if error:
        return error

    result = RNG.choice(
        [
            "🏀 Попадание!",
            "🏀 Трёшка!",
            "🧱 Мимо!",
            "🏀 Данкан!",
        ]
    )

    won = result in {
        "🏀 Попадание!",
        "🏀 Трёшка!",
        "🏀 Данкан!",
    }

    multiplier = 2.0 if won else 0

    payout = await finish_game(
        session,
        chat_id,
        user_id,
        "basketball",
        bet,
        result,
        multiplier,
        won,
    )

    if won:
        text = (
            f"🏀 <b>{result}</b>\n\n"
            f"🏆 Выплата: "
            f"<b>{format_balance(payout)}</b> 🥜"
        )
    else:
        text = (
            f"🏀 <b>{result}</b>\n\n"
            "💀 Мимо."
        )

    return ServiceResult(
        True,
        text,
        changed=True,
    )


# ============================================================================
# CREATE GAME / LIST
# ============================================================================


async def create_game(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    game_type: str,
    bet: int,
) -> ServiceResult:

    handlers = {
        "coinflip": play_coinflip,
        "dice": play_dice,
        "slots": play_slots,
        "football": play_football,
        "basketball": play_basketball,
    }

    handler = handlers.get(
        game_type
    )

    if handler is None:
        return ServiceResult(
            False,
            "❌ Эта игра запускается другим способом.",
        )

    return await handler(
        session,
        chat_id,
        user_id,
        bet,
    )


def get_game_list() -> list[str]:
    return [
        "coinflip",
        "dice",
        "slots",
        "roulette",
        "guess",
        "football",
        "basketball",
        "tictactoe",
        "blackjack",
        "crash",
    ]


# ============================================================================
# TIC TAC TOE
# ============================================================================


def ttt_keyboard(
    game: TicTacToeGame,
) -> InlineKeyboardMarkup:

    builder = InlineKeyboardBuilder()

    for position, symbol in enumerate(
        game.board
    ):
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
            and board[a]
            == board[b]
            == board[c]
        ):
            return board[a]

    if "-" not in board:
        return "draw"

    return None


async def start_tictactoe(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    bet: int = 10,
) -> ServiceResult:

    if bet < 10:
        return ServiceResult(
            False,
            "❌ Минимальная ставка TTT — 10 🥜.",
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

    required_level = 10

    if member.level < required_level:
        return ServiceResult(
            False,
            (
                f"🔒 Крестики-нолики открываются "
                f"на <b>{required_level} уровне</b>."
            ),
        )

    _, error = await can_afford(
        session,
        chat_id,
        user_id,
        bet,
    )

    if error:
        return ServiceResult(
            False,
            error,
        )

    existing = await session.execute(
        select(TicTacToeGame).where(
            TicTacToeGame.chat_id == chat_id,
            TicTacToeGame.status.in_(
                ["waiting", "playing"]
            ),
        )
    )

    for game in existing.scalars().all():
        if (
            game.player_x_id == user_id
            or game.player_o_id == user_id
        ):
            return ServiceResult(
                False,
                "❌ У тебя уже есть активная игра.",
            )

    # Ставка резервируется сразу.
    await change_balance(
        session,
        chat_id,
        user_id,
        -bet,
        "ttt_bet",
        "Ставка в крестики-нолики",
    )

    game = TicTacToeGame(
        chat_id=chat_id,
        player_x_id=user_id,
        current_player_id=user_id,
        board="---------",
        status="waiting",
        bet=bet,
    )

    session.add(game)

    await session.flush()

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎮 Присоединиться",
                    callback_data=(
                        f"tttjoin:{game.id}"
                    ),
                )
            ]
        ]
    )

    return ServiceResult(
        True,
        (
            "⭕❌ <b>Крестики-нолики</b>\n\n"
            "Игрок X создал игру.\n"
            f"Ставка: <b>{format_balance(bet)}</b> 🥜\n\n"
            "Нажми кнопку, чтобы присоединиться."
        ),
        changed=True,
        keyboard=keyboard,
    )


async def join_tictactoe(
    session: AsyncSession,
    game_id: int,
    user_id: int,
) -> ServiceResult:

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

    if game.status != "waiting":
        return ServiceResult(
            False,
            "❌ В эту игру уже нельзя войти.",
            answer="Игра недоступна.",
            show_alert=True,
        )

    if game.player_x_id == user_id:
        return ServiceResult(
            False,
            "❌ Нельзя играть самому с собой.",
            answer="Нельзя играть самому с собой.",
            show_alert=True,
        )

    member, error = await can_afford(
        session,
        game.chat_id,
        user_id,
        game.bet,
    )

    if error:
        return ServiceResult(
            False,
            error,
            answer="Недостаточно арахиса.",
            show_alert=True,
        )

    game.player_o_id = user_id
    game.current_player_id = game.player_x_id
    game.status = "playing"

    await change_balance(
        session,
        game.chat_id,
        user_id,
        -game.bet,
        "ttt_bet",
        "Ставка в крестики-нолики",
    )

    return ServiceResult(
        True,
        (
            "⭕❌ <b>Игра началась!</b>\n\n"
            f"Ставка: <b>{format_balance(game.bet)}</b> 🥜\n"
            "Ход ❌"
        ),
        changed=True,
        keyboard=ttt_keyboard(game),
    )


async def tictactoe_move(
    session: AsyncSession,
    game_id: int,
    user_id: int,
    position: int,
) -> ServiceResult:

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

    if not 0 <= position <= 8:
        return ServiceResult(
            False,
            "❌ Некорректная клетка.",
            answer="Некорректная клетка.",
            show_alert=True,
        )

    board = list(
        game.board
    )

    if board[position] != "-":
        return ServiceResult(
            False,
            "❌ Клетка занята.",
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

            total = game.bet * 2

            # При ничьей возвращаем обе ставки.
            await change_balance(
                session,
                game.chat_id,
                game.player_x_id,
                game.bet,
                "ttt_refund",
                "Возврат при ничьей TTT",
            )

            if game.player_o_id:
                await change_balance(
                    session,
                    game.chat_id,
                    game.player_o_id,
                    game.bet,
                    "ttt_refund",
                    "Возврат при ничьей TTT",
                )

            text = (
                "⭕❌ <b>Ничья!</b>\n\n"
                "Ставки возвращены."
            )

        else:
            winner_id = (
                game.player_x_id
                if winner == "X"
                else game.player_o_id
            )

            loser_id = (
                game.player_o_id
                if winner == "X"
                else game.player_x_id
            )

            game.winner_id = winner_id

            if winner_id is not None:
                await change_balance(
                    session,
                    game.chat_id,
                    winner_id,
                    game.bet * 2,
                    "ttt_payout",
                    "Победа в TTT",
                )

            winner_member = await get_member(
                session,
                game.chat_id,
                winner_id,
            )

            loser_member = await get_member(
                session,
                game.chat_id,
                loser_id,
            )

            if winner_member:
                winner_member.games_played += 1
                winner_member.games_won += 1
                winner_member.total_won += game.bet

            if loser_member:
                loser_member.games_played += 1
                loser_member.games_lost += 1
                loser_member.total_lost += game.bet

            text = (
                "⭕❌ <b>Игра окончена!</b>\n\n"
                f"Победитель: "
                f"<a href=\"tg://user?id={winner_id}\">"
                f"игрок"
                f"</a> 🎉\n"
                f"🏆 Выигрыш: "
                f"<b>{format_balance(game.bet * 2)}</b> 🥜"
            )

        return ServiceResult(
            True,
            text,
            changed=True,
            keyboard=ttt_keyboard(game),
        )

    if game.player_o_id is None:
        return ServiceResult(
            False,
            "❌ В игре нет второго игрока.",
            answer="Нет второго игрока.",
            show_alert=True,
        )

    game.current_player_id = (
        game.player_o_id
        if user_id == game.player_x_id
        else game.player_x_id
    )

    current_symbol = (
        "❌"
        if game.current_player_id
        == game.player_x_id
        else "⭕"
    )

    return ServiceResult(
        True,
        (
            "⭕❌ <b>Крестики-нолики</b>\n\n"
            f"Ход: {current_symbol}"
        ),
        changed=True,
        keyboard=ttt_keyboard(game),
    )

# ============================================================================
# GAMES COMMON
# ============================================================================


def game_unlocked(
    member: ChatMember,
    game_type: str,
) -> bool:

    required_level = 1

    for level, features in LEVEL_UNLOCKS.items():
        if game_type in features:
            required_level = min(
                required_level,
                level,
            )

    # Более надёжный поиск по таблице unlocks.
    found_level = None

    for level, features in LEVEL_UNLOCKS.items():
        if game_type in features:
            found_level = level
            break

    if found_level is None:
        return True

    return member.level >= found_level


async def prepare_game(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    game_type: str,
    bet: int,
) -> tuple[
    Optional[ChatMember],
    Optional[ServiceResult],
]:

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

    if member is not None:
        required_level = None

        for level, features in LEVEL_UNLOCKS.items():
            if game_type in features:
                required_level = level
                break

        if (
            required_level is not None
            and member.level < required_level
        ):
            return (
                member,
                ServiceResult(
                    False,
                    (
                        f"🔒 Игра откроется на "
                        f"<b>{required_level} уровне</b>.\n"
                        f"Твой уровень: <b>{member.level}</b>."
                    ),
                ),
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

    payout = (
        int(
            bet * multiplier
        )
        if won
        else 0
    )

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

    session.add(
        Game(
            chat_id=chat_id,
            user_id=user_id,
            game_type=game_type,
            bet=bet,
            result=result,
            multiplier=multiplier,
            payout=payout,
            won=won,
            status="finished",
        )
    )

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
            f"🎉 Ты выиграл "
            f"<b>{format_balance(payout - bet)}</b> 🥜"
        )
    else:
        text = (
            "🪙 <b>Решка!</b>\n\n"
            f"💀 Ты проиграл "
            f"<b>{format_balance(bet)}</b> 🥜"
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

    multiplier = 1.8 if won else 0

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
            f"🎲 {first} + {second} = "
            f"<b>{total}</b>\n\n"
            f"🏆 Выигрыш: "
            f"<b>{format_balance(payout - bet)}</b> 🥜"
        )
    else:
        text = (
            f"🎲 {first} + {second} = "
            f"<b>{total}</b>\n\n"
            f"💀 Проигрыш: "
            f"<b>{format_balance(bet)}</b> 🥜"
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

    if (
        result[0]
        == result[1]
        == result[2]
    ):
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

    text = (
        "🎰 <b>| "
        + " | ".join(result)
        + " |</b>\n\n"
    )

    if won:
        text += (
            f"🎉 Выплата: "
            f"<b>{format_balance(payout)}</b> 🥜"
        )
    else:
        text += "💀 Не повезло."

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
        1, 3, 5, 7, 9,
        12, 14, 16, 18,
        19, 21, 23, 25,
        27, 30, 32, 34,
        36,
    }:
        color = "red"

    else:
        color = "black"

    won = color == choice

    multiplier = (
        {
            "red": 1.95,
            "black": 1.95,
            "green": 14.0,
        }[choice]
        if won
        else 0
    )

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
            f"🎡 Выпало: "
            f"<b>{number}</b> {color_emoji}\n\n"
            f"🎉 Выплата: "
            f"<b>{format_balance(payout)}</b> 🥜"
        )
    else:
        text = (
            f"🎡 Выпало: "
            f"<b>{number}</b> {color_emoji}\n\n"
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
            f"🔢 Выпало число "
            f"<b>{generated}</b>!\n\n"
            f"🎉 Ты выиграл "
            f"<b>{format_balance(payout - bet)}</b> 🥜"
        )
    else:
        text = (
            f"🔢 Выпало число "
            f"<b>{generated}</b>.\n\n"
            "💀 Не угадал."
        )

    return ServiceResult(
        True,
        text,
        changed=True,
    )


# ============================================================================
# FOOTBALL
# ============================================================================


async def play_football(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    bet: int,
) -> ServiceResult:

    _, error = await prepare_game(
        session,
        chat_id,
        user_id,
        "football",
        bet,
    )

    if error:
        return error

    result = RNG.choice(
        [
            "⚽ Гол!",
            "🧤 Вратарь отбил!",
            "🥅 Штанга!",
            "⚽ Красивый гол!",
        ]
    )

    won = result in {
        "⚽ Гол!",
        "⚽ Красивый гол!",
    }

    multiplier = 2.0 if won else 0

    payout = await finish_game(
        session,
        chat_id,
        user_id,
        "football",
        bet,
        result,
        multiplier,
        won,
    )

    if won:
        text = (
            f"⚽ <b>{result}</b>\n\n"
            f"🏆 Выплата: "
            f"<b>{format_balance(payout)}</b> 🥜"
        )
    else:
        text = (
            f"⚽ <b>{result}</b>\n\n"
            "💀 Ставка проиграна."
        )

    return ServiceResult(
        True,
        text,
        changed=True,
    )


# ============================================================================
# BASKETBALL
# ============================================================================


async def play_basketball(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    bet: int,
) -> ServiceResult:

    _, error = await prepare_game(
        session,
        chat_id,
        user_id,
        "basketball",
        bet,
    )

    if error:
        return error

    result = RNG.choice(
        [
            "🏀 Попадание!",
            "🏀 Трёшка!",
            "🧱 Мимо!",
            "🏀 Данкан!",
        ]
    )

    won = result in {
        "🏀 Попадание!",
        "🏀 Трёшка!",
        "🏀 Данкан!",
    }

    multiplier = 2.0 if won else 0

    payout = await finish_game(
        session,
        chat_id,
        user_id,
        "basketball",
        bet,
        result,
        multiplier,
        won,
    )

    if won:
        text = (
            f"🏀 <b>{result}</b>\n\n"
            f"🏆 Выплата: "
            f"<b>{format_balance(payout)}</b> 🥜"
        )
    else:
        text = (
            f"🏀 <b>{result}</b>\n\n"
            "💀 Мимо."
        )

    return ServiceResult(
        True,
        text,
        changed=True,
    )


# ============================================================================
# CREATE GAME / LIST
# ============================================================================


async def create_game(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    game_type: str,
    bet: int,
) -> ServiceResult:

    handlers = {
        "coinflip": play_coinflip,
        "dice": play_dice,
        "slots": play_slots,
        "football": play_football,
        "basketball": play_basketball,
    }

    handler = handlers.get(
        game_type
    )

    if handler is None:
        return ServiceResult(
            False,
            "❌ Эта игра запускается другим способом.",
        )

    return await handler(
        session,
        chat_id,
        user_id,
        bet,
    )


def get_game_list() -> list[str]:
    return [
        "coinflip",
        "dice",
        "slots",
        "roulette",
        "guess",
        "football",
        "basketball",
        "tictactoe",
        "blackjack",
        "crash",
    ]


# ============================================================================
# TIC TAC TOE
# ============================================================================


def ttt_keyboard(
    game: TicTacToeGame,
) -> InlineKeyboardMarkup:

    builder = InlineKeyboardBuilder()

    for position, symbol in enumerate(
        game.board
    ):
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
            and board[a]
            == board[b]
            == board[c]
        ):
            return board[a]

    if "-" not in board:
        return "draw"

    return None


async def start_tictactoe(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    bet: int = 10,
) -> ServiceResult:

    if bet < 10:
        return ServiceResult(
            False,
            "❌ Минимальная ставка TTT — 10 🥜.",
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

    required_level = 10

    if member.level < required_level:
        return ServiceResult(
            False,
            (
                f"🔒 Крестики-нолики открываются "
                f"на <b>{required_level} уровне</b>."
            ),
        )

    _, error = await can_afford(
        session,
        chat_id,
        user_id,
        bet,
    )

    if error:
        return ServiceResult(
            False,
            error,
        )

    existing = await session.execute(
        select(TicTacToeGame).where(
            TicTacToeGame.chat_id == chat_id,
            TicTacToeGame.status.in_(
                ["waiting", "playing"]
            ),
        )
    )

    for game in existing.scalars().all():
        if (
            game.player_x_id == user_id
            or game.player_o_id == user_id
        ):
            return ServiceResult(
                False,
                "❌ У тебя уже есть активная игра.",
            )

    # Ставка резервируется сразу.
    await change_balance(
        session,
        chat_id,
        user_id,
        -bet,
        "ttt_bet",
        "Ставка в крестики-нолики",
    )

    game = TicTacToeGame(
        chat_id=chat_id,
        player_x_id=user_id,
        current_player_id=user_id,
        board="---------",
        status="waiting",
        bet=bet,
    )

    session.add(game)

    await session.flush()

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎮 Присоединиться",
                    callback_data=(
                        f"tttjoin:{game.id}"
                    ),
                )
            ]
        ]
    )

    return ServiceResult(
        True,
        (
            "⭕❌ <b>Крестики-нолики</b>\n\n"
            "Игрок X создал игру.\n"
            f"Ставка: <b>{format_balance(bet)}</b> 🥜\n\n"
            "Нажми кнопку, чтобы присоединиться."
        ),
        changed=True,
        keyboard=keyboard,
    )


async def join_tictactoe(
    session: AsyncSession,
    game_id: int,
    user_id: int,
) -> ServiceResult:

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

    if game.status != "waiting":
        return ServiceResult(
            False,
            "❌ В эту игру уже нельзя войти.",
            answer="Игра недоступна.",
            show_alert=True,
        )

    if game.player_x_id == user_id:
        return ServiceResult(
            False,
            "❌ Нельзя играть самому с собой.",
            answer="Нельзя играть самому с собой.",
            show_alert=True,
        )

    member, error = await can_afford(
        session,
        game.chat_id,
        user_id,
        game.bet,
    )

    if error:
        return ServiceResult(
            False,
            error,
            answer="Недостаточно арахиса.",
            show_alert=True,
        )

    game.player_o_id = user_id
    game.current_player_id = game.player_x_id
    game.status = "playing"

    await change_balance(
        session,
        game.chat_id,
        user_id,
        -game.bet,
        "ttt_bet",
        "Ставка в крестики-нолики",
    )

    return ServiceResult(
        True,
        (
            "⭕❌ <b>Игра началась!</b>\n\n"
            f"Ставка: <b>{format_balance(game.bet)}</b> 🥜\n"
            "Ход ❌"
        ),
        changed=True,
        keyboard=ttt_keyboard(game),
    )


async def tictactoe_move(
    session: AsyncSession,
    game_id: int,
    user_id: int,
    position: int,
) -> ServiceResult:

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

    if not 0 <= position <= 8:
        return ServiceResult(
            False,
            "❌ Некорректная клетка.",
            answer="Некорректная клетка.",
            show_alert=True,
        )

    board = list(
        game.board
    )

    if board[position] != "-":
        return ServiceResult(
            False,
            "❌ Клетка занята.",
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

            total = game.bet * 2

            # При ничьей возвращаем обе ставки.
            await change_balance(
                session,
                game.chat_id,
                game.player_x_id,
                game.bet,
                "ttt_refund",
                "Возврат при ничьей TTT",
            )

            if game.player_o_id:
                await change_balance(
                    session,
                    game.chat_id,
                    game.player_o_id,
                    game.bet,
                    "ttt_refund",
                    "Возврат при ничьей TTT",
                )

            text = (
                "⭕❌ <b>Ничья!</b>\n\n"
                "Ставки возвращены."
            )

        else:
            winner_id = (
                game.player_x_id
                if winner == "X"
                else game.player_o_id
            )

            loser_id = (
                game.player_o_id
                if winner == "X"
                else game.player_x_id
            )

            game.winner_id = winner_id

            if winner_id is not None:
                await change_balance(
                    session,
                    game.chat_id,
                    winner_id,
                    game.bet * 2,
                    "ttt_payout",
                    "Победа в TTT",
                )

            winner_member = await get_member(
                session,
                game.chat_id,
                winner_id,
            )

            loser_member = await get_member(
                session,
                game.chat_id,
                loser_id,
            )

            if winner_member:
                winner_member.games_played += 1
                winner_member.games_won += 1
                winner_member.total_won += game.bet

            if loser_member:
                loser_member.games_played += 1
                loser_member.games_lost += 1
                loser_member.total_lost += game.bet

            text = (
                "⭕❌ <b>Игра окончена!</b>\n\n"
                f"Победитель: "
                f"<a href=\"tg://user?id={winner_id}\">"
                f"игрок"
                f"</a> 🎉\n"
                f"🏆 Выигрыш: "
                f"<b>{format_balance(game.bet * 2)}</b> 🥜"
            )

        return ServiceResult(
            True,
            text,
            changed=True,
            keyboard=ttt_keyboard(game),
        )

    if game.player_o_id is None:
        return ServiceResult(
            False,
            "❌ В игре нет второго игрока.",
            answer="Нет второго игрока.",
            show_alert=True,
        )

    game.current_player_id = (
        game.player_o_id
        if user_id == game.player_x_id
        else game.player_x_id
    )

    current_symbol = (
        "❌"
        if game.current_player_id
        == game.player_x_id
        else "⭕"
    )

    return ServiceResult(
        True,
        (
            "⭕❌ <b>Крестики-нолики</b>\n\n"
            f"Ход: {current_symbol}"
        ),
        changed=True,
        keyboard=ttt_keyboard(game),
    )