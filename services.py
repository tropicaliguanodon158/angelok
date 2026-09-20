from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from html import escape
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core import (
    ABORT_COST,
    ABORT_SUCCESS_CHANCE,
    ADULT_RP_COST,
    ADULT_RP_COOLDOWN_SECONDS,
    ADULT_RP_SIZE_GAIN_MAX,
    ADULT_RP_SIZE_GAIN_MIN,
    ADULT_RP_TARGET_SIZE_LOSS_MAX,
    ADULT_RP_TARGET_SIZE_LOSS_MIN,
    BATTLE_PASS_MAX_LEVEL,
    BATTLE_PASS_REWARDS,
    BASKETBALL_MULTIPLIER,
    BLACKJACK_DRAW_REFUND,
    BLACKJACK_MIN_BET,
    BLACKJACK_NATURAL_MULTIPLIER,
    BLACKJACK_WIN_MULTIPLIER,
    CASE_REWARDS,
    CHILD_DURATION_HOURS,
    CHILD_SUPPORT_PER_HOUR,
    CONDOM_DISEASE_PROTECTION_CHANCE,
    CONDOM_ITEM_CODE,
    CRASH_MAX_MULTIPLIER,
    CRASH_MIN_BET,
    CRASH_MIN_MULTIPLIER,
    DEFAULT_MODERATION_PERMISSIONS,
    DISEASE_CONTRACT_CHANCE,
    DISEASE_MEDICINE_COST,
    DISEASE_SIZE_LOSS_PER_TICK,
    DISEASE_TICK_COST,
    DILDO_DUPLICATE_COMPENSATION,
    DILDO_ITEM_CODE,
    DILDO_MAX_OWNED,
    DILDO_MAX_USES,
    DILDO_MIN_USES,
    FOOTBALL_MULTIPLIER,
    IMPREGNATION_CHANCE_WITH_CONDOM,
    IMPREGNATION_CHANCE_WITHOUT_CONDOM,
    LEVEL_UNLOCKS,
    LEVEL_UP_SIZE_BONUS,
    LUBRICANT_GROWTH_BONUS,
    LUBRICANT_ITEM_CODE,
    MASTURBATION_COOLDOWN_SECONDS,
    MASTURBATION_MAX_GAIN,
    MASTURBATION_MIN_GAIN,
    MODERATION_PERMISSION_LEVEL,
    NORMAL_RP_COST,
    PERMISSION_ADMIN,
    PERMISSION_HEAD_ADMIN,
    PERMISSION_STAFF,
    ROLE_ADMIN,
    ROLE_HEAD_ADMIN,
    ROLE_MODERATOR,
    ROLE_OWNER,
    ROLE_POWER,
    RP_ACTIONS,
    RUBBER_PUSSY_COOLDOWN_MULTIPLIER,
    RUBBER_PUSSY_DAILY_BONUS,
    RUBBER_PUSSY_DAILY_CHANCE,
    RUBBER_PUSSY_ITEM_CODE,
    RUBBER_PUSSY_MASTURBATION_MAX,
    RUBBER_PUSSY_MASTURBATION_MIN,
    ROB_COOLDOWN_SECONDS,
    ROB_MAX_REWARD_PERCENT,
    ROB_MAX_SUCCESS_CHANCE,
    ROB_MIN_REWARD_PERCENT,
    ROB_MIN_SUCCESS_CHANCE,
    SILICONE_IMPLANT_BONUS,
    SILICONE_IMPLANT_ITEM_CODE,
    TAG_DISPLAY_NAMES,
    TAG_LIVING_LEGEND,
    TICTACTOE_DRAW_REFUND,
    TICTACTOE_MIN_BET,
    TICTACTOE_WIN_MULTIPLIER,
    VENEREOLOGIST_COST,
    VENEREOLOGIST_CURE_CHANCE,
    can_manage_role,
    can_use_moderation_command,
    get_adult_rp_action,
    get_config,
    get_feature_required_level,
    get_rp_action_by_alias,
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
    get_staff_member,
    get_staff_role,
    get_tag_by_code,
    get_top_by_balance,
    get_top_by_messages,
    get_top_by_penis_size,
    get_top_by_xp,
    get_user_item,
    get_user_items,
    get_user_tags,
    utcnow,
)


@dataclass
class ServiceResult:
    success: bool
    message: str
    changed: bool = False
    level_up_message: Optional[str] = None
    keyboard: Optional[InlineKeyboardMarkup] = None
    answer: Optional[str] = None
    show_alert: bool = False


config = get_config()
RNG = random.SystemRandom()

MAX_PROFILE_NICK_LENGTH = 32

BP_XP_PER_LEVEL = 100
BP_MAX_LEVEL = BATTLE_PASS_MAX_LEVEL

SIZE_LEVEL_REWARD = LEVEL_UP_SIZE_BONUS

ADULT_RP_COOLDOWN = ADULT_RP_COOLDOWN_SECONDS
MASTURBATION_COOLDOWN = MASTURBATION_COOLDOWN_SECONDS

NORMAL_RP_COST_VALUE = NORMAL_RP_COST
ADULT_RP_COST_VALUE = ADULT_RP_COST

ROB_COOLDOWN = ROB_COOLDOWN_SECONDS

DISEASE_TICK_INTERVAL = 60 * 60

CHILD_DURATION = CHILD_DURATION_HOURS * 60 * 60
CHILD_SUPPORT_COST = CHILD_SUPPORT_PER_HOUR
ABORT_COST_VALUE = ABORT_COST

RUBBER_DAILY_INTERVAL = 24 * 60 * 60

GAME_FEATURES = {
    "coinflip": "coinflip",
    "dice": "dice",
    "slots": "slots",
    "roulette": "roulette",
    "guess": "guess",
    "football": "football",
    "basketball": "basketball",
    "tictactoe": "tictactoe",
    "blackjack": "blackjack",
    "crash": "crash",
}

_BALANCE_LOCK = asyncio.Lock()
_BATTLE_PASS_LOCK = asyncio.Lock()
_TTT_LOCK = asyncio.Lock()
_CASE_LOCK = asyncio.Lock()
_GIVEAWAY_LOCK = asyncio.Lock()


def clean_name(user: Optional[User]) -> str:
    if user is None:
        return "Игрок"

    if user.username:
        return f"@{escape(user.username)}"

    return escape(user.first_name or "Игрок")


def format_balance(amount: int) -> str:
    return f"{amount:,}".replace(",", " ")


def user_mention(user_id: int, name: str) -> str:
    return f'<a href="tg://user?id={user_id}">{name}</a>'


def normalize_text(value: str) -> str:
    return " ".join(value.strip().lower().split())


def cooldown_remaining(
    last_at: Optional[datetime],
    cooldown_seconds: float,
) -> int:
    if last_at is None:
        return 0

    elapsed = (utcnow() - last_at).total_seconds()
    return max(0, int(cooldown_seconds - elapsed))


def format_seconds(seconds: int) -> str:
    if seconds <= 0:
        return "сейчас"

    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    parts = []

    if hours:
        parts.append(f"{hours} ч.")

    if minutes:
        parts.append(f"{minutes} мин.")

    if not hours and secs:
        parts.append(f"{secs} сек.")

    return " ".join(parts)


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

    return await get_or_create_member(
        session=session,
        chat_id=chat_id,
        user_id=user_id,
    )


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


async def _change_balance_unlocked(
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

    now = utcnow()

    conditions = [
        ChatMember.chat_id == chat_id,
        ChatMember.user_id == user_id,
    ]

    if amount < 0:
        conditions.append(
            ChatMember.balance + amount >= 0
        )

    statement = (
        update(ChatMember)
        .where(*conditions)
        .values(
            balance=ChatMember.balance + amount,
            updated_at=now,
        )
    )

    result = await session.execute(statement)

    if result.rowcount != 1:
        raise ValueError(
            "Недостаточно арахиса."
        )

    await session.refresh(
        member,
        attribute_names=[
            "balance",
            "updated_at",
        ],
    )

    await add_transaction(
        session=session,
        chat_id=chat_id,
        user_id=user_id,
        amount=amount,
        balance_after=member.balance,
        transaction_type=transaction_type,
        description=description,
    )

    await session.flush()

    return member


async def change_balance(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    amount: int,
    transaction_type: str,
    description: Optional[str] = None,
) -> ChatMember:
    async with _BALANCE_LOCK:
        return await _change_balance_unlocked(
            session=session,
            chat_id=chat_id,
            user_id=user_id,
            amount=amount,
            transaction_type=transaction_type,
            description=description,
        )


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


async def grant_tag(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    tag_code: str,
    earned_from: str,
) -> Optional[Tag]:
    tag = await get_tag_by_code(
        session,
        tag_code,
    )

    if tag is None:
        tag = Tag(
            code=tag_code,
            name=TAG_DISPLAY_NAMES.get(
                tag_code,
                tag_code,
            ),
            description=f"Получен через {earned_from}.",
        )

        session.add(tag)
        await session.flush()

    result = await session.execute(
        select(UserTag).where(
            UserTag.chat_id == chat_id,
            UserTag.user_id == user_id,
            UserTag.tag_id == tag.id,
        )
    )

    if result.scalar_one_or_none() is None:
        session.add(
            UserTag(
                chat_id=chat_id,
                user_id=user_id,
                tag_id=tag.id,
                earned_from=earned_from,
            )
        )

        await session.flush()

    return tag


async def grant_item(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    item_code: str,
    quantity: int = 1,
) -> Optional[UserItem]:
    if quantity <= 0:
        return None

    item = await get_inventory_item(
        session,
        item_code,
    )

    if item is None:
        return None

    if item_code == SILICONE_IMPLANT_ITEM_CODE:
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

        member.penis_size = round(
            max(
                0,
                member.penis_size
                + SILICONE_IMPLANT_BONUS * quantity,
            ),
            2,
        )

        await session.flush()
        return None

    user_item = await get_user_item(
        session,
        chat_id,
        user_id,
        item_code,
    )

    if user_item is None:
        uses_left = None

        if item_code == DILDO_ITEM_CODE:
            uses_left = RNG.randint(
                DILDO_MIN_USES,
                DILDO_MAX_USES,
            )

        user_item = UserItem(
            chat_id=chat_id,
            user_id=user_id,
            item_id=item.id,
            quantity=quantity,
            uses_left=uses_left,
        )

        session.add(user_item)

    else:
        max_quantity = getattr(
            item,
            "max_quantity",
            None,
        )

        if max_quantity is None:
            user_item.quantity += quantity
        else:
            user_item.quantity = min(
                max_quantity,
                user_item.quantity + quantity,
            )

        if (
            item_code == DILDO_ITEM_CODE
            and user_item.uses_left is None
        ):
            user_item.uses_left = RNG.randint(
                DILDO_MIN_USES,
                DILDO_MAX_USES,
            )

    await session.flush()
    return user_item


async def _consume_user_item(
    session: AsyncSession,
    item: UserItem,
) -> None:
    if item.uses_left is not None:
        if item.uses_left > 1:
            item.uses_left -= 1
            return

        await session.delete(item)
        return

    if item.quantity > 1:
        item.quantity -= 1
    else:
        await session.delete(item)


async def _has_item(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    item_code: str,
) -> Optional[UserItem]:
    return await get_user_item(
        session,
        chat_id,
        user_id,
        item_code,
    )


async def reconcile_rubber_pussy_daily(
    session: AsyncSession,
    member: ChatMember,
) -> float:
    item = await _has_item(
        session,
        member.chat_id,
        member.user_id,
        RUBBER_PUSSY_ITEM_CODE,
    )

    if item is None:
        return 0.0

    now = utcnow()

    if member.last_rubber_daily_bonus_at is not None:
        elapsed = (
            now - member.last_rubber_daily_bonus_at
        ).total_seconds()

        if elapsed < RUBBER_DAILY_INTERVAL:
            return 0.0

    member.last_rubber_daily_bonus_at = now

    if RNG.random() >= RUBBER_PUSSY_DAILY_CHANCE:
        return 0.0

    member.penis_size = round(
        max(
            0.0,
            member.penis_size
            + RUBBER_PUSSY_DAILY_BONUS,
        ),
        2,
    )

    return RUBBER_PUSSY_DAILY_BONUS


async def reconcile_member_state(
    session: AsyncSession,
    member: ChatMember,
) -> None:
    await reconcile_disease(
        session,
        member,
    )

    await reconcile_child(
        session,
        member,
    )

    await reconcile_rubber_pussy_daily(
        session,
        member,
    )

    await session.flush()


async def format_inventory(
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

    await reconcile_member_state(
        session,
        member,
    )

    items = await get_user_items(
        session,
        chat_id,
        user_id,
    )

    if not items:
        return "🎒 Инвентарь пуст."

    lines = [
        "🎒 <b>Инвентарь</b>"
    ]

    for user_item in items:
        item = user_item.item

        if item is None:
            continue

        extra = ""

        if user_item.uses_left is not None:
            extra = (
                f" | использований: "
                f"<b>{user_item.uses_left}</b>"
            )

        lines.append(
            f"• {escape(item.name)} × "
            f"<b>{user_item.quantity}</b>{extra}"
        )

    return "\n".join(lines)


async def get_tag_keyboard(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
) -> InlineKeyboardMarkup:
    tags = await get_user_tags(
        session,
        chat_id,
        user_id,
    )

    member = await get_member(
        session,
        chat_id,
        user_id,
    )

    selected_id = (
        member.selected_tag_id
        if member
        else None
    )

    builder = InlineKeyboardBuilder()

    for user_tag in tags:
        tag = user_tag.tag

        if tag is None:
            continue

        prefix = (
            "✅ "
            if tag.id == selected_id
            else ""
        )

        builder.button(
            text=prefix + tag.name,
            callback_data=f"tagselect:{tag.id}",
        )

    builder.adjust(1)

    return builder.as_markup()


async def select_tag(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    tag_id: int,
) -> ServiceResult:
    member = await get_member(
        session,
        chat_id,
        user_id,
    )

    if member is None:
        return ServiceResult(
            False,
            "❌ Профиль не найден.",
        )

    result = await session.execute(
        select(UserTag).where(
            UserTag.chat_id == chat_id,
            UserTag.user_id == user_id,
            UserTag.tag_id == tag_id,
        )
    )

    user_tag = result.scalar_one_or_none()

    if user_tag is None:
        return ServiceResult(
            False,
            "❌ У тебя нет этого тега.",
            answer="У тебя нет этого тега.",
            show_alert=True,
        )

    tag = await session.get(
        Tag,
        tag_id,
    )

    if tag is None:
        return ServiceResult(
            False,
            "❌ Тег не найден.",
        )

    member.selected_tag_id = tag.id
    member.profile_tag = tag.name

    await session.flush()

    return ServiceResult(
        True,
        f"🏷 Выбран тег: <b>{escape(tag.name)}</b>",
        changed=True,
    )


async def set_profile_tag(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    tag: str,
) -> ServiceResult:
    return ServiceResult(
        False,
        (
            "❌ Самостоятельно устанавливать тег нельзя.\n"
            "🏷 Теги выдаются через игровые награды, кейсы "
            "и Battle Pass.\n\n"
            "Используй <code>/tag</code>, чтобы выбрать "
            "полученный тег."
        ),
    )


async def set_profile_nick(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    nick: str,
) -> ServiceResult:
    nick = nick.strip()

    if not nick:
        return ServiceResult(
            False,
            "❌ Ник не может быть пустым.",
        )

    if len(nick) > MAX_PROFILE_NICK_LENGTH:
        return ServiceResult(
            False,
            (
                "❌ Ник не должен быть длиннее "
                f"{MAX_PROFILE_NICK_LENGTH} символов."
            ),
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

    await session.flush()

    return ServiceResult(
        True,
        f"✏️ Ник изменён на <b>{escape(nick)}</b>.",
        changed=True,
    )


async def _process_battle_pass(
    session: AsyncSession,
    member: ChatMember,
) -> list[str]:
    async with _BATTLE_PASS_LOCK:
        old_level = member.battle_pass_level

        member.battle_pass_xp += 1

        new_level = min(
            BP_MAX_LEVEL,
            1 + member.battle_pass_xp // BP_XP_PER_LEVEL,
        )

        if new_level <= old_level:
            return []

        member.battle_pass_level = new_level

        messages: list[str] = []

        for level in range(
            old_level + 1,
            new_level + 1,
        ):
            reward = BATTLE_PASS_REWARDS.get(level)

            if reward is None:
                continue

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
                    reward_code=str(
                        reward.item_code
                        or reward.tag_code
                        or reward.reward_type
                    ),
                )
            )

            if reward.reward_type == "peanuts":
                await change_balance(
                    session,
                    member.chat_id,
                    member.user_id,
                    reward.amount,
                    "battle_pass_reward",
                    f"Battle Pass уровень {level}",
                )

            elif reward.reward_type == "xp":
                member.xp += reward.amount
                member.level = level_from_xp(
                    member.xp
                )

            elif reward.reward_type == "case":
                if reward.item_code:
                    await grant_item(
                        session,
                        member.chat_id,
                        member.user_id,
                        reward.item_code,
                    )

            elif reward.reward_type == "tag":
                if reward.tag_code:
                    await grant_tag(
                        session,
                        member.chat_id,
                        member.user_id,
                        reward.tag_code,
                        f"battle_pass:{level}",
                    )

            messages.append(
                f"• {level} — "
                f"{escape(reward.description)}"
            )

        return messages


async def handle_message(
    session: AsyncSession,
    message: Message,
) -> ServiceResult:
    if (
        not message.from_user
        or message.from_user.is_bot
    ):
        return ServiceResult(
            False,
            "",
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

    await reconcile_member_state(
        session,
        member,
    )

    now = utcnow()
    old_level = member.level

    member.messages += 1
    member.xp += config.message_xp

    new_level = level_from_xp(
        member.xp
    )

    if new_level > old_level:
        member.level = new_level

    bp_rewards = await _process_battle_pass(
        session,
        member,
    )

    post_bp_level = level_from_xp(
        member.xp
    )

    if post_bp_level > member.level:
        member.level = post_bp_level

    new_level = max(
        new_level,
        member.level,
    )

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

        await change_balance(
            session,
            message.chat.id,
            message.from_user.id,
            reward,
            "message_reward",
            "Награда за сообщение",
        )

        member.last_message_at = now

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

        unlocked = []

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
            f"🎉 "
            f"{user_mention(message.from_user.id, clean_name(user))}\n"
            f"Ты достиг <b>{new_level} уровня</b>! ⭐\n"
            f"📏 Размер: "
            f"<b>{member.penis_size:.2f} см</b>"
            f"{unlock_text}"
        )

    if bp_rewards:
        bp_text = (
            "🎫 <b>Battle Pass</b>\n"
            f"Уровень: "
            f"<b>{member.battle_pass_level}</b>\n"
            + "\n".join(bp_rewards)
        )

        if level_up_message:
            level_up_message += (
                "\n\n"
                + bp_text
            )
        else:
            level_up_message = (
                f"🎫 "
                f"{user_mention(message.from_user.id, clean_name(user))}\n"
                + bp_text
            )

    if (
        member.battle_pass_level >= BP_MAX_LEVEL
        and bp_rewards
    ):
        level_up_message = (
            level_up_message or ""
        ) + "\n\n🏆 <b>ЖИВАЯ ЛЕГЕНДА</b>"

    member.updated_at = now

    await session.flush()

    return ServiceResult(
        True,
        "",
        changed=True,
        level_up_message=level_up_message,
    )


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

    await reconcile_member_state(
        session,
        member,
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

    current_xp = xp_for_level(member.level)
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

    disease_text = ""

    if member.has_disease:
        next_tick_text = ""

        if member.next_disease_tick is not None:
            next_tick_text = (
                " "
                "(следующий тик через "
                f"<b>{format_seconds(max(0, int((member.next_disease_tick - utcnow()).total_seconds())))}</b>)"
            )

        disease_text = (
            "\n🦠 Болезнь: <b>есть</b>"
            f"{next_tick_text}"
            f"\n💊 Лечение: "
            f"<b>{format_balance(DISEASE_MEDICINE_COST)}</b> 🥜"
            f"\n🧑‍⚕️ Венеролог: "
            f"<b>{format_balance(VENEREOLOGIST_COST)}</b> 🥜"
        )

    child_text = ""

    if member.has_child:
        child_remaining = 0

        if member.child_until is not None:
            child_remaining = max(
                0,
                int(
                    (
                        member.child_until
                        - utcnow()
                    ).total_seconds()
                ),
            )

        child_text = (
            "\n👶 Ребёнок: <b>есть</b>"
            f"\n⏳ Осталось: "
            f"<b>{format_seconds(child_remaining)}</b>"
            f"\n🥜 Содержание: "
            f"<b>{format_balance(CHILD_SUPPORT_COST)}</b>/час"
            f"\n🏥 Аборт: "
            f"<b>{format_balance(ABORT_COST_VALUE)}</b> 🥜"
        )

    adult_cooldown = ADULT_RP_COOLDOWN
    masturbation_cooldown = MASTURBATION_COOLDOWN

    rubber = await _has_item(
        session,
        chat_id,
        user_id,
        RUBBER_PUSSY_ITEM_CODE,
    )

    if rubber:
        adult_cooldown *= RUBBER_PUSSY_COOLDOWN_MULTIPLIER
        masturbation_cooldown *= RUBBER_PUSSY_COOLDOWN_MULTIPLIER

    adult_remaining = cooldown_remaining(
        member.last_adult_rp_at,
        adult_cooldown,
    )

    masturbation_remaining = cooldown_remaining(
        member.last_masturbation_at,
        masturbation_cooldown,
    )

    cooldown_text = (
        "\n\n⏱ <b>Cooldown</b>"
        f"\n18+ RP: "
        f"<b>{format_seconds(adult_remaining)}</b>"
        f"\n😏 Мастурбация: "
        f"<b>{format_seconds(masturbation_remaining)}</b>"
    )

    return (
        f"👤 <b>{escape(name)}</b>"
        f"{tag_text}\n"
        f"⭐ Уровень: <b>{member.level}</b>\n"
        f"✨ XP: <b>{format_balance(member.xp)}</b>\n"
        f"{bar} {progress_percent}%\n"
        f"📈 До следующего уровня: "
        f"<b>{format_balance(xp_to_next_level(member.xp))}</b>\n\n"
        f"🎫 Battle Pass: "
        f"<b>{member.battle_pass_level}/{BP_MAX_LEVEL}</b>\n"
        f"📏 Размер: "
        f"<b>{member.penis_size:.2f} см</b>\n"
        f"🥜 Баланс: "
        f"<b>{format_balance(member.balance)}</b>\n"
        f"💬 Сообщений: "
        f"<b>{format_balance(member.messages)}</b>\n"
        f"🎮 Игр: "
        f"<b>{format_balance(member.games_played)}</b>\n"
        f"🏆 Побед: "
        f"<b>{format_balance(member.games_won)}</b>\n"
        f"💀 Поражений: "
        f"<b>{format_balance(member.games_lost)}</b>"
        f"{disease_text}"
        f"{child_text}"
        f"{cooldown_text}"
    )


async def format_other_profile(
    session: AsyncSession,
    chat_id: int,
    target_user_id: int,
) -> str:
    return await format_profile(
        session,
        chat_id,
        target_user_id,
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
        return "❌ Профиль не найден."

    await reconcile_member_state(
        session,
        member,
    )

    return (
        "📊 <b>Статистика</b>\n\n"
        f"💬 Сообщений: "
        f"<b>{format_balance(member.messages)}</b>\n"
        f"⭐ XP: "
        f"<b>{format_balance(member.xp)}</b>\n"
        f"🎮 Игр: "
        f"<b>{format_balance(member.games_played)}</b>\n"
        f"🏆 Побед: "
        f"<b>{format_balance(member.games_won)}</b>\n"
        f"💀 Поражений: "
        f"<b>{format_balance(member.games_lost)}</b>\n"
        f"📈 Выиграно: "
        f"<b>{format_balance(member.total_won)}</b> 🥜\n"
        f"📉 Проиграно: "
        f"<b>{format_balance(member.total_lost)}</b> 🥜\n"
        f"📏 Размер: "
        f"<b>{member.penis_size:.2f} см</b>"
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

    if member is None:
        member = await ensure_member(
            session,
            chat_id,
            user_id,
        )

    await reconcile_member_state(
        session,
        member,
    )

    return member.balance


async def get_leaderboard(
    session: AsyncSession,
    chat_id: int,
) -> str:
    balance_top = await get_top_by_balance(
        session,
        chat_id,
        5,
    )

    xp_top = await get_top_by_xp(
        session,
        chat_id,
        5,
    )

    size_top = await get_top_by_penis_size(
        session,
        chat_id,
        5,
    )

    for member in (
        balance_top
        + xp_top
        + size_top
    ):
        await reconcile_member_state(
            session,
            member,
        )

    def render(
        title: str,
        members: list[ChatMember],
        value,
    ) -> str:
        lines = [title]

        for index, member in enumerate(
            members,
            1,
        ):
            lines.append(
                f'{index}. <a href="tg://user?id={member.user_id}">'
                f"Игрок</a> — <b>{value(member)}</b>"
            )

        return "\n".join(lines)

    return (
        render(
            "🥜 <b>Топ по арахису</b>",
            balance_top,
            lambda m: format_balance(m.balance),
        )
        + "\n\n"
        + render(
            "⭐ <b>Топ по XP</b>",
            xp_top,
            lambda m: format_balance(m.xp),
        )
        + "\n\n"
        + render(
            "📏 <b>Топ по размеру</b>",
            size_top,
            lambda m: f"{m.penis_size:.2f} см",
        )
    )


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

    await reconcile_member_state(
        session,
        member,
    )

    now = utcnow()
    cutoff = now - timedelta(
        days=1,
    )

    async with _BALANCE_LOCK:
        statement = (
            update(ChatMember)
            .where(
                ChatMember.chat_id == chat_id,
                ChatMember.user_id == user_id,
                or_(
                    ChatMember.last_bonus_at.is_(None),
                    ChatMember.last_bonus_at <= cutoff,
                ),
            )
            .values(
                last_bonus_at=now,
                updated_at=now,
            )
        )

        result = await session.execute(statement)

        if result.rowcount != 1:
            current = await get_member(
                session,
                chat_id,
                user_id,
            )

            remaining = 0

            if (
                current is not None
                and current.last_bonus_at is not None
            ):
                remaining = max(
                    0,
                    int(
                        (
                            24 * 60 * 60
                            - (
                                now
                                - current.last_bonus_at
                            ).total_seconds()
                        )
                    ),
                )

            return ServiceResult(
                False,
                (
                    "⏳ Бонус уже получен.\n"
                    f"Следующий через "
                    f"<b>{format_seconds(remaining)}</b>."
                ),
            )

        amount = RNG.randint(
            config.daily_bonus_min,
            config.daily_bonus_max,
        )

        await _change_balance_unlocked(
            session,
            chat_id,
            user_id,
            amount,
            "daily_bonus",
            "Ежедневный бонус",
        )

    return ServiceResult(
        True,
        (
            "🎁 <b>Ежедневный бонус</b>\n\n"
            f"Ты получил "
            f"<b>{format_balance(amount)}</b> 🥜."
        ),
        changed=True,
    )


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
            "😐 Самому себе переводить нельзя.",
        )

    sender_member = await get_member(
        session,
        chat_id,
        sender_id,
    )

    if sender_member is None:
        sender_member = await ensure_member(
            session,
            chat_id,
            sender_id,
        )

    receiver_member = await get_member(
        session,
        chat_id,
        receiver_id,
    )

    if receiver_member is None:
        receiver_member = await ensure_member(
            session,
            chat_id,
            receiver_id,
        )

    await reconcile_member_state(
        session,
        sender_member,
    )

    await reconcile_member_state(
        session,
        receiver_member,
    )

    async with _BALANCE_LOCK:
        sender_member = await get_member(
            session,
            chat_id,
            sender_id,
        )

        if sender_member is None:
            sender_member = await ensure_member(
                session,
                chat_id,
                sender_id,
            )

        if sender_member.balance < amount:
            return ServiceResult(
                False,
                (
                    "❌ Недостаточно арахиса.\n"
                    f"Баланс: <b>{format_balance(sender_member.balance)}</b> 🥜\n"
                    f"Нужно: <b>{format_balance(amount)}</b> 🥜"
                ),
            )

        await _change_balance_unlocked(
            session,
            chat_id,
            sender_id,
            -amount,
            "transfer_out",
            f"Перевод пользователю {receiver_id}",
        )

        await _change_balance_unlocked(
            session,
            chat_id,
            receiver_id,
            amount,
            "transfer_in",
            f"Перевод от пользователя {sender_id}",
        )

    return ServiceResult(
        True,
        (
            "💸 Перевод выполнен.\n"
            f"Отправлено: "
            f"<b>{format_balance(amount)}</b> 🥜"
        ),
        changed=True,
    )


def game_unlocked(
    member: ChatMember,
    game_type: str,
) -> bool:
    required = get_feature_required_level(
        game_type
    )

    if required is None:
        return True

    return member.level >= required


async def prepare_game(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    game_type: str,
    bet: int,
) -> tuple[Optional[ChatMember], Optional[ServiceResult]]:
    error = valid_bet(bet)

    if error:
        return None, ServiceResult(
            False,
            error,
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

    await reconcile_member_state(
        session,
        member,
    )

    if not game_unlocked(
        member,
        game_type,
    ):
        required = get_feature_required_level(
            game_type
        )

        return member, ServiceResult(
            False,
            (
                "🔒 Игра открывается на "
                f"<b>{required} уровне</b>.\n"
                f"Твой уровень: "
                f"<b>{member.level}</b>."
            ),
        )

    if member.balance < bet:
        return member, ServiceResult(
            False,
            (
                "❌ Недостаточно арахиса.\n"
                f"Баланс: "
                f"<b>{format_balance(member.balance)}</b> 🥜\n"
                f"Нужно: "
                f"<b>{format_balance(bet)}</b> 🥜"
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
) -> Optional[int]:
    payout = (
        int(bet * multiplier)
        if won
        else 0
    )

    async with _BALANCE_LOCK:
        try:
            await _change_balance_unlocked(
                session,
                chat_id,
                user_id,
                -bet,
                "game_bet",
                f"Ставка: {game_type}",
            )
        except ValueError:
            return None

        if payout:
            await _change_balance_unlocked(
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
                finished_at=utcnow(),
            )
        )

        await session.flush()

    return payout


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
        [
            "Орёл",
            "Решка",
        ]
    )

    won = result == "Орёл"

    payout = await finish_game(
        session,
        chat_id,
        user_id,
        "coinflip",
        bet,
        result,
        1.95 if won else 0,
        won,
    )

    if payout is None:
        return ServiceResult(
            False,
            "❌ Не удалось завершить игру: баланс изменился. Попробуй ещё раз.",
            answer="Баланс изменился. Попробуй ещё раз.",
            show_alert=True,
        )

    return ServiceResult(
        True,
        (
            f"🪙 Выпало: <b>{result}</b>\n\n"
            + (
                f"🎉 Выплата: "
                f"<b>{format_balance(payout)}</b> 🥜"
                if won
                else "💀 Ставка проиграна."
            )
        ),
        changed=True,
    )


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

    first = RNG.randint(
        1,
        6,
    )

    second = RNG.randint(
        1,
        6,
    )

    total = first + second
    won = total >= 8

    payout = await finish_game(
        session,
        chat_id,
        user_id,
        "dice",
        bet,
        str(total),
        1.8 if won else 0,
        won,
    )

    if payout is None:
        return ServiceResult(
            False,
            "❌ Не удалось завершить игру: баланс изменился. Попробуй ещё раз.",
            answer="Баланс изменился. Попробуй ещё раз.",
            show_alert=True,
        )

    return ServiceResult(
        True,
        (
            f"🎲 {first} + {second} = "
            f"<b>{total}</b>\n\n"
            + (
                f"🏆 Выплата: "
                f"<b>{format_balance(payout)}</b> 🥜"
                if won
                else "💀 Проигрыш."
            )
        ),
        changed=True,
    )


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

    if result[0] == result[1] == result[2]:
        multiplier = {
            "7️⃣": 10.0,
            "💎": 7.0,
        }.get(
            result[0],
            5.0,
        )
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

    if payout is None:
        return ServiceResult(
            False,
            "❌ Не удалось завершить игру: баланс изменился. Попробуй ещё раз.",
            answer="Баланс изменился. Попробуй ещё раз.",
            show_alert=True,
        )

    return ServiceResult(
        True,
        (
            "🎰 <b>| "
            + " | ".join(result)
            + " |</b>\n\n"
            + (
                f"🎉 Выплата: "
                f"<b>{format_balance(payout)}</b> 🥜"
                if won
                else "💀 Не повезло."
            )
        ),
        changed=True,
    )


async def play_roulette(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    bet: int,
    choice: str,
) -> ServiceResult:
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

    _, error = await prepare_game(
        session,
        chat_id,
        user_id,
        "roulette",
        bet,
    )

    if error:
        return error

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
        27, 30, 32, 34, 36,
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

    if payout is None:
        return ServiceResult(
            False,
            "❌ Не удалось завершить игру: баланс изменился. Попробуй ещё раз.",
            answer="Баланс изменился. Попробуй ещё раз.",
            show_alert=True,
        )

    emoji = {
        "red": "🔴",
        "black": "⚫",
        "green": "🟢",
    }[color]

    return ServiceResult(
        True,
        (
            f"🎡 Выпало: "
            f"<b>{number}</b> {emoji}\n\n"
            + (
                f"🎉 Выплата: "
                f"<b>{format_balance(payout)}</b> 🥜"
                if won
                else "💀 Проигрыш."
            )
        ),
        changed=True,
    )


async def play_guess(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    bet: int,
    number: int,
) -> ServiceResult:
    if not 1 <= number <= 10:
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

    payout = await finish_game(
        session,
        chat_id,
        user_id,
        "guess",
        bet,
        f"{number}:{generated}",
        9.0 if won else 0,
        won,
    )

    if payout is None:
        return ServiceResult(
            False,
            "❌ Не удалось завершить игру: баланс изменился. Попробуй ещё раз.",
            answer="Баланс изменился. Попробуй ещё раз.",
            show_alert=True,
        )

    return ServiceResult(
        True,
        (
            f"🔢 Выпало: "
            f"<b>{generated}</b>\n\n"
            + (
                f"🎉 Выплата: "
                f"<b>{format_balance(payout)}</b> 🥜"
                if won
                else "💀 Не угадал."
            )
        ),
        changed=True,
    )


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

    payout = await finish_game(
        session,
        chat_id,
        user_id,
        "football",
        bet,
        result,
        FOOTBALL_MULTIPLIER if won else 0,
        won,
    )

    if payout is None:
        return ServiceResult(
            False,
            "❌ Не удалось завершить игру: баланс изменился. Попробуй ещё раз.",
            answer="Баланс изменился. Попробуй ещё раз.",
            show_alert=True,
        )

    return ServiceResult(
        True,
        (
            f"⚽ <b>{result}</b>\n\n"
            + (
                f"🏆 Выплата: "
                f"<b>{format_balance(payout)}</b> 🥜"
                if won
                else "💀 Ставка проиграна."
            )
        ),
        changed=True,
    )


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

    won = result != "🧱 Мимо!"

    payout = await finish_game(
        session,
        chat_id,
        user_id,
        "basketball",
        bet,
        result,
        BASKETBALL_MULTIPLIER if won else 0,
        won,
    )

    if payout is None:
        return ServiceResult(
            False,
            "❌ Не удалось завершить игру: баланс изменился. Попробуй ещё раз.",
            answer="Баланс изменился. Попробуй ещё раз.",
            show_alert=True,
        )

    return ServiceResult(
        True,
        (
            f"🏀 <b>{result}</b>\n\n"
            + (
                f"🏆 Выплата: "
                f"<b>{format_balance(payout)}</b> 🥜"
                if won
                else "💀 Мимо."
            )
        ),
        changed=True,
    )


def _blackjack_card_value(
    rank: str,
) -> int:
    if rank in {
        "J",
        "Q",
        "K",
    }:
        return 10

    if rank == "A":
        return 11

    return int(rank)


def _blackjack_hand_value(
    hand: list[str],
) -> int:
    total = sum(
        _blackjack_card_value(card[:-1])
        for card in hand
    )

    aces = sum(
        1
        for card in hand
        if card[:-1] == "A"
    )

    while total > 21 and aces:
        total -= 10
        aces -= 1

    return total


def _blackjack_card_text(
    card: str,
) -> str:
    rank = card[:-1]
    suit = card[-1]

    return f"{rank}{suit}"


async def play_blackjack(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    bet: int,
) -> ServiceResult:
    if bet < BLACKJACK_MIN_BET:
        return ServiceResult(
            False,
            (
                "❌ Минимальная ставка Blackjack — "
                f"<b>{format_balance(BLACKJACK_MIN_BET)}</b> 🥜."
            ),
        )

    _, error = await prepare_game(
        session,
        chat_id,
        user_id,
        "blackjack",
        bet,
    )

    if error:
        return error

    ranks = [
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
        "8",
        "9",
        "10",
        "J",
        "Q",
        "K",
        "A",
    ]

    suits = [
        "♠",
        "♥",
        "♦",
        "♣",
    ]

    deck = [
        f"{rank}{suit}"
        for rank in ranks
        for suit in suits
    ]

    RNG.shuffle(deck)

    player = [
        deck.pop(),
        deck.pop(),
    ]

    dealer = [
        deck.pop(),
        deck.pop(),
    ]

    player_total = _blackjack_hand_value(
        player
    )

    dealer_total = _blackjack_hand_value(
        dealer
    )

    player_natural = (
        len(player) == 2
        and player_total == 21
    )

    dealer_natural = (
        len(dealer) == 2
        and dealer_total == 21
    )

    while (
        player_total < 17
        and player_total <= 21
    ):
        player.append(
            deck.pop()
        )
        player_total = _blackjack_hand_value(
            player
        )

    while (
        dealer_total < 17
        and dealer_total <= 21
    ):
        dealer.append(
            deck.pop()
        )
        dealer_total = _blackjack_hand_value(
            dealer
        )

    won = False
    draw = False
    multiplier = 0.0

    if player_natural and dealer_natural:
        draw = True

    elif player_natural:
        won = True
        multiplier = BLACKJACK_NATURAL_MULTIPLIER

    elif player_total > 21:
        won = False

    elif dealer_total > 21:
        won = True
        multiplier = BLACKJACK_WIN_MULTIPLIER

    elif player_total > dealer_total:
        won = True
        multiplier = BLACKJACK_WIN_MULTIPLIER

    elif player_total == dealer_total:
        draw = True

    else:
        won = False

    if draw and BLACKJACK_DRAW_REFUND:
        try:
            await _change_balance_unlocked(
                session,
                chat_id,
                user_id,
                -bet,
                "game_bet",
                "Ставка: blackjack",
            )

            await _change_balance_unlocked(
                session,
                chat_id,
                user_id,
                bet,
                "game_payout",
                "Возврат ставки: blackjack",
            )
        except ValueError:
            return ServiceResult(
                False,
                "❌ Не удалось завершить игру: баланс изменился. Попробуй ещё раз.",
                answer="Баланс изменился. Попробуй ещё раз.",
                show_alert=True,
            )

        member = await get_member(
            session,
            chat_id,
            user_id,
        )

        if member:
            member.games_played += 1

        session.add(
            Game(
                chat_id=chat_id,
                user_id=user_id,
                game_type="blackjack",
                bet=bet,
                result=(
                    f"player:{player_total};"
                    f"dealer:{dealer_total};draw"
                ),
                multiplier=1.0,
                payout=bet,
                won=False,
                status="finished",
                finished_at=utcnow(),
            )
        )

        await session.flush()

        return ServiceResult(
            True,
            (
                "🃏 <b>Blackjack</b>\n\n"
                f"Твои карты: "
                f"<b>{' '.join(_blackjack_card_text(card) for card in player)}</b>\n"
                f"Твой счёт: <b>{player_total}</b>\n"
                f"Карты дилера: "
                f"<b>{' '.join(_blackjack_card_text(card) for card in dealer)}</b>\n"
                f"Счёт дилера: <b>{dealer_total}</b>\n\n"
                "🤝 Ничья. Ставка возвращена."
            ),
            changed=True,
        )

    payout = await finish_game(
        session,
        chat_id,
        user_id,
        "blackjack",
        bet,
        (
            f"player:{player_total};"
            f"dealer:{dealer_total};"
            f"{'win' if won else 'loss'}"
        ),
        multiplier,
        won,
    )

    if payout is None:
        return ServiceResult(
            False,
            "❌ Не удалось завершить игру: баланс изменился. Попробуй ещё раз.",
            answer="Баланс изменился. Попробуй ещё раз.",
            show_alert=True,
        )

    return ServiceResult(
        True,
        (
            "🃏 <b>Blackjack</b>\n\n"
            f"Твои карты: "
            f"<b>{' '.join(_blackjack_card_text(card) for card in player)}</b>\n"
            f"Твой счёт: <b>{player_total}</b>\n"
            f"Карты дилера: "
            f"<b>{' '.join(_blackjack_card_text(card) for card in dealer)}</b>\n"
            f"Счёт дилера: <b>{dealer_total}</b>\n\n"
            + (
                f"🎉 Выплата: "
                f"<b>{format_balance(payout)}</b> 🥜"
                if won
                else "💀 Ставка проиграна."
            )
        ),
        changed=True,
    )


async def play_crash(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    bet: int,
    cashout_multiplier: float = 2.0,
) -> ServiceResult:
    if bet < CRASH_MIN_BET:
        return ServiceResult(
            False,
            (
                "❌ Минимальная ставка Crash — "
                f"<b>{format_balance(CRASH_MIN_BET)}</b> 🥜."
            ),
        )

    try:
        cashout_multiplier = float(
            cashout_multiplier
        )
    except (
        TypeError,
        ValueError,
    ):
        return ServiceResult(
            False,
            "❌ Некорректный множитель вывода.",
        )

    cashout_multiplier = round(
        cashout_multiplier,
        2,
    )

    if not (
        CRASH_MIN_MULTIPLIER
        <= cashout_multiplier
        <= CRASH_MAX_MULTIPLIER
    ):
        return ServiceResult(
            False,
            (
                "❌ Множитель вывода должен быть от "
                f"<b>{CRASH_MIN_MULTIPLIER:.2f}x</b> "
                f"до <b>{CRASH_MAX_MULTIPLIER:.2f}x</b>."
            ),
        )

    _, error = await prepare_game(
        session,
        chat_id,
        user_id,
        "crash",
        bet,
    )

    if error:
        return error

    random_value = max(
        RNG.random(),
        0.0001,
    )

    crash_multiplier = 1.0 / random_value

    crash_multiplier = min(
        CRASH_MAX_MULTIPLIER,
        max(
            CRASH_MIN_MULTIPLIER,
            crash_multiplier,
        ),
    )

    crash_multiplier = round(
        crash_multiplier,
        2,
    )

    won = (
        cashout_multiplier
        <= crash_multiplier
    )

    payout = await finish_game(
        session,
        chat_id,
        user_id,
        "crash",
        bet,
        (
            f"crash:{crash_multiplier:.2f};"
            f"cashout:{cashout_multiplier:.2f}"
        ),
        cashout_multiplier if won else 0.0,
        won,
    )

    if payout is None:
        return ServiceResult(
            False,
            "❌ Не удалось завершить игру: баланс изменился. Попробуй ещё раз.",
            answer="Баланс изменился. Попробуй ещё раз.",
            show_alert=True,
        )

    if won:
        result_text = (
            f"🚀 <b>Crash</b>\n\n"
            f"💥 Краш произошёл на: "
            f"<b>{crash_multiplier:.2f}x</b>\n"
            f"🎯 Твой вывод: "
            f"<b>{cashout_multiplier:.2f}x</b>\n\n"
            f"🎉 Выплата: "
            f"<b>{format_balance(payout)}</b> 🥜"
        )
    else:
        result_text = (
            f"🚀 <b>Crash</b>\n\n"
            f"💥 Краш произошёл на: "
            f"<b>{crash_multiplier:.2f}x</b>\n"
            f"🎯 Твой вывод: "
            f"<b>{cashout_multiplier:.2f}x</b>\n\n"
            "💀 Ставка проиграна."
        )

    return ServiceResult(
        True,
        result_text,
        changed=True,
    )


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
        "blackjack": play_blackjack,
        "crash": play_crash,
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
    bet: int = TICTACTOE_MIN_BET,
) -> ServiceResult:
    if bet < TICTACTOE_MIN_BET:
        return ServiceResult(
            False,
            (
                "❌ Минимальная ставка TTT — "
                f"{TICTACTOE_MIN_BET} 🥜."
            ),
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

    await reconcile_member_state(
        session,
        member,
    )

    required_level = (
        get_feature_required_level(
            "tictactoe"
        )
        or 10
    )

    if member.level < required_level:
        return ServiceResult(
            False,
            (
                "🔒 Крестики-нолики открываются "
                f"на <b>{required_level} уровне</b>."
            ),
        )

    async with _TTT_LOCK:
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

        await reconcile_member_state(
            session,
            member,
        )

        if member.balance < bet:
            return ServiceResult(
                False,
                (
                    "❌ Недостаточно арахиса.\n"
                    f"Баланс: "
                    f"<b>{format_balance(member.balance)}</b> 🥜\n"
                    f"Нужно: "
                    f"<b>{format_balance(bet)}</b> 🥜"
                ),
            )

        existing = await session.execute(
            select(TicTacToeGame).where(
                TicTacToeGame.chat_id == chat_id,
                TicTacToeGame.status.in_(
                    [
                        "waiting",
                        "playing",
                    ]
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

        await _change_balance_unlocked(
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
            f"Ставка: "
            f"<b>{format_balance(bet)}</b> 🥜\n\n"
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
    async with _TTT_LOCK:
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

        target_member = await get_member(
            session,
            game.chat_id,
            user_id,
        )

        if target_member is None:
            target_member = await ensure_member(
                session,
                game.chat_id,
                user_id,
            )

        await reconcile_member_state(
            session,
            target_member,
        )

        if target_member.balance < game.bet:
            return ServiceResult(
                False,
                (
                    "❌ Недостаточно арахиса.\n"
                    f"Баланс: "
                    f"<b>{format_balance(target_member.balance)}</b> 🥜\n"
                    f"Нужно: "
                    f"<b>{format_balance(game.bet)}</b> 🥜"
                ),
                answer="Недостаточно арахиса.",
                show_alert=True,
            )

        game.player_o_id = user_id
        game.current_player_id = (
            game.player_x_id
        )
        game.status = "playing"

        await _change_balance_unlocked(
            session,
            game.chat_id,
            user_id,
            -game.bet,
            "ttt_bet",
            "Ставка в крестики-нолики",
        )

        await session.flush()

    return ServiceResult(
        True,
        (
            "⭕❌ <b>Игра началась!</b>\n\n"
            f"Ставка: "
            f"<b>{format_balance(game.bet)}</b> 🥜\n"
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
    async with _TTT_LOCK:
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

        if user_id not in {
            game.player_x_id,
            game.player_o_id,
        }:
            return ServiceResult(
                False,
                "❌ Ты не участник этой игры.",
                answer="Ты не участник.",
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

        board = list(game.board)

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

                if TICTACTOE_DRAW_REFUND:
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

                player_x = await get_member(
                    session,
                    game.chat_id,
                    game.player_x_id,
                )

                player_o = await get_member(
                    session,
                    game.chat_id,
                    game.player_o_id,
                ) if game.player_o_id else None

                if player_x:
                    await reconcile_member_state(
                        session,
                        player_x,
                    )
                    player_x.games_played += 1

                if player_o:
                    await reconcile_member_state(
                        session,
                        player_o,
                    )
                    player_o.games_played += 1

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
                        int(
                            game.bet
                            * TICTACTOE_WIN_MULTIPLIER
                        ),
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
                    await reconcile_member_state(
                        session,
                        winner_member,
                    )

                    winner_member.games_played += 1
                    winner_member.games_won += 1
                    winner_member.total_won += game.bet

                if loser_member:
                    await reconcile_member_state(
                        session,
                        loser_member,
                    )

                    loser_member.games_played += 1
                    loser_member.games_lost += 1
                    loser_member.total_lost += game.bet

                text = (
                    "⭕❌ <b>Игра окончена!</b>\n\n"
                    "Победитель: "
                    f'<a href="tg://user?id={winner_id}">'
                    "игрок</a> 🎉\n"
                    "🏆 Выигрыш: "
                    f"<b>{format_balance(game.bet * 2)}</b> 🥜"
                )

            game.updated_at = utcnow()

            await session.flush()

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

        game.updated_at = utcnow()

        await session.flush()

        return ServiceResult(
            True,
            (
                "⭕❌ <b>Крестики-нолики</b>\n\n"
                f"Ход: {current_symbol}"
            ),
            changed=True,
            keyboard=ttt_keyboard(game),
        )


async def perform_rp(
    session: AsyncSession,
    chat_id: int,
    actor_id: int,
    action: str,
    target_id: Optional[int] = None,
    target_name: Optional[str] = None,
) -> ServiceResult:
    normalized = normalize_text(
        action.replace("_", " ")
    )

    adult_action = get_adult_rp_action(
        normalized
    )

    if adult_action is not None:
        return await perform_adult_rp(
            session,
            chat_id,
            actor_id,
            normalized,
            target_id,
            target_name,
        )

    matched = None

    for key, data in RP_ACTIONS.items():
        for alias in data.get(
            "aliases",
            (),
        ):
            if normalize_text(
                str(alias)
            ) == normalized:
                matched = (
                    key,
                    data,
                )
                break

        if matched:
            break

    if matched is None:
        return ServiceResult(
            False,
            "❌ Неизвестная RP-команда.",
        )

    key, data = matched

    if target_id is None:
        return ServiceResult(
            False,
            "❌ Укажи пользователя через reply или @username.",
        )

    if actor_id == target_id:
        return ServiceResult(
            False,
            "😐 На себя RP-команды использовать нельзя.",
        )

    target_user = await session.get(
        User,
        target_id,
    )

    if target_user is None:
        return ServiceResult(
            False,
            "❌ Пользователь не найден.",
        )

    actor_member = await get_member(
        session,
        chat_id,
        actor_id,
    )

    if actor_member is None:
        actor_member = await ensure_member(
            session,
            chat_id,
            actor_id,
        )

    await reconcile_member_state(
        session,
        actor_member,
    )

    target_member = await get_member(
        session,
        chat_id,
        target_id,
    )

    if target_member is not None:
        await reconcile_member_state(
            session,
            target_member,
        )

    _, error = await can_afford(
        session,
        chat_id,
        actor_id,
        NORMAL_RP_COST,
    )

    if error:
        return ServiceResult(
            False,
            error,
        )

    try:
        await change_balance(
            session,
            chat_id,
            actor_id,
            -NORMAL_RP_COST,
            "rp",
            f"Обычный RP: {key}",
        )
    except ValueError:
        return ServiceResult(
            False,
            "❌ Баланс изменился. Попробуй ещё раз.",
            answer="Баланс изменился. Попробуй ещё раз.",
            show_alert=True,
        )

    actor = await session.get(
        User,
        actor_id,
    )

    actor_name = clean_name(actor)

    if target_name is None:
        target_name = clean_name(
            target_user
        )

    emoji = str(
        data.get(
            "emoji",
            "🎭",
        )
    )

    verb = str(
        data.get(
            "verb",
            key,
        )
    )

    return ServiceResult(
        True,
        (
            f"{emoji} "
            f"{user_mention(actor_id, actor_name)} "
            f"<b>{verb}</b> "
            f"{target_name}\n\n"
            f"💸 Стоимость: "
            f"<b>{NORMAL_RP_COST}</b> 🥜"
        ),
        changed=True,
    )


async def perform_adult_rp(
    session: AsyncSession,
    chat_id: int,
    actor_id: int,
    action: str,
    target_id: Optional[int] = None,
    target_name: Optional[str] = None,
) -> ServiceResult:
    adult_action = get_adult_rp_action(
        normalize_text(action)
    )

    if adult_action is None:
        return ServiceResult(
            False,
            "❌ Неизвестная 18+ RP-команда.",
        )

    if target_id is None:
        return ServiceResult(
            False,
            "❌ Укажи пользователя через reply или @username.",
        )

    if actor_id == target_id:
        return ServiceResult(
            False,
            "😐 На себя это действие использовать нельзя.",
        )

    actor_member = await get_member(
        session,
        chat_id,
        actor_id,
    )

    target_member = await get_member(
        session,
        chat_id,
        target_id,
    )

    if actor_member is None:
        actor_member = await ensure_member(
            session,
            chat_id,
            actor_id,
        )

    if target_member is None:
        target_member = await ensure_member(
            session,
            chat_id,
            target_id,
        )

    await reconcile_member_state(
        session,
        actor_member,
    )

    await reconcile_member_state(
        session,
        target_member,
    )

    now = utcnow()

    if actor_member.has_child:
        if (
            actor_member.child_until is not None
            and actor_member.child_until <= now
        ):
            actor_member.has_child = False
            actor_member.child_until = None
            actor_member.last_child_support = None

        else:
            return ServiceResult(
                False,
                (
                    "👶 Пока активен эффект ребёнка, "
                    "18+ RP недоступен."
                ),
            )

    cooldown = ADULT_RP_COOLDOWN

    rubber = await _has_item(
        session,
        chat_id,
        actor_id,
        RUBBER_PUSSY_ITEM_CODE,
    )

    if rubber:
        cooldown *= RUBBER_PUSSY_COOLDOWN_MULTIPLIER

    remaining = cooldown_remaining(
        actor_member.last_adult_rp_at,
        cooldown,
    )

    if remaining:
        return ServiceResult(
            False,
            (
                "⏳ 18+ RP пока на cooldown.\n"
                f"Осталось: "
                f"<b>{format_seconds(remaining)}</b>."
            ),
        )

    _, error = await can_afford(
        session,
        chat_id,
        actor_id,
        ADULT_RP_COST,
    )

    if error:
        return ServiceResult(
            False,
            error,
        )

    try:
        await change_balance(
            session,
            chat_id,
            actor_id,
            -ADULT_RP_COST,
            "adult_rp",
            f"18+ RP: {adult_action.key}",
        )
    except ValueError:
        return ServiceResult(
            False,
            "❌ Баланс изменился. Попробуй ещё раз.",
            answer="Баланс изменился. Попробуй ещё раз.",
            show_alert=True,
        )

    actor_gain = (
        RNG.uniform(
            ADULT_RP_SIZE_GAIN_MIN,
            ADULT_RP_SIZE_GAIN_MAX,
        )
        * adult_action.actor_size_multiplier
    )

    target_loss = (
        RNG.uniform(
            ADULT_RP_TARGET_SIZE_LOSS_MIN,
            ADULT_RP_TARGET_SIZE_LOSS_MAX,
        )
        * adult_action.target_size_multiplier
    )

    lubricant = None

    if adult_action.can_use_lubricant:
        lubricant = await _has_item(
            session,
            chat_id,
            actor_id,
            LUBRICANT_ITEM_CODE,
        )

        if lubricant:
            actor_gain *= (
                1.0 + LUBRICANT_GROWTH_BONUS
            )

            await _consume_user_item(
                session,
                lubricant,
            )

    actor_member.penis_size = round(
        max(
            0,
            actor_member.penis_size
            + actor_gain,
        ),
        2,
    )

    target_member.penis_size = round(
        max(
            0,
            target_member.penis_size
            - target_loss,
        ),
        2,
    )

    actor_member.last_adult_rp_at = now

    condom = await _has_item(
        session,
        chat_id,
        actor_id,
        CONDOM_ITEM_CODE,
    )

    if condom:
        await _consume_user_item(
            session,
            condom,
        )

    disease_chance = DISEASE_CONTRACT_CHANCE

    if condom:
        disease_chance *= (
            1 - CONDOM_DISEASE_PROTECTION_CHANCE
        )

    if (
        target_member.has_disease
        and RNG.random() < disease_chance
    ):
        actor_member.has_disease = True
        actor_member.disease_since = now
        actor_member.next_disease_tick = (
            now + timedelta(hours=1)
        )

    impregnation_chance = (
        IMPREGNATION_CHANCE_WITH_CONDOM
        if condom
        else IMPREGNATION_CHANCE_WITHOUT_CONDOM
    )

    child_triggered = (
        RNG.random()
        < impregnation_chance
    )

    if child_triggered:
        actor_member.has_child = True
        actor_member.child_until = (
            now + timedelta(
                hours=CHILD_DURATION_HOURS
            )
        )
        actor_member.last_child_support = now

    actor = await session.get(
        User,
        actor_id,
    )

    target = await session.get(
        User,
        target_id,
    )

    if target_name is None:
        target_name = clean_name(
            target
        )

    extra = ""

    if child_triggered:
        extra += (
            "\n👶 Сработал игровой эффект ребёнка."
        )

    if actor_member.has_disease:
        extra += (
            "\n🦠 У тебя есть риск болезни."
        )

    rubber_growth = await reconcile_rubber_pussy_daily(
        session,
        actor_member,
    )

    if rubber_growth:
        extra += (
            "\n🧸 Rubber Pussy: "
            f"+{rubber_growth:.2f} см за день."
        )

    await session.flush()

    return ServiceResult(
        True,
        (
            f"{adult_action.emoji} "
            f"{user_mention(actor_id, clean_name(actor))} "
            f"<b>{escape(adult_action.key)}</b> "
            f"{target_name}\n\n"
            f"📏 Твой размер: "
            f"<b>{actor_member.penis_size:.2f} см</b>\n"
            f"📉 Размер цели: "
            f"<b>{target_member.penis_size:.2f} см</b>\n"
            f"💸 Стоимость: "
            f"<b>{ADULT_RP_COST}</b> 🥜"
            f"{extra}"
        ),
        changed=True,
    )


async def masturbate(
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

    await reconcile_member_state(
        session,
        member,
    )

    now = utcnow()

    dildo = await _has_item(
        session,
        chat_id,
        user_id,
        DILDO_ITEM_CODE,
    )

    dildo_available = bool(
        dildo
        and dildo.uses_left is not None
        and dildo.uses_left > 0
    )

    cooldown = MASTURBATION_COOLDOWN

    rubber = await _has_item(
        session,
        chat_id,
        user_id,
        RUBBER_PUSSY_ITEM_CODE,
    )

    if rubber:
        cooldown *= (
            RUBBER_PUSSY_COOLDOWN_MULTIPLIER
        )

    if not dildo_available:
        remaining = cooldown_remaining(
            member.last_masturbation_at,
            cooldown,
        )

        if remaining:
            return ServiceResult(
                False,
                (
                    "⏳ Команда пока недоступна.\n"
                    f"Осталось: "
                    f"<b>{format_seconds(remaining)}</b>."
                ),
            )

    gain = (
        RNG.uniform(
            RUBBER_PUSSY_MASTURBATION_MIN,
            RUBBER_PUSSY_MASTURBATION_MAX,
        )
        if rubber
        else RNG.uniform(
            MASTURBATION_MIN_GAIN,
            MASTURBATION_MAX_GAIN,
        )
    )

    extra = ""

    if dildo_available and dildo is not None:
        await _consume_user_item(
            session,
            dildo,
        )

        extra = (
            "\n🪀 Использован Dildo."
        )

    member.penis_size = round(
        max(
            0,
            member.penis_size + gain,
        ),
        2,
    )

    member.last_masturbation_at = now

    rubber_growth = await reconcile_rubber_pussy_daily(
        session,
        member,
    )

    if rubber_growth:
        extra += (
            "\n🧸 Rubber Pussy: "
            f"+{rubber_growth:.2f} см за день."
        )

    await session.flush()

    dildo_left = None

    if dildo_available:
        updated_dildo = await _has_item(
            session,
            chat_id,
            user_id,
            DILDO_ITEM_CODE,
        )

        if updated_dildo is not None:
            dildo_left = updated_dildo.uses_left

    if (
        dildo_available
        and dildo_left is not None
    ):
        extra += (
            "\n🪀 Осталось использований Dildo: "
            f"<b>{dildo_left}</b>"
        )

    return ServiceResult(
        True,
        (
            "😏 Действие выполнено.\n"
            f"📏 Размер: "
            f"<b>{member.penis_size:.2f} см</b>"
            f"\n📈 Рост: "
            f"<b>+{gain:.2f} см</b>"
            f"{extra}"
        ),
        changed=True,
    )


async def rob_user(
    session: AsyncSession,
    chat_id: int,
    actor_id: int,
    target_id: int,
) -> ServiceResult:
    if actor_id == target_id:
        return ServiceResult(
            False,
            "😐 Себя грабить нельзя.",
        )

    actor = await get_member(
        session,
        chat_id,
        actor_id,
    )

    target = await get_member(
        session,
        chat_id,
        target_id,
    )

    if actor is None or target is None:
        return ServiceResult(
            False,
            "❌ Пользователь не найден.",
        )

    await reconcile_member_state(
        session,
        actor,
    )

    await reconcile_member_state(
        session,
        target,
    )

    remaining = cooldown_remaining(
        actor.last_rob_at,
        ROB_COOLDOWN_SECONDS,
    )

    if remaining:
        return ServiceResult(
            False,
            (
                "⏳ Ограбление на cooldown.\n"
                f"Осталось: "
                f"<b>{format_seconds(remaining)}</b>."
            ),
        )

    if actor.penis_size <= target.penis_size:
        return ServiceResult(
            False,
            (
                "❌ Ограбить можно только "
                "пользователя с меньшим размером."
            ),
        )

    if target.balance <= 0:
        return ServiceResult(
            False,
            "❌ У цели нет арахиса.",
        )

    chance = RNG.uniform(
        ROB_MIN_SUCCESS_CHANCE,
        ROB_MAX_SUCCESS_CHANCE,
    )

    actor.last_rob_at = utcnow()

    if RNG.random() > chance:
        await session.flush()

        return ServiceResult(
            True,
            "🥷 Ограбление провалилось.",
            changed=True,
        )

    percent = RNG.uniform(
        ROB_MIN_REWARD_PERCENT,
        ROB_MAX_REWARD_PERCENT,
    )

    amount = max(
        1,
        int(
            target.balance
            * percent
        ),
    )

    amount = min(
        amount,
        target.balance,
    )

    try:
        async with _BALANCE_LOCK:
            await _change_balance_unlocked(
                session,
                chat_id,
                target.user_id,
                -amount,
                "rob_loss",
                f"Ограбление пользователем {actor_id}",
            )

            await _change_balance_unlocked(
                session,
                chat_id,
                actor_id,
                amount,
                "rob_reward",
                f"Ограбление пользователя {target_id}",
            )
    except ValueError:
        return ServiceResult(
            False,
            "❌ Баланс цели изменился. Попробуй ещё раз.",
            answer="Баланс цели изменился. Попробуй ещё раз.",
            show_alert=True,
        )

    return ServiceResult(
        True,
        (
            "🥷 Ограбление успешно!\n"
            f"💰 Получено: "
            f"<b>{format_balance(amount)}</b> 🥜"
        ),
        changed=True,
    )


async def reconcile_disease(
    session: AsyncSession,
    member: ChatMember,
) -> None:
    if not member.has_disease:
        return

    now = utcnow()

    if member.next_disease_tick is None:
        member.next_disease_tick = (
            now + timedelta(hours=1)
        )
        return

    ticks = 0

    while (
        member.next_disease_tick <= now
        and ticks < 24
    ):
        member.penis_size = round(
            max(
                0,
                member.penis_size
                - DISEASE_SIZE_LOSS_PER_TICK,
            ),
            2,
        )

        charge = min(
            DISEASE_TICK_COST,
            max(
                0,
                member.balance,
            ),
        )

        if charge > 0:
            await change_balance(
                session,
                member.chat_id,
                member.user_id,
                -charge,
                "disease_tick",
                "Ежечасный расход при болезни",
            )

        member.next_disease_tick += timedelta(
            hours=1
        )

        ticks += 1


async def use_medicine(
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
        return ServiceResult(
            False,
            "❌ Профиль не найден.",
        )

    await reconcile_disease(
        session,
        member,
    )

    if not member.has_disease:
        return ServiceResult(
            False,
            "🧼 Болезни нет.",
        )

    _, error = await can_afford(
        session,
        chat_id,
        user_id,
        DISEASE_MEDICINE_COST,
    )

    if error:
        return ServiceResult(
            False,
            error,
        )

    try:
        await change_balance(
            session,
            chat_id,
            user_id,
            -DISEASE_MEDICINE_COST,
            "medicine",
            "Лекарство",
        )
    except ValueError:
        return ServiceResult(
            False,
            "❌ Баланс изменился. Попробуй ещё раз.",
            answer="Баланс изменился. Попробуй ещё раз.",
            show_alert=True,
        )

    member.has_disease = False
    member.disease_since = None
    member.next_disease_tick = None

    await session.flush()

    return ServiceResult(
        True,
        "💊 Лекарство использовано. Болезнь снята.",
        changed=True,
    )


async def visit_venereologist(
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
        return ServiceResult(
            False,
            "❌ Профиль не найден.",
        )

    await reconcile_disease(
        session,
        member,
    )

    if not member.has_disease:
        return ServiceResult(
            False,
            "🧑‍⚕️ Болезни нет.",
        )

    _, error = await can_afford(
        session,
        chat_id,
        user_id,
        VENEREOLOGIST_COST,
    )

    if error:
        return ServiceResult(
            False,
            error,
        )

    try:
        await change_balance(
            session,
            chat_id,
            user_id,
            -VENEREOLOGIST_COST,
            "venereologist",
            "Венеролог",
        )
    except ValueError:
        return ServiceResult(
            False,
            "❌ Баланс изменился. Попробуй ещё раз.",
            answer="Баланс изменился. Попробуй ещё раз.",
            show_alert=True,
        )

    if RNG.random() < VENEREOLOGIST_CURE_CHANCE:
        member.has_disease = False
        member.disease_since = None
        member.next_disease_tick = None

        return ServiceResult(
            True,
            "🧑‍⚕️ Лечение прошло успешно. Болезнь снята.",
            changed=True,
        )

    return ServiceResult(
        True,
        "🧑‍⚕️ Лечение не помогло. Попробуй ещё раз позже.",
        changed=True,
    )


async def reconcile_child(
    session: AsyncSession,
    member: ChatMember,
) -> None:
    if not member.has_child:
        return

    now = utcnow()

    if member.last_child_support is None:
        member.last_child_support = now

    support_until = now

    if member.child_until is not None:
        support_until = min(
            support_until,
            member.child_until,
        )

    elapsed_seconds = (
        support_until - member.last_child_support
    ).total_seconds()

    elapsed_hours = int(
        max(
            0,
            elapsed_seconds,
        )
        // 3600
    )

    for _ in range(elapsed_hours):
        charge = min(
            CHILD_SUPPORT_COST,
            max(
                0,
                member.balance,
            ),
        )

        if charge > 0:
            await change_balance(
                session,
                member.chat_id,
                member.user_id,
                -charge,
                "child_support",
                "Содержание ребёнка",
            )

        member.last_child_support += timedelta(
            hours=1
        )

    if (
        member.child_until is not None
        and member.child_until <= now
    ):
        member.has_child = False
        member.child_until = None
        member.last_child_support = None


async def child_status(
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
        return ServiceResult(
            False,
            "❌ Профиль не найден.",
        )

    await reconcile_child(
        session,
        member,
    )

    if not member.has_child:
        return ServiceResult(
            True,
            "👶 Активного ребёнка нет.",
        )

    remaining = 0

    if member.child_until:
        remaining = max(
            0,
            int(
                (
                    member.child_until
                    - utcnow()
                ).total_seconds()
            ),
        )

    return ServiceResult(
        True,
        (
            "👶 <b>Ребёнок</b>\n\n"
            f"Осталось: "
            f"<b>{format_seconds(remaining)}</b>\n"
            f"Содержание: "
            f"<b>{format_balance(CHILD_SUPPORT_COST)}</b> 🥜/час."
        ),
    )


async def abort_child(
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
        return ServiceResult(
            False,
            "❌ Профиль не найден.",
        )

    await reconcile_child(
        session,
        member,
    )

    if not member.has_child:
        return ServiceResult(
            False,
            "👶 Активного ребёнка нет.",
        )

    _, error = await can_afford(
        session,
        chat_id,
        user_id,
        ABORT_COST_VALUE,
    )

    if error:
        return ServiceResult(
            False,
            error,
        )

    try:
        await change_balance(
            session,
            chat_id,
            user_id,
            -ABORT_COST_VALUE,
            "abort",
            "Игровой аборт",
        )
    except ValueError:
        return ServiceResult(
            False,
            "❌ Баланс изменился. Попробуй ещё раз.",
            answer="Баланс изменился. Попробуй ещё раз.",
            show_alert=True,
        )

    if RNG.random() >= ABORT_SUCCESS_CHANCE:
        return ServiceResult(
            True,
            "❌ Процедура не сработала.",
            changed=True,
        )

    member.has_child = False
    member.child_until = None
    member.last_child_support = None

    return ServiceResult(
        True,
        "🏥 Игровой эффект ребёнка снят.",
        changed=True,
    )


def role_power_value(
    role: Optional[str],
) -> int:
    if role is None:
        return 0

    return ROLE_POWER.get(
        role,
        0,
    )


async def effective_role(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
) -> Optional[str]:
    if user_id == config.owner_id:
        return ROLE_OWNER

    return await get_staff_role(
        session,
        chat_id,
        user_id,
    )


async def check_moderation_access(
    session: AsyncSession,
    chat_id: int,
    actor_id: int,
    command: str,
) -> tuple[bool, Optional[str]]:
    role = await effective_role(
        session,
        chat_id,
        actor_id,
    )

    permission = await session.execute(
        select(ModPermission).where(
            ModPermission.chat_id == chat_id,
            ModPermission.command == command,
        )
    )

    row = permission.scalar_one_or_none()

    required = (
        row.scope.lower()
        if row
        else DEFAULT_MODERATION_PERMISSIONS.get(
            command,
            PERMISSION_STAFF,
        )
    )

    if not can_use_moderation_command(
        role,
        required,
    ):
        return (
            False,
            (
                "❌ Недостаточно прав.\n"
                f"Требуется уровень: "
                f"<b>{required}</b>."
            ),
        )

    return True, None


async def assign_staff_role(
    session: AsyncSession,
    chat_id: int,
    actor_id: int,
    target_id: int,
    role: str,
) -> ServiceResult:
    if role not in {
        ROLE_HEAD_ADMIN,
        ROLE_ADMIN,
        ROLE_MODERATOR,
    }:
        return ServiceResult(
            False,
            "❌ Недопустимая роль.",
        )

    actor_role = await effective_role(
        session,
        chat_id,
        actor_id,
    )

    if not can_manage_role(
        actor_role,
        role,
    ):
        return ServiceResult(
            False,
            "❌ У тебя нет права назначать эту роль.",
        )

    target_role = await effective_role(
        session,
        chat_id,
        target_id,
    )

    if target_role == ROLE_OWNER:
        return ServiceResult(
            False,
            "❌ Владельца изменить нельзя.",
        )

    if (
        target_role
        and role_power_value(target_role)
        >= role_power_value(actor_role)
    ):
        return ServiceResult(
            False,
            "❌ Нельзя изменить роль пользователя выше или равного себе.",
        )

    staff = await get_staff_member(
        session,
        chat_id,
        target_id,
    )

    if staff is None:
        staff = StaffMember(
            chat_id=chat_id,
            user_id=target_id,
            role=role,
            appointed_by=actor_id,
        )

        session.add(staff)

    else:
        staff.role = role
        staff.appointed_by = actor_id
        staff.updated_at = utcnow()

    await session.flush()

    return ServiceResult(
        True,
        (
            f"🛡 Пользователь "
            f"<code>{target_id}</code> назначен: "
            f"<b>{role}</b>."
        ),
        changed=True,
    )


async def remove_staff_role(
    session: AsyncSession,
    chat_id: int,
    actor_id: int,
    target_id: int,
) -> ServiceResult:
    actor_role = await effective_role(
        session,
        chat_id,
        actor_id,
    )

    staff = await get_staff_member(
        session,
        chat_id,
        target_id,
    )

    if staff is None:
        return ServiceResult(
            False,
            "❌ У пользователя нет staff-роли.",
        )

    if not can_manage_role(
        actor_role,
        staff.role,
    ):
        return ServiceResult(
            False,
            "❌ У тебя нет права снять эту роль.",
        )

    await session.delete(
        staff
    )

    return ServiceResult(
        True,
        (
            "🛡 Роль пользователя "
            f"<code>{target_id}</code> снята."
        ),
        changed=True,
    )


async def set_moderation_permission(
    session: AsyncSession,
    chat_id: int,
    actor_id: int,
    command: str,
    scope: str,
) -> ServiceResult:
    command = command.lower().lstrip("/")
    scope = scope.lower()

    if scope not in {
        PERMISSION_STAFF,
        PERMISSION_ADMIN,
        PERMISSION_HEAD_ADMIN,
    }:
        return ServiceResult(
            False,
            "❌ Доступ: staff, admin или head_admin.",
        )

    actor_role = await effective_role(
        session,
        chat_id,
        actor_id,
    )

    if (
        role_power_value(actor_role)
        < ROLE_POWER[ROLE_HEAD_ADMIN]
    ):
        return ServiceResult(
            False,
            "❌ Настраивать права может только head admin или owner.",
        )

    result = await session.execute(
        select(ModPermission).where(
            ModPermission.chat_id == chat_id,
            ModPermission.command == command,
        )
    )

    row = result.scalar_one_or_none()

    if row is None:
        row = ModPermission(
            chat_id=chat_id,
            command=command,
            scope=scope,
            updated_by=actor_id,
        )
        session.add(row)

    else:
        row.scope = scope
        row.updated_by = actor_id
        row.updated_at = utcnow()

    await session.flush()

    return ServiceResult(
        True,
        (
            f"🛡 Для <code>/{escape(command)}</code> "
            f"установлен доступ: "
            f"<b>{escape(scope)}</b>."
        ),
        changed=True,
    )


async def _moderation_action(
    session: AsyncSession,
    chat_id: int,
    target_user_id: int,
    moderator_id: int,
    action: str,
    reason: Optional[str] = None,
    duration: Optional[int] = None,
) -> ServiceResult:
    allowed, error = await check_moderation_access(
        session,
        chat_id,
        moderator_id,
        action,
    )

    if not allowed:
        return ServiceResult(
            False,
            error or "❌ Нет доступа.",
        )

    if target_user_id == moderator_id:
        return ServiceResult(
            False,
            "❌ Нельзя применить эту модерацию к себе.",
        )

    actor_role = await effective_role(
        session,
        chat_id,
        moderator_id,
    )

    target_role = await effective_role(
        session,
        chat_id,
        target_user_id,
    )

    if (
        target_role is not None
        and role_power_value(target_role)
        >= role_power_value(actor_role)
    ):
        return ServiceResult(
            False,
            "❌ Нельзя модерировать равную или более высокую staff-роль.",
        )

    session.add(
        ModerationAction(
            chat_id=chat_id,
            target_user_id=target_user_id,
            moderator_id=moderator_id,
            action=action,
            reason=reason,
        )
    )

    return ServiceResult(
        True,
        (
            f"🛡 Действие "
            f"<b>{escape(action)}</b> зарегистрировано."
        ),
        changed=True,
    )


async def add_warning(
    session: AsyncSession,
    chat_id: int,
    target_user_id: int,
    moderator_id: int,
    reason: str = "",
) -> ServiceResult:
    result = await _moderation_action(
        session,
        chat_id,
        target_user_id,
        moderator_id,
        "warn",
        reason,
    )

    if not result.success:
        return result

    session.add(
        Warning(
            chat_id=chat_id,
            user_id=target_user_id,
            moderator_id=moderator_id,
            reason=reason or None,
            active=True,
        )
    )

    return ServiceResult(
        True,
        (
            f"⚠️ Пользователь "
            f"<code>{target_user_id}</code> "
            "получил предупреждение."
        ),
        changed=True,
    )


async def remove_warning(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    moderator_id: int,
) -> ServiceResult:
    result = await _moderation_action(
        session,
        chat_id,
        user_id,
        moderator_id,
        "unwarn",
    )

    if not result.success:
        return result

    query = await session.execute(
        select(Warning)
        .where(
            Warning.chat_id == chat_id,
            Warning.user_id == user_id,
            Warning.active.is_(True),
        )
        .order_by(
            Warning.id.desc()
        )
    )

    warning = query.scalars().first()

    if warning is None:
        return ServiceResult(
            False,
            "❌ Активных предупреждений нет.",
        )

    warning.active = False

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
    result = await session.execute(
        select(Warning)
        .where(
            Warning.chat_id == chat_id,
            Warning.user_id == user_id,
            Warning.active.is_(True),
        )
        .order_by(
            Warning.id.asc()
        )
    )

    warnings = list(
        result.scalars().all()
    )

    if not warnings:
        return "⚠️ Активных предупреждений нет."

    lines = [
        f"⚠️ <b>Предупреждения: {len(warnings)}</b>"
    ]

    for index, warning in enumerate(
        warnings,
        1,
    ):
        reason = (
            escape(warning.reason)
            if warning.reason
            else "без причины"
        )

        lines.append(
            f"{index}. {reason}"
        )

    return "\n".join(lines)


async def moderate_mute(
    session: AsyncSession,
    bot: Bot,
    chat_id: int,
    target_user_id: int,
    moderator_id: int,
    duration_minutes: int = 60,
) -> ServiceResult:
    if duration_minutes <= 0:
        return ServiceResult(
            False,
            "❌ Время мута должно быть больше 0.",
        )

    result = await _moderation_action(
        session,
        chat_id,
        target_user_id,
        moderator_id,
        "mute",
        duration=duration_minutes,
    )

    if not result.success:
        return result

    from aiogram.types import ChatPermissions

    try:
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
            until_date=utcnow()
            + timedelta(
                minutes=duration_minutes
            ),
        )

    except (
        TelegramBadRequest,
        TelegramForbiddenError,
    ):
        return ServiceResult(
            False,
            "❌ Telegram не позволил установить мут.",
        )

    return ServiceResult(
        True,
        (
            f"🔇 Пользователь "
            f"<code>{target_user_id}</code> "
            f"замучен на "
            f"<b>{duration_minutes} мин.</b>"
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
    result = await _moderation_action(
        session,
        chat_id,
        target_user_id,
        moderator_id,
        "unmute",
    )

    if not result.success:
        return result

    from aiogram.types import ChatPermissions

    try:
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

    except (
        TelegramBadRequest,
        TelegramForbiddenError,
    ):
        return ServiceResult(
            False,
            "❌ Telegram не позволил снять мут.",
        )

    return ServiceResult(
        True,
        f"🔊 Мут с <code>{target_user_id}</code> снят.",
        changed=True,
    )


async def moderate_ban(
    session: AsyncSession,
    bot: Bot,
    chat_id: int,
    target_user_id: int,
    moderator_id: int,
    reason: str = "",
) -> ServiceResult:
    result = await _moderation_action(
        session,
        chat_id,
        target_user_id,
        moderator_id,
        "ban",
        reason,
    )

    if not result.success:
        return result

    try:
        await bot.ban_chat_member(
            chat_id=chat_id,
            user_id=target_user_id,
        )

    except (
        TelegramBadRequest,
        TelegramForbiddenError,
    ):
        return ServiceResult(
            False,
            "❌ Telegram не позволил заблокировать пользователя.",
        )

    return ServiceResult(
        True,
        f"🔨 Пользователь <code>{target_user_id}</code> заблокирован.",
        changed=True,
    )


async def moderate_unban(
    session: AsyncSession,
    bot: Bot,
    chat_id: int,
    target_user_id: int,
    moderator_id: int,
) -> ServiceResult:
    result = await _moderation_action(
        session,
        chat_id,
        target_user_id,
        moderator_id,
        "unban",
    )

    if not result.success:
        return result

    try:
        await bot.unban_chat_member(
            chat_id=chat_id,
            user_id=target_user_id,
            only_if_banned=True,
        )

    except (
        TelegramBadRequest,
        TelegramForbiddenError,
    ):
        return ServiceResult(
            False,
            "❌ Telegram не позволил разблокировать пользователя.",
        )

    return ServiceResult(
        True,
        f"🔓 Пользователь <code>{target_user_id}</code> разблокирован.",
        changed=True,
    )


async def moderate_kick(
    session: AsyncSession,
    bot: Bot,
    chat_id: int,
    target_user_id: int,
    moderator_id: int,
    reason: str = "",
) -> ServiceResult:
    result = await _moderation_action(
        session,
        chat_id,
        target_user_id,
        moderator_id,
        "kick",
        reason,
    )

    if not result.success:
        return result

    try:
        await bot.ban_chat_member(
            chat_id=chat_id,
            user_id=target_user_id,
        )

        await bot.unban_chat_member(
            chat_id=chat_id,
            user_id=target_user_id,
        )

    except (
        TelegramBadRequest,
        TelegramForbiddenError,
    ):
        return ServiceResult(
            False,
            "❌ Telegram не позволил удалить пользователя.",
        )

    return ServiceResult(
        True,
        f"👢 Пользователь <code>{target_user_id}</code> исключён.",
        changed=True,
    )


async def admin_give_money(
    session: AsyncSession,
    owner_id: int,
    chat_id: int,
    target_user_id: int,
    amount: int,
) -> ServiceResult:
    if owner_id != config.owner_id:
        return ServiceResult(
            False,
            "❌ Только owner.",
        )

    if amount <= 0:
        return ServiceResult(
            False,
            "❌ Сумма должна быть положительной.",
        )

    await change_balance(
        session,
        chat_id,
        target_user_id,
        amount,
        "admin_give",
        f"Выдано owner {owner_id}",
    )

    return ServiceResult(
        True,
        (
            f"🥜 Выдано: "
            f"<b>{format_balance(amount)}</b>.\n"
            f"Пользователь: "
            f"<code>{target_user_id}</code>"
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
    if owner_id != config.owner_id:
        return ServiceResult(
            False,
            "❌ Только owner.",
        )

    if amount <= 0:
        return ServiceResult(
            False,
            "❌ Сумма должна быть положительной.",
        )

    _, error = await can_afford(
        session,
        chat_id,
        target_user_id,
        amount,
    )

    if error:
        return ServiceResult(
            False,
            error,
        )

    try:
        await change_balance(
            session,
            chat_id,
            target_user_id,
            -amount,
            "admin_take",
            f"Забрано owner {owner_id}",
        )
    except ValueError:
        return ServiceResult(
            False,
            "❌ Баланс изменился. Попробуй ещё раз.",
            answer="Баланс изменился. Попробуй ещё раз.",
            show_alert=True,
        )

    return ServiceResult(
        True,
        (
            f"🥜 Забрано: "
            f"<b>{format_balance(amount)}</b>.\n"
            f"Пользователь: "
            f"<code>{target_user_id}</code>"
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
    if owner_id != config.owner_id:
        return ServiceResult(
            False,
            "❌ Только owner.",
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

    if difference:
        await change_balance(
            session,
            chat_id,
            target_user_id,
            difference,
            "admin_set_balance",
            f"Установлено owner {owner_id}",
        )

    return ServiceResult(
        True,
        (
            "🥜 Баланс установлен: "
            f"<b>{format_balance(amount)}</b>."
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
    if owner_id != config.owner_id:
        return ServiceResult(
            False,
            "❌ Только owner.",
        )

    if level < 1:
        return ServiceResult(
            False,
            "❌ Уровень должен быть не меньше 1.",
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
    member.xp = xp_for_level(
        level
    )

    await session.flush()

    return ServiceResult(
        True,
        (
            "⭐ Уровень пользователя "
            f"<code>{target_user_id}</code> установлен: "
            f"<b>{level}</b>."
        ),
        changed=True,
    )


def _weighted_choice(rewards):
    total = sum(
        reward[2]
        for reward in rewards
    )

    if total <= 0:
        return rewards[-1]

    roll = RNG.uniform(
        0,
        total,
    )

    current = 0

    for reward in rewards:
        current += reward[2]

        if roll <= current:
            return reward

    return rewards[-1]


async def open_case(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    case_code: str,
) -> ServiceResult:
    async with _CASE_LOCK:
        if case_code not in CASE_REWARDS:
            return ServiceResult(
                False,
                "❌ Неизвестный кейс.",
            )

        case_item = await get_user_item(
            session,
            chat_id,
            user_id,
            case_code,
        )

        if (
            case_item is None
            or case_item.quantity <= 0
        ):
            return ServiceResult(
                False,
                "❌ У тебя нет этого кейса.",
            )

        await _consume_user_item(
            session,
            case_item,
        )

        reward_code, amount, _ = _weighted_choice(
            CASE_REWARDS[case_code]
        )

        if reward_code == "peanuts":
            await change_balance(
                session,
                chat_id,
                user_id,
                amount,
                "case_reward",
                case_code,
            )

            return ServiceResult(
                True,
                (
                    "📦 <b>Кейс открыт!</b>\n\n"
                    f"🥜 Ты получил "
                    f"<b>{format_balance(amount)}</b>."
                ),
                changed=True,
            )

        if reward_code.startswith(
            "item:"
        ):
            item_code = reward_code.split(
                ":",
                1,
            )[1]

            item = await get_inventory_item(
                session,
                item_code,
            )

            if item_code == DILDO_ITEM_CODE:
                existing = await get_user_item(
                    session,
                    chat_id,
                    user_id,
                    DILDO_ITEM_CODE,
                )

                if (
                    existing
                    and existing.quantity
                    >= DILDO_MAX_OWNED
                ):
                    await change_balance(
                        session,
                        chat_id,
                        user_id,
                        DILDO_DUPLICATE_COMPENSATION,
                        "case_duplicate_compensation",
                        "Дубликат Dildo",
                    )

                    return ServiceResult(
                        True,
                        (
                            "📦 <b>Кейс открыт!</b>\n\n"
                            "🔁 Выпал повторный Dildo.\n"
                            "🥜 Компенсация: "
                            f"<b>{format_balance(DILDO_DUPLICATE_COMPENSATION)}</b>."
                        ),
                        changed=True,
                    )

            await grant_item(
                session,
                chat_id,
                user_id,
                item_code,
                amount,
            )

            item_reward_text = (
                "автоматически использован"
                if item_code
                == SILICONE_IMPLANT_ITEM_CODE
                else escape(
                    item.name
                    if item
                    else item_code
                )
            )

            return ServiceResult(
                True,
                (
                    "📦 <b>Кейс открыт!</b>\n\n"
                    "🎁 Получено: "
                    f"<b>{item_reward_text}</b>"
                ),
                changed=True,
            )

        if reward_code.startswith(
            "tag:"
        ):
            tag_code = reward_code.split(
                ":",
                1,
            )[1]

            tag = await grant_tag(
                session,
                chat_id,
                user_id,
                tag_code,
                f"case:{case_code}",
            )

            return ServiceResult(
                True,
                (
                    "📦 <b>Кейс открыт!</b>\n\n"
                    "🏷 Получен тег: "
                    f"<b>{escape(tag.name if tag else tag_code)}</b>"
                ),
                changed=True,
            )

        return ServiceResult(
            True,
            "📦 Кейс открыт.",
            changed=True,
        )


async def create_giveaway(
    session: AsyncSession,
    chat_id: int,
    creator_id: int,
    prize_type: str,
    ends_at: datetime,
    prize_amount: Optional[int] = None,
    prize_item_code: Optional[str] = None,
    prize_description: Optional[str] = None,
) -> ServiceResult:
    if prize_type not in {
        "peanuts",
        "item",
        "external",
    }:
        return ServiceResult(
            False,
            "❌ Тип приза: peanuts, item или external.",
        )

    if ends_at <= utcnow():
        return ServiceResult(
            False,
            "❌ Время окончания должно быть в будущем.",
        )

    if prize_type == "peanuts":
        if (
            prize_amount is None
            or prize_amount <= 0
        ):
            return ServiceResult(
                False,
                "❌ Сумма приза должна быть положительной.",
            )

    elif prize_type == "item":
        if not prize_item_code:
            return ServiceResult(
                False,
                "❌ Укажи код предмета.",
            )

        item = await get_inventory_item(
            session,
            prize_item_code,
        )

        if item is None:
            return ServiceResult(
                False,
                "❌ Предмет для розыгрыша не найден.",
            )

    elif prize_type == "external":
        if not prize_description:
            return ServiceResult(
                False,
                "❌ Для внешнего приза нужно описание.",
            )

    giveaway = Giveaway(
        chat_id=chat_id,
        creator_id=creator_id,
        prize_type=prize_type,
        prize_amount=prize_amount,
        prize_item_code=prize_item_code,
        prize_description=prize_description,
        ends_at=ends_at,
        status="active",
    )

    session.add(giveaway)

    await session.flush()

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎉 Участвовать",
                    callback_data=(
                        f"giveaway:join:{giveaway.id}"
                    ),
                )
            ]
        ]
    )

    if prize_type == "peanuts":
        prize_text = (
            "🥜 Приз: "
            f"<b>{format_balance(prize_amount or 0)}</b>"
        )

    elif prize_type == "item":
        prize_text = (
            "🎁 Предмет: "
            f"<code>{escape(prize_item_code or '')}</code>"
        )

    else:
        prize_text = (
            "📦 Внешний приз:\n"
            f"<b>{escape(prize_description or '')}</b>\n"
            "⚠️ Выдача внешнего приза производится вручную."
        )

    return ServiceResult(
        True,
        (
            "🎉 <b>Розыгрыш создан!</b>\n\n"
            f"ID: <code>{giveaway.id}</code>\n"
            f"{prize_text}\n"
            f"⏳ До: <b>{giveaway.ends_at}</b>"
        ),
        changed=True,
        keyboard=keyboard,
    )


async def join_giveaway(
    session: AsyncSession,
    giveaway_id: int,
    chat_id: int,
    user_id: int,
) -> ServiceResult:
    async with _GIVEAWAY_LOCK:
        giveaway = await session.get(
            Giveaway,
            giveaway_id,
        )

        if giveaway is None:
            return ServiceResult(
                False,
                "❌ Розыгрыш не найден.",
                answer="Розыгрыш не найден.",
                show_alert=True,
            )

        if giveaway.chat_id != chat_id:
            return ServiceResult(
                False,
                (
                    "❌ Этот розыгрыш относится "
                    "к другому чату."
                ),
                answer="Розыгрыш относится к другому чату.",
                show_alert=True,
            )

        if giveaway.status != "active":
            return ServiceResult(
                False,
                "❌ Розыгрыш уже завершён.",
                answer="Розыгрыш уже завершён.",
                show_alert=True,
            )

        if giveaway.ends_at <= utcnow():
            return ServiceResult(
                False,
                "⏰ Розыгрыш уже закончился.",
                answer="Розыгрыш уже закончился.",
                show_alert=True,
            )

        existing = await session.execute(
            select(
                GiveawayParticipant
            ).where(
                GiveawayParticipant.giveaway_id
                == giveaway_id,
                GiveawayParticipant.user_id
                == user_id,
                GiveawayParticipant.chat_id
                == chat_id,
            )
        )

        if existing.scalar_one_or_none():
            return ServiceResult(
                False,
                "❌ Ты уже участвуешь.",
                answer="Ты уже участвуешь.",
                show_alert=True,
            )

        session.add(
            GiveawayParticipant(
                giveaway_id=giveaway_id,
                chat_id=chat_id,
                user_id=user_id,
            )
        )

        await session.flush()

    return ServiceResult(
        True,
        "🎉 Ты участвуешь в розыгрыше!",
        changed=True,
        answer="Ты участвуешь в розыгрыше!",
    )


async def finish_giveaway(
    session: AsyncSession,
    giveaway_id: int,
    chat_id: Optional[int] = None,
) -> ServiceResult:
    async with _GIVEAWAY_LOCK:
        giveaway = await session.get(
            Giveaway,
            giveaway_id,
        )

        if giveaway is None:
            return ServiceResult(
                False,
                "❌ Розыгрыш не найден.",
            )

        if (
            chat_id is not None
            and giveaway.chat_id != chat_id
        ):
            return ServiceResult(
                False,
                "❌ Этот розыгрыш относится к другому чату.",
            )

        if giveaway.status != "active":
            return ServiceResult(
                False,
                "❌ Розыгрыш уже завершён.",
            )

        result = await session.execute(
            select(
                GiveawayParticipant
            ).where(
                GiveawayParticipant.giveaway_id
                == giveaway_id,
                GiveawayParticipant.chat_id
                == giveaway.chat_id,
            )
        )

        participants = list(
            result.scalars().all()
        )

        if not participants:
            giveaway.status = "finished"
            giveaway.completed_at = utcnow()

            return ServiceResult(
                True,
                "🎉 Розыгрыш завершён без участников.",
                changed=True,
            )

        winner = RNG.choice(
            participants
        )

        giveaway.winner_id = winner.user_id
        giveaway.status = "finished"
        giveaway.completed_at = utcnow()

        if giveaway.prize_type == "peanuts":
            if giveaway.prize_amount:
                await change_balance(
                    session,
                    giveaway.chat_id,
                    winner.user_id,
                    giveaway.prize_amount,
                    "giveaway_reward",
                    f"Розыгрыш #{giveaway.id}",
                )

        elif giveaway.prize_type == "item":
            if giveaway.prize_item_code:
                await grant_item(
                    session,
                    giveaway.chat_id,
                    winner.user_id,
                    giveaway.prize_item_code,
                )

        elif giveaway.prize_type == "external":
            await session.flush()

            return ServiceResult(
                True,
                (
                    "🎉 <b>Розыгрыш завершён!</b>\n"
                    "Победитель: "
                    f'<a href="tg://user?id={winner.user_id}">'
                    "игрок</a>\n"
                    "📦 Внешний приз: "
                    f"<b>{escape(giveaway.prize_description or 'без описания')}</b>\n"
                    "⚠️ Приз необходимо выдать вручную."
                ),
                changed=True,
            )

        await session.flush()

        return ServiceResult(
            True,
            (
                "🎉 <b>Розыгрыш завершён!</b>\n"
                "Победитель: "
                f'<a href="tg://user?id={winner.user_id}">'
                "игрок</a>"
            ),
            changed=True,
        )


def get_games_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for game_code, title in [
        ("coinflip", "🪙 Монетка"),
        ("dice", "🎲 Кубики"),
        ("slots", "🎰 Слоты"),
        ("roulette", "🎡 Рулетка"),
        ("guess", "🔢 Угадай число"),
        ("football", "⚽ Футбол"),
        ("basketball", "🏀 Баскетбол"),
        ("tictactoe", "⭕❌ TTT"),
        ("blackjack", "🃏 Blackjack"),
        ("crash", "🚀 Crash"),
    ]:
        builder.button(
            text=title,
            callback_data=f"game:{game_code}",
        )

    builder.adjust(2)

    return builder.as_markup()