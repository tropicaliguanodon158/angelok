"""
Ezzzy Game Bot
==============
handlers.py — Telegram handlers.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from html import escape
from typing import Awaitable, Callable, Optional

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

from sqlalchemy import select

from core import (
    ADULT_RP_ACTIONS,
    BATTLE_PASS_MAX_LEVEL,
    BATTLE_PASS_REWARDS,
    CASE_REWARDS,
    RP_ACTIONS,
    get_adult_rp_action,
    get_feature_required_level,
    get_rp_action_by_alias,
)

from database import (
    AsyncSessionLocal,
    InventoryItem,
    User,
    UserItem,
    get_or_create_chat,
    get_or_create_member,
    get_or_create_user,
    get_top_by_penis_size,
)

from services import (
    ServiceResult,
    abort_child,
    add_warning,
    admin_give_money,
    admin_set_balance,
    admin_set_level,
    admin_take_money,
    assign_staff_role,
    balance_user,
    check_moderation_access,
    claim_daily_bonus,
    create_giveaway,
    finish_giveaway,
    format_balance,
    format_inventory,
    format_other_profile,
    format_profile,
    format_stats,
    get_leaderboard,
    get_tag_keyboard,
    get_warnings,
    game_unlocked,
    handle_message,
    join_giveaway,
    join_tictactoe,
    masturbate,
    moderate_ban,
    moderate_kick,
    moderate_mute,
    moderate_unban,
    moderate_unmute,
    open_case,
    perform_adult_rp,
    perform_rp,
    play_basketball,
    play_blackjack,
    play_coinflip,
    play_crash,
    play_dice,
    play_football,
    play_guess,
    play_roulette,
    play_slots,
    remove_staff_role,
    remove_warning,
    rob_user,
    select_tag,
    set_moderation_permission,
    set_profile_nick,
    start_tictactoe,
    tictactoe_move,
    transfer_money,
    use_medicine,
    visit_venereologist,
)

logger = logging.getLogger("EzzzyGameBot.handlers")

router = Router(name="main")


# ============================================================================
# UI / MESSAGE CLEANUP
# ============================================================================

GROUP_BOT_MESSAGE_TTL = 30
GROUP_COMMAND_TTL = 5
PRIVATE_BOT_MESSAGE_TTL = 0

NAV_PROFILE = "👤 Профиль"
NAV_STATS = "📊 Стата"
NAV_BALANCE = "🥜 Баланс"
NAV_INVENTORY = "🎒 Инвентарь"
NAV_GAMES = "🎮 Игры"
NAV_TOP = "🏆 Топ"
NAV_SIZE_TOP = "📏 Топ размера"
NAV_BONUS = "🎁 Бонус"
NAV_BP = "🏅 Battle Pass"
NAV_TAG = "🏷 Теги"

NAVIGATION_BUTTONS = {
    NAV_PROFILE,
    NAV_STATS,
    NAV_BALANCE,
    NAV_INVENTORY,
    NAV_GAMES,
    NAV_TOP,
    NAV_SIZE_TOP,
    NAV_BONUS,
    NAV_BP,
    NAV_TAG,
}


def is_group(message: Message) -> bool:
    return message.chat.type in {
        ChatType.GROUP,
        ChatType.SUPERGROUP,
    }


def parse_integer(value: Optional[str]) -> Optional[int]:
    if not value:
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def navigation_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=NAV_PROFILE),
                KeyboardButton(text=NAV_STATS),
                KeyboardButton(text=NAV_BALANCE),
            ],
            [
                KeyboardButton(text=NAV_INVENTORY),
                KeyboardButton(text=NAV_GAMES),
                KeyboardButton(text=NAV_TOP),
            ],
            [
                KeyboardButton(text=NAV_SIZE_TOP),
                KeyboardButton(text=NAV_BONUS),
                KeyboardButton(text=NAV_BP),
            ],
            [
                KeyboardButton(text=NAV_TAG),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери раздел",
    )


def section_keyboard(
    *,
    include_games: bool = True,
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="👤 Профиль",
                callback_data="nav:profile",
            ),
            InlineKeyboardButton(
                text="📊 Стата",
                callback_data="nav:stats",
            ),
        ],
        [
            InlineKeyboardButton(
                text="🥜 Баланс",
                callback_data="nav:balance",
            ),
            InlineKeyboardButton(
                text="🎒 Инвентарь",
                callback_data="nav:inventory",
            ),
        ],
        [
            InlineKeyboardButton(
                text="🏆 Топ",
                callback_data="nav:top",
            ),
            InlineKeyboardButton(
                text="📏 Размер",
                callback_data="nav:topsize",
            ),
        ],
        [
            InlineKeyboardButton(
                text="🏅 Battle Pass",
                callback_data="nav:battlepass",
            ),
            InlineKeyboardButton(
                text="🏷 Теги",
                callback_data="nav:tag",
            ),
        ],
    ]

    if include_games:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🎮 Игры",
                    callback_data="nav:games",
                )
            ]
        )

    return InlineKeyboardMarkup(
        inline_keyboard=rows,
    )


async def safe_delete_message(
    message: Message,
) -> None:
    try:
        await message.delete()
    except (
        TelegramBadRequest,
        TelegramForbiddenError,
    ):
        pass
    except Exception:
        logger.debug(
            "Не удалось удалить сообщение %s:%s.",
            message.chat.id,
            message.message_id,
            exc_info=True,
        )


async def delete_later(
    message: Message,
    delay: int | float,
) -> None:
    if delay <= 0:
        return

    try:
        await asyncio.sleep(delay)
        await safe_delete_message(message)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.debug(
            "Ошибка отложенного удаления сообщения %s:%s.",
            message.chat.id,
            message.message_id,
            exc_info=True,
        )


def schedule_delete(
    message: Optional[Message],
    delay: int | float,
) -> None:
    if message is None or delay <= 0:
        return

    asyncio.create_task(
        delete_later(
            message,
            delay,
        )
    )


async def reply(
    message: Message,
    text: str,
    *,
    delete_after: Optional[int | float] = None,
    delete_command: bool = True,
    **kwargs,
) -> Optional[Message]:
    if not text:
        return None

    if delete_after is None:
        delete_after = (
            GROUP_BOT_MESSAGE_TTL
            if is_group(message)
            else PRIVATE_BOT_MESSAGE_TTL
        )

    try:
        sent = await message.answer(
            text,
            **kwargs,
        )
    except TelegramForbiddenError:
        logger.warning(
            "Telegram запретил отправку сообщения chat_id=%s",
            message.chat.id,
        )
        return None
    except TelegramBadRequest:
        logger.exception(
            "Telegram отклонил сообщение chat_id=%s",
            message.chat.id,
        )
        return None

    if delete_after:
        schedule_delete(
            sent,
            delete_after,
        )

    if (
        delete_command
        and is_group(message)
        and message.message_id
    ):
        schedule_delete(
            message,
            GROUP_COMMAND_TTL,
        )

    return sent


async def callback_edit(
    callback: CallbackQuery,
    text: str,
    *,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> bool:
    if not callback.message:
        return False

    try:
        await callback.message.edit_text(
            text,
            reply_markup=reply_markup,
        )
        return True
    except TelegramBadRequest:
        return False


async def commit_result(
    session,
    result: ServiceResult,
) -> None:
    if result.success:
        await session.commit()
    else:
        await session.rollback()


# ============================================================================
# MEMBER PREPARATION
# ============================================================================

async def get_or_prepare_member(
    message: Message,
):
    if not message.from_user:
        return None

    async with AsyncSessionLocal() as session:
        await get_or_create_user(
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
            title=message.chat.title or "Private",
            chat_type=message.chat.type,
        )

        member = await get_or_create_member(
            session=session,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
        )

        await session.commit()

        return member


# ============================================================================
# PROFILE TARGET
# ============================================================================

async def resolve_user_id(
    message: Message,
    command: Optional[CommandObject] = None,
) -> Optional[int]:
    if (
        message.reply_to_message
        and message.reply_to_message.from_user
    ):
        return message.reply_to_message.from_user.id

    args = (
        command.args
        if command is not None
        else ""
    ) or ""

    args = args.strip()

    if not args:
        return (
            message.from_user.id
            if message.from_user
            else None
        )

    first = args.split()[0]

    parsed = parse_integer(first)

    if parsed is not None:
        return parsed

    username = first.lstrip("@").lower()

    if not username:
        return None

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User.id).where(
                User.username.ilike(username)
            )
        )

        return result.scalar_one_or_none()


def reply_target_id(
    message: Message,
) -> Optional[int]:
    if not message.reply_to_message:
        return None

    if not message.reply_to_message.from_user:
        return None

    return message.reply_to_message.from_user.id


# ============================================================================
# CASES
# ============================================================================

async def build_case_keyboard(
    session,
    chat_id: int,
    user_id: int,
) -> Optional[InlineKeyboardMarkup]:
    query = await session.execute(
        select(
            InventoryItem.code,
            UserItem.quantity,
        )
        .join(
            UserItem,
            UserItem.item_id == InventoryItem.id,
        )
        .where(
            UserItem.chat_id == chat_id,
            UserItem.user_id == user_id,
            InventoryItem.code.in_(
                tuple(CASE_REWARDS.keys())
            ),
            UserItem.quantity > 0,
        )
        .order_by(
            InventoryItem.id.asc()
        )
    )

    titles = {
        "basic_case": "📦 Basic Case",
        "rare_case": "💎 Rare Case",
        "epic_case": "🔥 Epic Case",
        "legendary_case": "👑 Legendary Case",
    }

    rows = []

    for code, quantity in query.all():
        rows.append(
            [
                InlineKeyboardButton(
                    text=(
                        f"{titles.get(code, code)} "
                        f"×{quantity}"
                    ),
                    callback_data=f"case:{code}",
                )
            ]
        )

    if not rows:
        return None

    return InlineKeyboardMarkup(
        inline_keyboard=rows,
    )


def inventory_keyboard(
    case_keyboard: Optional[InlineKeyboardMarkup],
) -> InlineKeyboardMarkup:
    rows = []

    if case_keyboard:
        rows.extend(
            case_keyboard.inline_keyboard
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="🏷 Теги",
                callback_data="nav:tag",
            ),
            InlineKeyboardButton(
                text="👤 Профиль",
                callback_data="nav:profile",
            ),
        ]
    )

    rows.append(
        [
            InlineKeyboardButton(
                text="🎮 Игры",
                callback_data="nav:games",
            )
        ]
    )

    return InlineKeyboardMarkup(
        inline_keyboard=rows,
    )


# ============================================================================
# START / HELP
# ============================================================================

@router.message(Command("start"))
async def cmd_start(
    message: Message,
) -> None:
    await get_or_prepare_member(message)

    await reply(
        message,
        (
            "<b>🥜 Ezzzy Game Bot</b>\n\n"
            "Добро пожаловать!\n\n"
            "⭐ Уровни\n"
            "🎮 Мини-игры\n"
            "💰 Экономика\n"
            "🏆 Battle Pass\n"
            "🏷 Теги\n"
            "🎭 RP\n\n"
            "Используй нижнее меню."
        ),
        reply_markup=navigation_keyboard(),
        delete_after=0,
    )


@router.message(Command("help"))
async def cmd_help(
    message: Message,
) -> None:
    await reply(
        message,
        (
            "<b>📚 Команды Ezzzy</b>\n\n"
            "<b>👤 Профиль</b>\n"
            "/profile\n"
            "/profile @username\n"
            "/profile ответом на сообщение\n"
            "/stats\n"
            "/balance\n"
            "/inventory\n"
            "/tag\n"
            "/battlepass\n"
            "/top\n"
            "/topsize\n\n"
            "<b>🎮 Игры</b>\n"
            "/games\n"
            "/bonus\n"
            "/coinflip 100\n"
            "/dice 100\n"
            "/slots 100\n"
            "/roulette 100 red\n"
            "/guess 100 5\n"
            "/football 100\n"
            "/basketball 100\n"
            "/ttt\n"
            "/blackjack 100\n"
            "/crash 100 2.00\n\n"
            "<b>💰 Экономика</b>\n"
            "/pay 100 ответом\n"
            "/masturbate\n"
            "/rob ответом\n\n"
            "<b>🎭 RP</b>\n"
            "обычные RP-команды работают текстом\n"
            "18+ RP-команды работают текстом\n\n"
            "<b>🛡 Модерация</b>\n"
            "/warn\n"
            "/unwarn\n"
            "/warnings\n"
            "/mute\n"
            "/unmute\n"
            "/ban\n"
            "/unban\n"
            "/kick\n"
            "/setnick\n"
            "/setrole\n"
            "/delrole\n"
            "/setperm\n\n"
            "<b>🎁 Розыгрыши</b>\n"
            "/giveaway\n"
            "/giveaway_join ID\n"
            "/giveaway_finish ID"
        ),
        delete_after=60,
    )


# ============================================================================
# PROFILE
# ============================================================================

def profile_keyboard(
    member,
) -> InlineKeyboardMarkup:
    rows = []

    if member.has_disease:
        rows.append(
            [
                InlineKeyboardButton(
                    text="💊 Лекарство",
                    callback_data=(
                        f"profile:medicine:{member.user_id}"
                    ),
                ),
                InlineKeyboardButton(
                    text="🧑‍⚕️ Венеролог",
                    callback_data=(
                        f"profile:venereologist:{member.user_id}"
                    ),
                ),
            ]
        )

    if member.has_child:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🏥 Аборт",
                    callback_data=(
                        f"profile:abort:{member.user_id}"
                    ),
                )
            ]
        )

    rows.extend(
        section_keyboard().inline_keyboard
    )

    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )


async def render_profile(
    session,
    chat_id: int,
    user_id: int,
) -> tuple[str, InlineKeyboardMarkup]:
    text = await format_profile(
        session=session,
        chat_id=chat_id,
        user_id=user_id,
    )

    member = await get_or_create_member(
        session=session,
        chat_id=chat_id,
        user_id=user_id,
    )

    keyboard = profile_keyboard(member)

    await session.commit()

    return text, keyboard


@router.message(Command("profile"))
async def cmd_profile(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    await get_or_prepare_member(message)

    target_id = await resolve_user_id(
        message,
        command,
    )

    if target_id is None:
        await reply(
            message,
            "❌ Не удалось найти пользователя.",
        )
        return

    async with AsyncSessionLocal() as session:
        if target_id == message.from_user.id:
            text, keyboard = await render_profile(
                session,
                message.chat.id,
                target_id,
            )
        else:
            text = await format_other_profile(
                session=session,
                chat_id=message.chat.id,
                target_user_id=target_id,
            )

            keyboard = section_keyboard(
                include_games=True
            )

            await session.commit()

    await reply(
        message,
        text,
        reply_markup=keyboard,
        delete_after=0,
    )


@router.callback_query(
    F.data.startswith("profile:")
)
async def callback_profile_action(
    callback: CallbackQuery,
) -> None:
    if (
        not callback.message
        or not callback.from_user
    ):
        await callback.answer()
        return

    parts = (
        callback.data or ""
    ).split(":")

    if len(parts) != 3:
        await callback.answer(
            "Некорректное действие.",
            show_alert=True,
        )
        return

    action = parts[1]

    target_id = parse_integer(
        parts[2]
    )

    if target_id is None:
        await callback.answer(
            "Некорректный профиль.",
            show_alert=True,
        )
        return

    if callback.from_user.id != target_id:
        await callback.answer(
            "Эта кнопка предназначена владельцу профиля.",
            show_alert=True,
        )
        return

    handlers = {
        "medicine": use_medicine,
        "venereologist": visit_venereologist,
        "abort": abort_child,
    }

    handler = handlers.get(action)

    if handler is None:
        await callback.answer(
            "Неизвестное действие.",
            show_alert=True,
        )
        return

    async with AsyncSessionLocal() as session:
        result = await handler(
            session=session,
            chat_id=callback.message.chat.id,
            user_id=target_id,
        )

        await commit_result(
            session,
            result,
        )

        text, keyboard = await render_profile(
            session,
            callback.message.chat.id,
            target_id,
        )

    await callback.answer(
        result.answer or result.message,
        show_alert=result.show_alert,
    )

    await callback_edit(
        callback,
        text,
        reply_markup=keyboard,
    )


@router.message(Command("stats"))
async def cmd_stats(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    await get_or_prepare_member(message)

    target_id = await resolve_user_id(
        message,
        command,
    )

    if target_id is None:
        return

    async with AsyncSessionLocal() as session:
        text = await format_stats(
            session=session,
            chat_id=message.chat.id,
            user_id=target_id,
        )

        keyboard = section_keyboard()

        await session.commit()

    await reply(
        message,
        text,
        reply_markup=keyboard,
        delete_after=0,
    )


@router.message(Command("balance"))
async def cmd_balance(
    message: Message,
) -> None:
    if not message.from_user:
        return

    await get_or_prepare_member(message)

    async with AsyncSessionLocal() as session:
        balance = await balance_user(
            session=session,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
        )

        keyboard = section_keyboard(
            include_games=False
        )

        await session.commit()

    await reply(
        message,
        (
            f"🥜 Баланс: "
            f"<b>{format_balance(balance)}</b>"
        ),
        reply_markup=keyboard,
        delete_after=0,
    )


@router.message(Command("inventory"))
async def cmd_inventory(
    message: Message,
) -> None:
    if not message.from_user:
        return

    await get_or_prepare_member(message)

    async with AsyncSessionLocal() as session:
        text = await format_inventory(
            session=session,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
        )

        case_keyboard = await build_case_keyboard(
            session=session,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
        )

        keyboard = inventory_keyboard(
            case_keyboard
        )

        await session.commit()

    await reply(
        message,
        text,
        reply_markup=keyboard,
        delete_after=0,
    )


@router.message(Command("tag"))
async def cmd_tag(
    message: Message,
) -> None:
    if not message.from_user:
        return

    await get_or_prepare_member(message)

    async with AsyncSessionLocal() as session:
        keyboard = await get_tag_keyboard(
            session=session,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
        )

        await session.commit()

    rows = list(
        keyboard.inline_keyboard
    )
    rows.extend(
        section_keyboard(
            include_games=False
        ).inline_keyboard
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=rows
    )

    await reply(
        message,
        (
            "🏷 <b>Твои теги</b>\n\n"
            "Выбери полученный тег:"
        ),
        reply_markup=keyboard,
        delete_after=0,
    )


@router.callback_query(
    F.data.startswith("tagselect:")
)
async def callback_tag_select(
    callback: CallbackQuery,
) -> None:
    if (
        not callback.message
        or not callback.from_user
    ):
        await callback.answer()
        return

    tag_id = parse_integer(
        (callback.data or "").split(
            ":",
            1,
        )[1]
    )

    if tag_id is None:
        await callback.answer(
            "Некорректный тег.",
            show_alert=True,
        )
        return

    async with AsyncSessionLocal() as session:
        result = await select_tag(
            session=session,
            chat_id=callback.message.chat.id,
            user_id=callback.from_user.id,
            tag_id=tag_id,
        )

        await commit_result(
            session,
            result,
        )

        keyboard = await get_tag_keyboard(
            session=session,
            chat_id=callback.message.chat.id,
            user_id=callback.from_user.id,
        )

        await session.commit()

    await callback.answer(
        result.answer or result.message,
        show_alert=result.show_alert,
    )

    if not result.success:
        return

    rows = list(
        keyboard.inline_keyboard
    )
    rows.extend(
        section_keyboard(
            include_games=False
        ).inline_keyboard
    )

    await callback_edit(
        callback,
        (
            "🏷 <b>Твои теги</b>\n\n"
            "Выбери полученный тег:"
        ),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=rows
        ),
    )


@router.message(Command("battlepass"))
async def cmd_battlepass(
    message: Message,
) -> None:
    if not message.from_user:
        return

    await get_or_prepare_member(message)

    async with AsyncSessionLocal() as session:
        member = await get_or_create_member(
            session=session,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
        )

        level = min(
            BATTLE_PASS_MAX_LEVEL,
            max(
                1,
                member.battle_pass_level,
            ),
        )

        current_xp = member.battle_pass_xp

        level_xp = current_xp % 100

        remaining = (
            0
            if level >= BATTLE_PASS_MAX_LEVEL
            else 100 - level_xp
        )

        reward_text = "—"

        reward = BATTLE_PASS_REWARDS.get(level)

        if reward is not None:
            reward_text = str(
                getattr(
                    reward,
                    "description",
                    None,
                )
                or getattr(
                    reward,
                    "name",
                    None,
                )
                or getattr(
                    reward,
                    "reward_type",
                    None,
                )
                or reward
            )

        await session.commit()

    await reply(
        message,
        (
            "<b>🏆 Battle Pass</b>\n\n"
            f"Уровень: "
            f"<b>{level}/{BATTLE_PASS_MAX_LEVEL}</b>\n"
            f"XP сезона: <b>{current_xp}</b>\n"
            f"До следующего уровня: "
            f"<b>{remaining}</b>\n\n"
            f"🎁 Награда текущего уровня:\n"
            f"{escape(reward_text)}"
        ),
        reply_markup=section_keyboard(
            include_games=False
        ),
        delete_after=0,
    )


@router.message(Command("top"))
async def cmd_top(
    message: Message,
) -> None:
    if not is_group(message):
        await reply(
            message,
            "🏆 Рейтинг доступен в группах.",
        )
        return

    async with AsyncSessionLocal() as session:
        text = await get_leaderboard(
            session=session,
            chat_id=message.chat.id,
        )

        await session.commit()

    await reply(
        message,
        text,
        reply_markup=section_keyboard(
            include_games=False
        ),
        delete_after=0,
    )


@router.message(Command("topsize"))
async def cmd_topsize(
    message: Message,
) -> None:
    if not is_group(message):
        await reply(
            message,
            "🏆 Рейтинг доступен в группах.",
        )
        return

    async with AsyncSessionLocal() as session:
        members = await get_top_by_penis_size(
            session=session,
            chat_id=message.chat.id,
            limit=10,
        )

        lines = [
            "📏 <b>Топ по размеру</b>"
        ]

        for index, member in enumerate(
            members,
            1,
        ):
            lines.append(
                f'{index}. '
                f'<a href="tg://user?id={member.user_id}">'
                "Игрок</a> — "
                f"<b>{member.penis_size:.2f} см</b>"
            )

        await session.commit()

    await reply(
        message,
        "\n".join(lines),
        reply_markup=section_keyboard(
            include_games=False
        ),
        delete_after=0,
    )


@router.message(Command("bonus"))
async def cmd_bonus(
    message: Message,
) -> None:
    if not message.from_user:
        return

    await get_or_prepare_member(message)

    async with AsyncSessionLocal() as session:
        result = await claim_daily_bonus(
            session=session,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
        )

        await commit_result(
            session,
            result,
        )

    await reply(
        message,
        result.message,
        reply_markup=section_keyboard(
            include_games=False
        ),
        delete_after=20,
    )


# ============================================================================
# BOTTOM NAVIGATION
# ============================================================================

async def _nav_profile(
    message: Message,
) -> None:
    if not message.from_user:
        return

    async with AsyncSessionLocal() as session:
        text, keyboard = await render_profile(
            session,
            message.chat.id,
            message.from_user.id,
        )

    await reply(
        message,
        text,
        reply_markup=keyboard,
        delete_after=0,
    )


async def _nav_stats(
    message: Message,
) -> None:
    if not message.from_user:
        return

    async with AsyncSessionLocal() as session:
        text = await format_stats(
            session=session,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
        )
        keyboard = section_keyboard()
        await session.commit()

    await reply(
        message,
        text,
        reply_markup=keyboard,
        delete_after=0,
    )


async def _nav_balance(
    message: Message,
) -> None:
    if not message.from_user:
        return

    async with AsyncSessionLocal() as session:
        balance = await balance_user(
            session=session,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
        )
        await session.commit()

    await reply(
        message,
        f"🥜 Баланс: <b>{format_balance(balance)}</b>",
        reply_markup=section_keyboard(
            include_games=False
        ),
        delete_after=0,
    )


async def _nav_inventory(
    message: Message,
) -> None:
    if not message.from_user:
        return

    async with AsyncSessionLocal() as session:
        text = await format_inventory(
            session=session,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
        )

        case_keyboard = await build_case_keyboard(
            session=session,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
        )

        await session.commit()

    await reply(
        message,
        text,
        reply_markup=inventory_keyboard(
            case_keyboard
        ),
        delete_after=0,
    )


async def _nav_tag(
    message: Message,
) -> None:
    if not message.from_user:
        return

    async with AsyncSessionLocal() as session:
        keyboard = await get_tag_keyboard(
            session=session,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
        )
        await session.commit()

    rows = list(
        keyboard.inline_keyboard
    )
    rows.extend(
        section_keyboard(
            include_games=False
        ).inline_keyboard
    )

    await reply(
        message,
        (
            "🏷 <b>Твои теги</b>\n\n"
            "Выбери полученный тег:"
        ),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=rows
        ),
        delete_after=0,
    )


async def _nav_battlepass(
    message: Message,
) -> None:
    await cmd_battlepass(message)


async def _nav_games(
    message: Message,
) -> None:
    await cmd_games(message)


async def _nav_top(
    message: Message,
) -> None:
    await cmd_top(message)


async def _nav_topsize(
    message: Message,
) -> None:
    await cmd_topsize(message)


async def _nav_bonus(
    message: Message,
) -> None:
    await cmd_bonus(message)


@router.message(F.text == NAV_PROFILE)
async def nav_profile_handler(
    message: Message,
) -> None:
    await _nav_profile(message)


@router.message(F.text == NAV_STATS)
async def nav_stats_handler(
    message: Message,
) -> None:
    await _nav_stats(message)


@router.message(F.text == NAV_BALANCE)
async def nav_balance_handler(
    message: Message,
) -> None:
    await _nav_balance(message)


@router.message(F.text == NAV_INVENTORY)
async def nav_inventory_handler(
    message: Message,
) -> None:
    await _nav_inventory(message)


@router.message(F.text == NAV_GAMES)
async def nav_games_handler(
    message: Message,
) -> None:
    await _nav_games(message)


@router.message(F.text == NAV_TOP)
async def nav_top_handler(
    message: Message,
) -> None:
    await _nav_top(message)


@router.message(F.text == NAV_SIZE_TOP)
async def nav_size_top_handler(
    message: Message,
) -> None:
    await _nav_topsize(message)


@router.message(F.text == NAV_BONUS)
async def nav_bonus_handler(
    message: Message,
) -> None:
    await _nav_bonus(message)


@router.message(F.text == NAV_BP)
async def nav_bp_handler(
    message: Message,
) -> None:
    await _nav_battlepass(message)


@router.message(F.text == NAV_TAG)
async def nav_tag_handler(
    message: Message,
) -> None:
    await _nav_tag(message)


# ============================================================================
# ECONOMY
# ============================================================================

@router.message(Command("pay"))
async def cmd_pay(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    if not message.reply_to_message:
        await reply(
            message,
            (
                "💸 Используй /pay ответом "
                "на сообщение.\n"
                "Пример: <code>/pay 500</code>"
            ),
        )
        return

    amount = parse_integer(
        command.args
    )

    if amount is None or amount <= 0:
        await reply(
            message,
            "❌ Укажи положительную сумму.",
        )
        return

    target = message.reply_to_message.from_user

    if not target:
        return

    async with AsyncSessionLocal() as session:
        result = await transfer_money(
            session=session,
            chat_id=message.chat.id,
            sender_id=message.from_user.id,
            receiver_id=target.id,
            amount=amount,
        )

        await commit_result(
            session,
            result,
        )

    await reply(
        message,
        result.message,
    )


@router.message(Command("masturbate"))
async def cmd_masturbate(
    message: Message,
) -> None:
    if not message.from_user:
        return

    async with AsyncSessionLocal() as session:
        result = await masturbate(
            session=session,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
        )

        await commit_result(
            session,
            result,
        )

    await reply(
        message,
        result.message,
    )


@router.message(Command("rob"))
async def cmd_rob(
    message: Message,
) -> None:
    if not message.from_user:
        return

    if not message.reply_to_message:
        await reply(
            message,
            "🥷 Используй /rob ответом "
            "на сообщение цели.",
        )
        return

    target = message.reply_to_message.from_user

    if not target:
        return

    async with AsyncSessionLocal() as session:
        result = await rob_user(
            session=session,
            chat_id=message.chat.id,
            actor_id=message.from_user.id,
            target_id=target.id,
        )

        await commit_result(
            session,
            result,
        )

    await reply(
        message,
        result.message,
    )


# ============================================================================
# GAMES
# ============================================================================

GAME_TITLES = {
    "coinflip": "🪙 Монетка",
    "dice": "🎲 Кубики",
    "slots": "🎰 Слоты",
    "roulette": "🎡 Рулетка",
    "guess": "🔢 Угадай число",
    "football": "⚽ Футбол",
    "basketball": "🏀 Баскетбол",
    "tictactoe": "⭕❌ Крестики-нолики",
    "blackjack": "🃏 Blackjack",
    "crash": "🚀 Crash",
}

GAME_CALLBACKS = {
    "coinflip": play_coinflip,
    "dice": play_dice,
    "slots": play_slots,
    "football": play_football,
    "basketball": play_basketball,
    "blackjack": play_blackjack,
}


def games_keyboard() -> InlineKeyboardMarkup:
    rows = []

    game_rows = [
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
    ]

    for index in range(0, len(game_rows), 2):
        first = game_rows[index]
        second = (
            game_rows[index + 1]
            if index + 1 < len(game_rows)
            else None
        )

        row = [
            InlineKeyboardButton(
                text=first[1],
                callback_data=f"game:{first[0]}",
            )
        ]

        if second:
            row.append(
                InlineKeyboardButton(
                    text=second[1],
                    callback_data=f"game:{second[0]}",
                )
            )

        rows.append(row)

    rows.append(
        [
            InlineKeyboardButton(
                text="👤 Профиль",
                callback_data="nav:profile",
            ),
            InlineKeyboardButton(
                text="🥜 Баланс",
                callback_data="nav:balance",
            ),
        ]
    )

    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )


def game_bet_keyboard(
    game_type: str,
) -> InlineKeyboardMarkup:
    bets = [10, 50, 100, 500, 1_000]

    rows = []

    for index in range(0, len(bets), 3):
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"🥜 {bet}",
                    callback_data=(
                        f"gamebet:{game_type}:{bet}"
                    ),
                )
                for bet in bets[index:index + 3]
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ Игры",
                callback_data="games:menu",
            )
        ]
    )

    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )


def roulette_bet_keyboard(
    bet: int,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔴 Красное",
                    callback_data=f"gameroulette:{bet}:red",
                ),
                InlineKeyboardButton(
                    text="⚫ Чёрное",
                    callback_data=f"gameroulette:{bet}:black",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🟢 Зеро",
                    callback_data=f"gameroulette:{bet}:green",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="game:roulette",
                )
            ],
        ]
    )


def guess_keyboard(
    bet: int,
) -> InlineKeyboardMarkup:
    rows = []

    for start in range(1, 11, 5):
        rows.append(
            [
                InlineKeyboardButton(
                    text=str(number),
                    callback_data=(
                        f"gameguess:{bet}:{number}"
                    ),
                )
                for number in range(
                    start,
                    min(start + 5, 11),
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ Игры",
                callback_data="games:menu",
            )
        ]
    )

    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )


def crash_keyboard(
    bet: int,
) -> InlineKeyboardMarkup:
    multipliers = [
        "1.10",
        "1.50",
        "2.00",
        "3.00",
        "5.00",
        "10.00",
    ]

    rows = []

    for index in range(0, len(multipliers), 3):
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{value}x",
                    callback_data=(
                        f"gamecrash:{bet}:{value}"
                    ),
                )
                for value in multipliers[index:index + 3]
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ Игры",
                callback_data="games:menu",
            )
        ]
    )

    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )


def ttt_start_keyboard() -> InlineKeyboardMarkup:
    bets = [10, 50, 100, 500]

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🥜 {bet}",
                    callback_data=f"gamettt:{bet}",
                )
                for bet in bets
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Игры",
                    callback_data="games:menu",
                )
            ],
        ]
    )


async def execute_simple_game(
    callback: CallbackQuery,
    game_type: str,
    bet: int,
) -> None:
    if not callback.message or not callback.from_user:
        await callback.answer()
        return

    handler = GAME_CALLBACKS.get(game_type)

    if handler is None:
        await callback.answer(
            "Эта игра требует дополнительного выбора.",
            show_alert=True,
        )
        return

    async with AsyncSessionLocal() as session:
        result = await handler(
            session=session,
            chat_id=callback.message.chat.id,
            user_id=callback.from_user.id,
            bet=bet,
        )

        await commit_result(
            session,
            result,
        )

    await callback.answer(
        result.answer or result.message,
        show_alert=result.show_alert,
    )

    if result.success:
        await callback_edit(
            callback,
            (
                result.message
                + "\n\n🎮 <i>Можно сыграть ещё раз.</i>"
            ),
            reply_markup=game_bet_keyboard(game_type),
        )
    else:
        await callback_edit(
            callback,
            (
                f"<b>{GAME_TITLES.get(game_type, 'Игра')}</b>\n\n"
                f"{result.message}"
            ),
            reply_markup=game_bet_keyboard(game_type),
        )


@router.message(Command("games"))
async def cmd_games(
    message: Message,
) -> None:
    await reply(
        message,
        (
            "<b>🎮 Мини-игры</b>\n\n"
            "Выбери игру:"
        ),
        reply_markup=games_keyboard(),
        delete_after=0,
    )


@router.message(Command("coinflip"))
async def cmd_coinflip(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    bet = parse_integer(
        command.args
    )

    if bet is None:
        await reply(
            message,
            "🪙 Пример: <code>/coinflip 100</code>",
        )
        return

    async with AsyncSessionLocal() as session:
        result = await play_coinflip(
            session=session,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            bet=bet,
        )

        await commit_result(
            session,
            result,
        )

    await reply(
        message,
        result.message,
    )


@router.message(Command("dice"))
async def cmd_dice(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    bet = parse_integer(
        command.args
    )

    if bet is None:
        await reply(
            message,
            "🎲 Пример: <code>/dice 100</code>",
        )
        return

    async with AsyncSessionLocal() as session:
        result = await play_dice(
            session=session,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            bet=bet,
        )

        await commit_result(
            session,
            result,
        )

    await reply(
        message,
        result.message,
    )


@router.message(Command("slots"))
async def cmd_slots(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    bet = parse_integer(
        command.args
    )

    if bet is None:
        await reply(
            message,
            "🎰 Пример: <code>/slots 100</code>",
        )
        return

    async with AsyncSessionLocal() as session:
        result = await play_slots(
            session=session,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            bet=bet,
        )

        await commit_result(
            session,
            result,
        )

    await reply(
        message,
        result.message,
    )


@router.message(Command("roulette"))
async def cmd_roulette(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    args = (
        command.args or ""
    ).split()

    if len(args) < 2:
        await reply(
            message,
            "🎡 Пример: <code>/roulette 100 red</code>",
        )
        return

    bet = parse_integer(args[0])

    if bet is None:
        await reply(
            message,
            "❌ Некорректная ставка.",
        )
        return

    async with AsyncSessionLocal() as session:
        result = await play_roulette(
            session=session,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            bet=bet,
            choice=args[1],
        )

        await commit_result(
            session,
            result,
        )

    await reply(
        message,
        result.message,
    )


@router.message(Command("guess"))
async def cmd_guess(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    args = (
        command.args or ""
    ).split()

    if len(args) != 2:
        await reply(
            message,
            "🔢 Пример: <code>/guess 100 5</code>",
        )
        return

    bet = parse_integer(args[0])
    number = parse_integer(args[1])

    if bet is None or number is None:
        await reply(
            message,
            "❌ Некорректные параметры.",
        )
        return

    async with AsyncSessionLocal() as session:
        result = await play_guess(
            session=session,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            bet=bet,
            number=number,
        )

        await commit_result(
            session,
            result,
        )

    await reply(
        message,
        result.message,
    )


@router.message(Command("football"))
async def cmd_football(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    bet = parse_integer(
        command.args
    )

    if bet is None:
        await reply(
            message,
            "⚽ Пример: <code>/football 100</code>",
        )
        return

    async with AsyncSessionLocal() as session:
        result = await play_football(
            session=session,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            bet=bet,
        )

        await commit_result(
            session,
            result,
        )

    await reply(
        message,
        result.message,
    )


@router.message(Command("basketball"))
async def cmd_basketball(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    bet = parse_integer(
        command.args
    )

    if bet is None:
        await reply(
            message,
            "🏀 Пример: <code>/basketball 100</code>",
        )
        return

    async with AsyncSessionLocal() as session:
        result = await play_basketball(
            session=session,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            bet=bet,
        )

        await commit_result(
            session,
            result,
        )

    await reply(
        message,
        result.message,
    )


@router.message(Command("blackjack"))
async def cmd_blackjack(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    bet = parse_integer(
        command.args
    )

    if bet is None:
        await reply(
            message,
            "🃏 Пример: <code>/blackjack 100</code>",
        )
        return

    async with AsyncSessionLocal() as session:
        result = await play_blackjack(
            session=session,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            bet=bet,
        )

        await commit_result(
            session,
            result,
        )

    await reply(
        message,
        result.message,
    )


@router.message(Command("crash"))
async def cmd_crash(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    args = (
        command.args or ""
    ).split()

    if not args:
        await reply(
            message,
            "🚀 Пример: <code>/crash 100 2.00</code>",
        )
        return

    bet = parse_integer(args[0])

    if bet is None:
        await reply(
            message,
            "❌ Некорректная ставка.",
        )
        return

    cashout = 2.0

    if len(args) >= 2:
        try:
            cashout = float(args[1])
        except ValueError:
            await reply(
                message,
                "❌ Некорректный множитель.",
            )
            return

    async with AsyncSessionLocal() as session:
        result = await play_crash(
            session=session,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            bet=bet,
            cashout_multiplier=cashout,
        )

        await commit_result(
            session,
            result,
        )

    await reply(
        message,
        result.message,
    )


@router.message(Command("ttt"))
async def cmd_ttt(
    message: Message,
) -> None:
    if not message.from_user:
        return

    await reply(
        message,
        (
            "⭕❌ <b>Крестики-нолики</b>\n\n"
            "Выбери ставку:"
        ),
        reply_markup=ttt_start_keyboard(),
        delete_after=0,
    )


@router.callback_query(
    F.data.startswith("game:")
)
async def callback_game(
    callback: CallbackQuery,
) -> None:
    if (
        not callback.message
        or not callback.from_user
    ):
        await callback.answer()
        return

    game_type = (
        callback.data or ""
    ).split(
        ":",
        1,
    )[1]

    if game_type not in GAME_TITLES:
        await callback.answer(
            "Неизвестная игра.",
            show_alert=True,
        )
        return

    async with AsyncSessionLocal() as session:
        member = await get_or_create_member(
            session=session,
            chat_id=callback.message.chat.id,
            user_id=callback.from_user.id,
        )

        if not game_unlocked(
            member,
            game_type,
        ):
            required = get_feature_required_level(
                game_type
            )

            await callback.answer(
                (
                    f"🔒 Игра открывается на "
                    f"<b>{required}</b> уровне.\n"
                    f"Твой уровень: <b>{member.level}</b>."
                ),
                show_alert=True,
            )
            return

    if game_type == "roulette":
        await callback.answer()

        await callback_edit(
            callback,
            (
                "<b>🎡 Рулетка</b>\n\n"
                "Сначала выбери ставку:"
            ),
            reply_markup=game_bet_keyboard(
                "roulette"
            ),
        )
        return

    if game_type == "guess":
        await callback.answer()

        await callback_edit(
            callback,
            (
                "<b>🔢 Угадай число</b>\n\n"
                "Сначала выбери ставку:"
            ),
            reply_markup=game_bet_keyboard(
                "guess"
            ),
        )
        return

    if game_type == "crash":
        await callback.answer()

        await callback_edit(
            callback,
            (
                "<b>🚀 Crash</b>\n\n"
                "Сначала выбери ставку:"
            ),
            reply_markup=game_bet_keyboard(
                "crash"
            ),
        )
        return

    if game_type == "tictactoe":
        await callback.answer()

        await callback_edit(
            callback,
            (
                "⭕❌ <b>Крестики-нолики</b>\n\n"
                "Выбери ставку:"
            ),
            reply_markup=ttt_start_keyboard(),
        )
        return

    await callback.answer()

    await callback_edit(
        callback,
        (
            f"<b>{GAME_TITLES[game_type]}</b>\n\n"
            "Выбери ставку:"
        ),
        reply_markup=game_bet_keyboard(
            game_type
        ),
    )


@router.callback_query(
    F.data.startswith("gamebet:")
)
async def callback_game_bet(
    callback: CallbackQuery,
) -> None:
    if (
        not callback.message
        or not callback.from_user
    ):
        await callback.answer()
        return

    parts = (
        callback.data or ""
    ).split(":")
    
    if len(parts) != 3:
        await callback.answer(
            "Некорректная ставка.",
            show_alert=True,
        )
        return

    game_type = parts[1]
    bet = parse_integer(parts[2])

    if game_type not in GAME_TITLES or bet is None:
        await callback.answer(
            "Некорректная игра или ставка.",
            show_alert=True,
        )
        return

    if game_type == "roulette":
        await callback.answer()

        await callback_edit(
            callback,
            (
                "<b>🎡 Рулетка</b>\n\n"
                f"Ставка: <b>{format_balance(bet)}</b> 🥜\n"
                "Выбери цвет:"
            ),
            reply_markup=roulette_bet_keyboard(
                bet
            ),
        )
        return

    if game_type == "guess":
        await callback.answer()

        await callback_edit(
            callback,
            (
                "<b>🔢 Угадай число</b>\n\n"
                f"Ставка: <b>{format_balance(bet)}</b> 🥜\n"
                "Выбери число:"
            ),
            reply_markup=guess_keyboard(
                bet
            ),
        )
        return

    if game_type == "crash":
        await callback.answer()

        await callback_edit(
            callback,
            (
                "<b>🚀 Crash</b>\n\n"
                f"Ставка: <b>{format_balance(bet)}</b> 🥜\n"
                "Выбери точку вывода:"
            ),
            reply_markup=crash_keyboard(
                bet
            ),
        )
        return

    if game_type == "tictactoe":
        await callback.answer(
            "Выбери ставку в меню TTT.",
            show_alert=True,
        )
        return

    await execute_simple_game(
        callback,
        game_type,
        bet,
    )


@router.callback_query(
    F.data.startswith("gameroulette:")
)
async def callback_game_roulette(
    callback: CallbackQuery,
) -> None:
    if (
        not callback.message
        or not callback.from_user
    ):
        await callback.answer()
        return

    parts = (
        callback.data or ""
    ).split(":")
    
    if len(parts) != 3:
        await callback.answer(
            "Некорректная ставка.",
            show_alert=True,
        )
        return

    bet = parse_integer(parts[1])
    choice = parts[2].lower()

    if (
        bet is None
        or choice not in {
            "red",
            "black",
            "green",
        }
    ):
        await callback.answer(
            "Некорректный выбор.",
            show_alert=True,
        )
        return

    async with AsyncSessionLocal() as session:
        result = await play_roulette(
            session=session,
            chat_id=callback.message.chat.id,
            user_id=callback.from_user.id,
            bet=bet,
            choice=choice,
        )

        await commit_result(
            session,
            result,
        )

    await callback.answer(
        result.answer or result.message,
        show_alert=result.show_alert,
    )

    if result.success:
        await callback_edit(
            callback,
            (
                result.message
                + "\n\n🎡 <i>Ещё одна ставка?</i>"
            ),
            reply_markup=game_bet_keyboard(
                "roulette"
            ),
        )
    else:
        await callback_edit(
            callback,
            result.message,
            reply_markup=roulette_bet_keyboard(
                bet
            ),
        )


@router.callback_query(
    F.data.startswith("gameguess:")
)
async def callback_game_guess(
    callback: CallbackQuery,
) -> None:
    if (
        not callback.message
        or not callback.from_user
    ):
        await callback.answer()
        return

    parts = (
        callback.data or ""
    ).split(":")
    
    if len(parts) != 3:
        await callback.answer(
            "Некорректный выбор.",
            show_alert=True,
        )
        return

    bet = parse_integer(parts[1])
    number = parse_integer(parts[2])

    if (
        bet is None
        or number is None
        or not 1 <= number <= 10
    ):
        await callback.answer(
            "Некорректный выбор.",
            show_alert=True,
        )
        return

    async with AsyncSessionLocal() as session:
        result = await play_guess(
            session=session,
            chat_id=callback.message.chat.id,
            user_id=callback.from_user.id,
            bet=bet,
            number=number,
        )

        await commit_result(
            session,
            result,
        )

    await callback.answer(
        result.answer or result.message,
        show_alert=result.show_alert,
    )

    await callback_edit(
        callback,
        result.message,
        reply_markup=game_bet_keyboard(
            "guess"
        ),
    )


@router.callback_query(
    F.data.startswith("gamecrash:")
)
async def callback_game_crash(
    callback: CallbackQuery,
) -> None:
    if (
        not callback.message
        or not callback.from_user
    ):
        await callback.answer()
        return

    parts = (
        callback.data or ""
    ).split(":")
    
    if len(parts) != 3:
        await callback.answer(
            "Некорректный выбор.",
            show_alert=True,
        )
        return

    bet = parse_integer(parts[1])

    try:
        multiplier = float(parts[2])
    except (TypeError, ValueError):
        multiplier = 0.0

    if bet is None:
        await callback.answer(
            "Некорректная ставка.",
            show_alert=True,
        )
        return

    async with AsyncSessionLocal() as session:
        result = await play_crash(
            session=session,
            chat_id=callback.message.chat.id,
            user_id=callback.from_user.id,
            bet=bet,
            cashout_multiplier=multiplier,
        )

        await commit_result(
            session,
            result,
        )

    await callback.answer(
        result.answer or result.message,
        show_alert=result.show_alert,
    )

    await callback_edit(
        callback,
        result.message,
        reply_markup=game_bet_keyboard(
            "crash"
        ),
    )


@router.callback_query(
    F.data.startswith("gamettt:")
)
async def callback_ttt_start(
    callback: CallbackQuery,
) -> None:
    if (
        not callback.message
        or not callback.from_user
    ):
        await callback.answer()
        return

    bet = parse_integer(
        (callback.data or "").split(
            ":",
            1,
        )[1]
    )

    if bet is None:
        await callback.answer(
            "Некорректная ставка.",
            show_alert=True,
        )
        return

    async with AsyncSessionLocal() as session:
        result = await start_tictactoe(
            session=session,
            chat_id=callback.message.chat.id,
            user_id=callback.from_user.id,
            bet=bet,
        )

        await commit_result(
            session,
            result,
        )

    await callback.answer(
        result.answer or result.message,
        show_alert=result.show_alert,
    )

    if result.success:
        await callback_edit(
            callback,
            result.message,
            reply_markup=result.keyboard,
        )
    else:
        await callback_edit(
            callback,
            result.message,
            reply_markup=ttt_start_keyboard(),
        )


@router.callback_query(
    F.data.startswith("tttjoin:")
)
async def callback_ttt_join(
    callback: CallbackQuery,
) -> None:
    if (
        not callback.message
        or not callback.from_user
    ):
        await callback.answer()
        return

    game_id = parse_integer(
        (callback.data or "").split(
            ":",
            1,
        )[1]
    )

    if game_id is None:
        await callback.answer(
            "Некорректная игра.",
            show_alert=True,
        )
        return

    async with AsyncSessionLocal() as session:
        result = await join_tictactoe(
            session=session,
            game_id=game_id,
            user_id=callback.from_user.id,
        )

        await commit_result(
            session,
            result,
        )

    await callback.answer(
        result.answer or result.message,
        show_alert=result.show_alert,
    )

    if result.success:
        await callback_edit(
            callback,
            result.message,
            reply_markup=result.keyboard,
        )


@router.callback_query(
    F.data.startswith("ttt:")
)
async def callback_ttt_move(
    callback: CallbackQuery,
) -> None:
    if (
        not callback.message
        or not callback.from_user
    ):
        await callback.answer()
        return

    parts = (
        callback.data or ""
    ).split(":")
    
    if len(parts) != 3:
        await callback.answer(
            "Некорректный ход.",
            show_alert=True,
        )
        return

    game_id = parse_integer(parts[1])
    cell = parse_integer(parts[2])

    if game_id is None or cell is None:
        await callback.answer(
            "Некорректный ход.",
            show_alert=True,
        )
        return

    async with AsyncSessionLocal() as session:
        result = await tictactoe_move(
            session=session,
            game_id=game_id,
            user_id=callback.from_user.id,
            position=cell,
        )

        await commit_result(
            session,
            result,
        )

    await callback.answer(
        result.answer or result.message,
        show_alert=result.show_alert,
    )

    if result.success:
        await callback_edit(
            callback,
            result.message,
            reply_markup=result.keyboard,
        )


@router.callback_query(
    F.data == "games:menu"
)
async def callback_games_menu(
    callback: CallbackQuery,
) -> None:
    if not callback.message:
        await callback.answer()
        return

    await callback.answer()

    await callback_edit(
        callback,
        (
            "<b>🎮 Мини-игры</b>\n\n"
            "Выбери игру:"
        ),
        reply_markup=games_keyboard(),
    )


# ============================================================================
# RP
# ============================================================================

def parse_rp_text(
    message: Message,
) -> tuple[str, str]:
    text = (
        message.text or ""
    ).strip()

    if text.startswith("/") or text.startswith("!"):
        text = text[1:].strip()

    parts = text.split()

    if not parts:
        return "", ""

    words = [
        part.lower()
        for part in parts
    ]

    candidates: set[str] = set()

    for data in RP_ACTIONS.values():
        for alias in data.get(
            "aliases",
            (),
        ):
            candidates.add(
                " ".join(
                    str(alias).lower().split()
                )
            )

    for data in ADULT_RP_ACTIONS.values():
        for alias in data.aliases:
            candidates.add(
                " ".join(
                    str(alias).lower().split()
                )
            )

    for candidate in sorted(
        candidates,
        key=lambda value: (
            len(value.split()),
            len(value),
        ),
        reverse=True,
    ):
        candidate_words = candidate.split()
        size = len(candidate_words)

        if words[:size] == candidate_words:
            return (
                candidate,
                " ".join(parts[size:]),
            )

    return (
        words[0],
        " ".join(parts[1:]),
    )


async def execute_rp(
    message: Message,
) -> Optional[ServiceResult]:
    if not message.from_user:
        return None

    action_alias, target_text = parse_rp_text(
        message
    )

    if not action_alias:
        return None

    adult_action = get_adult_rp_action(
        action_alias
    )

    if adult_action is not None:
        target_id = None

        if message.reply_to_message:
            target = message.reply_to_message.from_user

            if target:
                target_id = target.id

        if (
            target_id is None
            and target_text
        ):
            parsed = parse_integer(
                target_text.split()[0]
            )

            if parsed is not None:
                target_id = parsed

        if target_id is None:
            return ServiceResult(
                success=False,
                message=(
                    "🎭 18+ RP нужно использовать "
                    "ответом на сообщение пользователя."
                ),
                answer="Нет цели.",
                show_alert=True,
            )

        async with AsyncSessionLocal() as session:
            result = await perform_adult_rp(
                session=session,
                chat_id=message.chat.id,
                actor_id=message.from_user.id,
                target_id=target_id,
                action=adult_action.key,
            )

            await commit_result(
                session,
                result,
            )

        return result

    action = get_rp_action_by_alias(
        action_alias
    )

    if action is None:
        return None

    target_id = None

    if message.reply_to_message:
        target = message.reply_to_message.from_user

        if target:
            target_id = target.id

    if (
        target_id is None
        and target_text
    ):
        parsed = parse_integer(
            target_text.split()[0]
        )

        if parsed is not None:
            target_id = parsed

    if target_id is None:
        return ServiceResult(
            success=False,
            message=(
                "🎭 Используй RP-команду "
                "ответом на сообщение пользователя."
            ),
            answer="Нет цели.",
            show_alert=True,
        )

    async with AsyncSessionLocal() as session:
        result = await perform_rp(
            session=session,
            chat_id=message.chat.id,
            actor_id=message.from_user.id,
            target_id=target_id,
            action=action[0],
        )

        await commit_result(
            session,
            result,
        )

    return result


# ============================================================================
# MODERATION
# ============================================================================

@router.message(Command("warn"))
async def cmd_warn(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    target_id = reply_target_id(message)

    if target_id is None:
        await reply(
            message,
            "Используй /warn ответом на сообщение.",
        )
        return

    reason = (
        command.args or ""
    ).strip()

    async with AsyncSessionLocal() as session:
        result = await add_warning(
            session=session,
            chat_id=message.chat.id,
            target_user_id=target_id,
            moderator_id=message.from_user.id,
            reason=reason,
        )

        await commit_result(
            session,
            result,
        )

    await reply(
        message,
        result.message,
    )


@router.message(Command("unwarn"))
async def cmd_unwarn(
    message: Message,
) -> None:
    if not message.from_user:
        return

    target_id = reply_target_id(message)

    if target_id is None:
        await reply(
            message,
            "Используй /unwarn ответом на сообщение.",
        )
        return

    async with AsyncSessionLocal() as session:
        result = await remove_warning(
            session=session,
            chat_id=message.chat.id,
            user_id=target_id,
            moderator_id=message.from_user.id,
        )

        await commit_result(
            session,
            result,
        )

    await reply(
        message,
        result.message,
    )


@router.message(Command("warnings"))
async def cmd_warnings(
    message: Message,
) -> None:
    if not message.from_user:
        return

    target_id = reply_target_id(message)

    if target_id is None:
        target_id = message.from_user.id

    async with AsyncSessionLocal() as session:
        text = await get_warnings(
            session=session,
            chat_id=message.chat.id,
            user_id=target_id,
        )

    await reply(
        message,
        text,
    )


@router.message(Command("mute"))
async def cmd_mute(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    target_id = reply_target_id(message)

    if target_id is None:
        await reply(
            message,
            "🔇 Используй /mute ответом на сообщение.",
        )
        return

    duration = 60

    args = (
        command.args or ""
    ).split()

    if args:
        parsed = parse_integer(
            args[0]
        )

        if parsed is not None:
            duration = parsed

    async with AsyncSessionLocal() as session:
        result = await moderate_mute(
            session=session,
            bot=message.bot,
            chat_id=message.chat.id,
            target_user_id=target_id,
            moderator_id=message.from_user.id,
            duration_minutes=duration,
        )

        await commit_result(
            session,
            result,
        )

    await reply(
        message,
        result.message,
    )


@router.message(Command("unmute"))
async def cmd_unmute(
    message: Message,
) -> None:
    if not message.from_user:
        return

    target_id = reply_target_id(message)

    if target_id is None:
        await reply(
            message,
            "Используй /unmute ответом на сообщение.",
        )
        return

    async with AsyncSessionLocal() as session:
        result = await moderate_unmute(
            session=session,
            bot=message.bot,
            chat_id=message.chat.id,
            target_user_id=target_id,
            moderator_id=message.from_user.id,
        )

        await commit_result(
            session,
            result,
        )

    await reply(
        message,
        result.message,
    )


@router.message(Command("ban"))
async def cmd_ban(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    target_id = reply_target_id(message)

    if target_id is None:
        await reply(
            message,
            "Используй /ban ответом на сообщение.",
        )
        return

    reason = (
        command.args or ""
    ).strip()

    async with AsyncSessionLocal() as session:
        result = await moderate_ban(
            session=session,
            bot=message.bot,
            chat_id=message.chat.id,
            target_user_id=target_id,
            moderator_id=message.from_user.id,
            reason=reason,
        )

        await commit_result(
            session,
            result,
        )

    await reply(
        message,
        result.message,
    )


@router.message(Command("unban"))
async def cmd_unban(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    target_id = parse_integer(
        (command.args or "").strip()
    )

    if target_id is None:
        await reply(
            message,
            "Пример: <code>/unban 123456789</code>",
        )
        return

    async with AsyncSessionLocal() as session:
        result = await moderate_unban(
            session=session,
            bot=message.bot,
            chat_id=message.chat.id,
            target_user_id=target_id,
            moderator_id=message.from_user.id,
        )

        await commit_result(
            session,
            result,
        )

    await reply(
        message,
        result.message,
    )


@router.message(Command("kick"))
async def cmd_kick(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    target_id = reply_target_id(message)

    if target_id is None:
        await reply(
            message,
            "Используй /kick ответом на сообщение.",
        )
        return

    reason = (
        command.args or ""
    ).strip()

    async with AsyncSessionLocal() as session:
        result = await moderate_kick(
            session=session,
            bot=message.bot,
            chat_id=message.chat.id,
            target_user_id=target_id,
            moderator_id=message.from_user.id,
            reason=reason,
        )

        await commit_result(
            session,
            result,
        )

    await reply(
        message,
        result.message,
    )


@router.message(Command("setnick"))
async def cmd_setnick(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    args = (
        command.args or ""
    ).strip()

    target_id = reply_target_id(message)

    if target_id is None:
        parts = args.split(
            maxsplit=1
        )

        if not parts:
            await reply(
                message,
                (
                    "Использование:\n"
                    "/setnick НОВЫЙ_НИК ответом\n"
                    "или /setnick USER_ID НОВЫЙ_НИК"
                ),
            )
            return

        parsed_target = parse_integer(
            parts[0]
        )

        if (
            parsed_target is not None
            and len(parts) == 2
        ):
            target_id = parsed_target
            nick = parts[1]
        else:
            target_id = message.from_user.id
            nick = args
    else:
        nick = args

    if target_id is None or not nick:
        await reply(
            message,
            "❌ Укажи пользователя и новый ник.",
        )
        return

    async with AsyncSessionLocal() as session:
        allowed, error = await check_moderation_access(
            session=session,
            chat_id=message.chat.id,
            actor_id=message.from_user.id,
            command="setnick",
        )

        if not allowed:
            await reply(
                message,
                error or "❌ Недостаточно прав.",
            )
            return

        result = await set_profile_nick(
            session=session,
            chat_id=message.chat.id,
            user_id=target_id,
            nick=nick,
        )

        await commit_result(
            session,
            result,
        )

    await reply(
        message,
        result.message,
    )


# ============================================================================
# STAFF ROLES / PERMISSIONS
# ============================================================================

@router.message(Command("setrole"))
async def cmd_setrole(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    target_id = reply_target_id(message)

    args = (
        command.args or ""
    ).split()

    if target_id is None and args:
        target_id = parse_integer(
            args[0]
        )
        args = args[1:]

    if target_id is None or not args:
        await reply(
            message,
            (
                "Использование:\n"
                "/setrole <role> ответом\n"
                "или /setrole USER_ID <role>\n\n"
                "Роли: head_admin, admin, moderator"
            ),
        )
        return

    role = args[0].lower()

    async with AsyncSessionLocal() as session:
        result = await assign_staff_role(
            session=session,
            chat_id=message.chat.id,
            actor_id=message.from_user.id,
            target_id=target_id,
            role=role,
        )

        await commit_result(
            session,
            result,
        )

    await reply(
        message,
        result.message,
    )


@router.message(Command("delrole"))
async def cmd_delrole(
    message: Message,
) -> None:
    if not message.from_user:
        return

    target_id = reply_target_id(message)

    if target_id is None:
        parts = (
            message.text or ""
        ).split()

        if len(parts) > 1:
            target_id = parse_integer(
                parts[1]
            )

    if target_id is None:
        await reply(
            message,
            (
                "Используй /delrole ответом "
                "или укажи USER_ID."
            ),
        )
        return

    async with AsyncSessionLocal() as session:
        result = await remove_staff_role(
            session=session,
            chat_id=message.chat.id,
            actor_id=message.from_user.id,
            target_id=target_id,
        )

        await commit_result(
            session,
            result,
        )

    await reply(
        message,
        result.message,
    )


@router.message(Command("setperm"))
async def cmd_setperm(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    args = (
        command.args or ""
    ).split()

    if len(args) != 2:
        await reply(
            message,
            (
                "Пример:\n"
                "<code>/setperm warn staff</code>\n\n"
                "Доступ: staff, admin, head_admin"
            ),
        )
        return

    command_name = args[0]
    scope = args[1]

    async with AsyncSessionLocal() as session:
        result = await set_moderation_permission(
            session=session,
            chat_id=message.chat.id,
            actor_id=message.from_user.id,
            command=command_name,
            scope=scope,
        )

        await commit_result(
            session,
            result,
        )

    await reply(
        message,
        result.message,
    )


# ============================================================================
# ADMIN ECONOMY
# ============================================================================

@router.message(Command("give"))
async def cmd_give(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    args = (
        command.args or ""
    ).split()

    if len(args) != 2:
        await reply(
            message,
            "Пример: <code>/give 123456789 1000</code>",
        )
        return

    target_id = parse_integer(args[0])
    amount = parse_integer(args[1])

    if (
        target_id is None
        or amount is None
        or amount <= 0
    ):
        await reply(
            message,
            "❌ Некорректные параметры.",
        )
        return

    async with AsyncSessionLocal() as session:
        result = await admin_give_money(
            session=session,
            owner_id=message.from_user.id,
            chat_id=message.chat.id,
            target_user_id=target_id,
            amount=amount,
        )

        await commit_result(
            session,
            result,
        )

    await reply(
        message,
        result.message,
    )


@router.message(Command("take"))
async def cmd_take(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    args = (
        command.args or ""
    ).split()

    if len(args) != 2:
        await reply(
            message,
            "Пример: <code>/take 123456789 1000</code>",
        )
        return

    target_id = parse_integer(args[0])
    amount = parse_integer(args[1])

    if (
        target_id is None
        or amount is None
        or amount <= 0
    ):
        await reply(
            message,
            "❌ Некорректные параметры.",
        )
        return

    async with AsyncSessionLocal() as session:
        result = await admin_take_money(
            session=session,
            owner_id=message.from_user.id,
            chat_id=message.chat.id,
            target_user_id=target_id,
            amount=amount,
        )

        await commit_result(
            session,
            result,
        )

    await reply(
        message,
        result.message,
    )


@router.message(Command("setbalance"))
async def cmd_setbalance(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    args = (
        command.args or ""
    ).split()

    if len(args) != 2:
        await reply(
            message,
            (
                "Пример: "
                "<code>/setbalance 123456789 5000</code>"
            ),
        )
        return

    target_id = parse_integer(args[0])
    amount = parse_integer(args[1])

    if (
        target_id is None
        or amount is None
        or amount < 0
    ):
        await reply(
            message,
            "❌ Некорректные параметры.",
        )
        return

    async with AsyncSessionLocal() as session:
        result = await admin_set_balance(
            session=session,
            owner_id=message.from_user.id,
            chat_id=message.chat.id,
            target_user_id=target_id,
            amount=amount,
        )

        await commit_result(
            session,
            result,
        )

    await reply(
        message,
        result.message,
    )


@router.message(Command("setlevel"))
async def cmd_setlevel(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    args = (
        command.args or ""
    ).split()

    if len(args) != 2:
        await reply(
            message,
            (
                "Пример: "
                "<code>/setlevel 123456789 10</code>"
            ),
        )
        return

    target_id = parse_integer(args[0])
    level = parse_integer(args[1])

    if (
        target_id is None
        or level is None
        or level < 1
    ):
        await reply(
            message,
            "❌ Некорректные параметры.",
        )
        return

    async with AsyncSessionLocal() as session:
        result = await admin_set_level(
            session=session,
            owner_id=message.from_user.id,
            chat_id=message.chat.id,
            target_user_id=target_id,
            level=level,
        )

        await commit_result(
            session,
            result,
        )

    await reply(
        message,
        result.message,
    )


# ============================================================================
# GIVEAWAYS
# ============================================================================

@router.message(Command("giveaway"))
async def cmd_giveaway(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    args = (
        command.args or ""
    ).split(
        maxsplit=3
    )

    if len(args) < 3:
        await reply(
            message,
            (
                "Формат:\n"
                "<code>/giveaway peanuts 100 60</code>\n"
                "<code>/giveaway item ITEM_CODE 60</code>\n"
                "<code>/giveaway external описание 60</code>\n\n"
                "Последнее число — длительность в минутах."
            ),
        )
        return

    prize_type = args[0].lower()

    try:
        duration_minutes = int(
            args[-1]
        )
    except ValueError:
        await reply(
            message,
            "❌ Длительность должна быть числом минут.",
        )
        return

    if duration_minutes <= 0:
        await reply(
            message,
            "❌ Длительность должна быть больше 0.",
        )
        return

    prize_amount = None
    prize_item_code = None
    prize_description = None

    if prize_type == "peanuts":
        prize_amount = parse_integer(
            args[1]
        )

        if (
            prize_amount is None
            or prize_amount <= 0
        ):
            await reply(
                message,
                (
                    "❌ Укажи положительное "
                    "количество арахиса."
                ),
            )
            return

    elif prize_type == "item":
        prize_item_code = args[1]

    elif prize_type == "external":
        prize_description = " ".join(
            args[1:-1]
        ).strip()

        if not prize_description:
            await reply(
                message,
                "❌ Укажи описание внешнего приза.",
            )
            return

    else:
        await reply(
            message,
            "❌ Тип приза: peanuts, item или external.",
        )
        return

    ends_at = datetime.utcnow() + timedelta(
        minutes=duration_minutes
    )

    async with AsyncSessionLocal() as session:
        allowed, error = await check_moderation_access(
            session=session,
            chat_id=message.chat.id,
            actor_id=message.from_user.id,
            command="giveaway",
        )

        if not allowed:
            await reply(
                message,
                error or "❌ Недостаточно прав.",
            )
            return

        result = await create_giveaway(
            session=session,
            chat_id=message.chat.id,
            creator_id=message.from_user.id,
            prize_type=prize_type,
            ends_at=ends_at,
            prize_amount=prize_amount,
            prize_item_code=prize_item_code,
            prize_description=prize_description,
        )

        await commit_result(
            session,
            result,
        )

    await reply(
        message,
        result.message,
        reply_markup=result.keyboard,
        delete_after=0,
    )


@router.callback_query(
    F.data.startswith("giveaway:join:")
)
async def callback_giveaway_join(
    callback: CallbackQuery,
) -> None:
    if (
        not callback.message
        or not callback.from_user
    ):
        await callback.answer()
        return

    parts = (
        callback.data or ""
    ).split(":")
    
    giveaway_id = (
        parse_integer(parts[2])
        if len(parts) == 3
        else None
    )

    if giveaway_id is None:
        await callback.answer(
            "Некорректный розыгрыш.",
            show_alert=True,
        )
        return

    async with AsyncSessionLocal() as session:
        result = await join_giveaway(
            session=session,
            giveaway_id=giveaway_id,
            chat_id=callback.message.chat.id,
            user_id=callback.from_user.id,
        )

        await commit_result(
            session,
            result,
        )

    await callback.answer(
        result.answer or result.message,
        show_alert=result.show_alert,
    )


@router.message(Command("giveaway_join"))
async def cmd_giveaway_join(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    giveaway_id = parse_integer(
        command.args
    )

    if giveaway_id is None:
        await reply(
            message,
            "Пример: <code>/giveaway_join 123</code>",
        )
        return

    async with AsyncSessionLocal() as session:
        result = await join_giveaway(
            session=session,
            giveaway_id=giveaway_id,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
        )

        await commit_result(
            session,
            result,
        )

    await reply(
        message,
        result.message,
    )


@router.message(Command("giveaway_finish"))
async def cmd_giveaway_finish(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    giveaway_id = parse_integer(
        command.args
    )

    if giveaway_id is None:
        await reply(
            message,
            "Пример: <code>/giveaway_finish 123</code>",
        )
        return

    async with AsyncSessionLocal() as session:
        allowed, error = await check_moderation_access(
            session=session,
            chat_id=message.chat.id,
            actor_id=message.from_user.id,
            command="giveaway",
        )

        if not allowed:
            await reply(
                message,
                error or "❌ Недостаточно прав.",
            )
            return

        result = await finish_giveaway(
            session=session,
            giveaway_id=giveaway_id,
            chat_id=message.chat.id,
        )

        await commit_result(
            session,
            result,
        )

    await reply(
        message,
        result.message,
    )


# ============================================================================
# INLINE SECTION NAVIGATION
# ============================================================================

async def _edit_profile_from_callback(
    callback: CallbackQuery,
) -> None:
    if not callback.message or not callback.from_user:
        return

    async with AsyncSessionLocal() as session:
        text, keyboard = await render_profile(
            session,
            callback.message.chat.id,
            callback.from_user.id,
        )

    await callback_edit(
        callback,
        text,
        reply_markup=keyboard,
    )


async def _edit_stats_from_callback(
    callback: CallbackQuery,
) -> None:
    if not callback.message or not callback.from_user:
        return

    async with AsyncSessionLocal() as session:
        text = await format_stats(
            session=session,
            chat_id=callback.message.chat.id,
            user_id=callback.from_user.id,
        )
        await session.commit()

    await callback_edit(
        callback,
        text,
        reply_markup=section_keyboard(),
    )


async def _edit_balance_from_callback(
    callback: CallbackQuery,
) -> None:
    if not callback.message or not callback.from_user:
        return

    async with AsyncSessionLocal() as session:
        balance = await balance_user(
            session=session,
            chat_id=callback.message.chat.id,
            user_id=callback.from_user.id,
        )
        await session.commit()

    await callback_edit(
        callback,
        f"🥜 Баланс: <b>{format_balance(balance)}</b>",
        reply_markup=section_keyboard(
            include_games=False
        ),
    )


async def _edit_inventory_from_callback(
    callback: CallbackQuery,
) -> None:
    if not callback.message or not callback.from_user:
        return

    async with AsyncSessionLocal() as session:
        text = await format_inventory(
            session=session,
            chat_id=callback.message.chat.id,
            user_id=callback.from_user.id,
        )

        case_keyboard = await build_case_keyboard(
            session=session,
            chat_id=callback.message.chat.id,
            user_id=callback.from_user.id,
        )

        await session.commit()

    await callback_edit(
        callback,
        text,
        reply_markup=inventory_keyboard(
            case_keyboard
        ),
    )


async def _edit_tag_from_callback(
    callback: CallbackQuery,
) -> None:
    if not callback.message or not callback.from_user:
        return

    async with AsyncSessionLocal() as session:
        keyboard = await get_tag_keyboard(
            session=session,
            chat_id=callback.message.chat.id,
            user_id=callback.from_user.id,
        )
        await session.commit()

    rows = list(
        keyboard.inline_keyboard
    )
    rows.extend(
        section_keyboard(
            include_games=False
        ).inline_keyboard
    )

    await callback_edit(
        callback,
        (
            "🏷 <b>Твои теги</b>\n\n"
            "Выбери полученный тег:"
        ),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=rows
        ),
    )


async def _edit_battlepass_from_callback(
    callback: CallbackQuery,
) -> None:
    if not callback.message or not callback.from_user:
        return

    async with AsyncSessionLocal() as session:
        member = await get_or_create_member(
            session=session,
            chat_id=callback.message.chat.id,
            user_id=callback.from_user.id,
        )

        level = min(
            BATTLE_PASS_MAX_LEVEL,
            max(
                1,
                member.battle_pass_level,
            ),
        )

        current_xp = member.battle_pass_xp
        level_xp = current_xp % 100

        remaining = (
            0
            if level >= BATTLE_PASS_MAX_LEVEL
            else 100 - level_xp
        )

        reward_text = "—"

        reward = BATTLE_PASS_REWARDS.get(level)

        if reward is not None:
            reward_text = str(
                getattr(
                    reward,
                    "description",
                    None,
                )
                or getattr(
                    reward,
                    "name",
                    None,
                )
                or getattr(
                    reward,
                    "reward_type",
                    None,
                )
                or reward
            )

        await session.commit()

    await callback_edit(
        callback,
        (
            "<b>🏆 Battle Pass</b>\n\n"
            f"Уровень: <b>{level}/{BATTLE_PASS_MAX_LEVEL}</b>\n"
            f"XP сезона: <b>{current_xp}</b>\n"
            f"До следующего уровня: <b>{remaining}</b>\n\n"
            f"🎁 Награда текущего уровня:\n"
            f"{escape(reward_text)}"
        ),
        reply_markup=section_keyboard(
            include_games=False
        ),
    )


async def _edit_top_from_callback(
    callback: CallbackQuery,
) -> None:
    if not callback.message:
        return

    if not is_group(callback.message):
        await callback.answer(
            "🏆 Рейтинг доступен в группах.",
            show_alert=True,
        )
        return

    async with AsyncSessionLocal() as session:
        text = await get_leaderboard(
            session=session,
            chat_id=callback.message.chat.id,
        )
        await session.commit()

    await callback_edit(
        callback,
        text,
        reply_markup=section_keyboard(
            include_games=False
        ),
    )


async def _edit_topsize_from_callback(
    callback: CallbackQuery,
) -> None:
    if not callback.message:
        return

    if not is_group(callback.message):
        await callback.answer(
            "📏 Рейтинг доступен в группах.",
            show_alert=True,
        )
        return

    async with AsyncSessionLocal() as session:
        members = await get_top_by_penis_size(
            session=session,
            chat_id=callback.message.chat.id,
            limit=10,
        )

        lines = [
            "📏 <b>Топ по размеру</b>"
        ]

        for index, member in enumerate(
            members,
            1,
        ):
            lines.append(
                f'{index}. '
                f'<a href="tg://user?id={member.user_id}">'
                "Игрок</a> — "
                f"<b>{member.penis_size:.2f} см</b>"
            )

        await session.commit()

    await callback_edit(
        callback,
        "\n".join(lines),
        reply_markup=section_keyboard(
            include_games=False
        ),
    )


@router.callback_query(
    F.data.startswith("nav:")
)
async def callback_navigation(
    callback: CallbackQuery,
) -> None:
    if not callback.message:
        await callback.answer()
        return

    action = (
        callback.data or ""
    ).split(
        ":",
        1,
    )[1]

    handlers: dict[
        str,
        Callable[[CallbackQuery], Awaitable[None]],
    ] = {
        "profile": _edit_profile_from_callback,
        "stats": _edit_stats_from_callback,
        "balance": _edit_balance_from_callback,
        "inventory": _edit_inventory_from_callback,
        "tag": _edit_tag_from_callback,
        "battlepass": _edit_battlepass_from_callback,
        "top": _edit_top_from_callback,
        "topsize": _edit_topsize_from_callback,
    }

    if action == "games":
        await callback.answer()

        await callback_edit(
            callback,
            (
                "<b>🎮 Мини-игры</b>\n\n"
                "Выбери игру:"
            ),
            reply_markup=games_keyboard(),
        )
        return

    handler = handlers.get(action)

    if handler is None:
        await callback.answer(
            "Неизвестный раздел.",
            show_alert=True,
        )
        return

    await callback.answer()

    await handler(
        callback
    )


# ============================================================================
# CASES CALLBACK
# ============================================================================

@router.callback_query(
    F.data.startswith("case:")
)
async def callback_case(
    callback: CallbackQuery,
) -> None:
    if (
        not callback.message
        or not callback.from_user
    ):
        await callback.answer()
        return

    case_code = (
        callback.data or ""
    ).split(
        ":",
        1,
    )[1]

    if case_code not in CASE_REWARDS:
        await callback.answer(
            "Неизвестный кейс.",
            show_alert=True,
        )
        return

    async with AsyncSessionLocal() as session:
        result = await open_case(
            session=session,
            chat_id=callback.message.chat.id,
            user_id=callback.from_user.id,
            case_code=case_code,
        )

        await commit_result(
            session,
            result,
        )

        inventory_text = await format_inventory(
            session=session,
            chat_id=callback.message.chat.id,
            user_id=callback.from_user.id,
        )

        case_keyboard = await build_case_keyboard(
            session=session,
            chat_id=callback.message.chat.id,
            user_id=callback.from_user.id,
        )

        await session.commit()

    await callback.answer(
        result.answer or result.message,
        show_alert=result.show_alert,
    )

    await callback_edit(
        callback,
        inventory_text,
        reply_markup=inventory_keyboard(
            case_keyboard
        ),
    )


# ============================================================================
# ORDINARY MESSAGE / XP / RP
# ============================================================================

@router.message(F.text)
async def ordinary_message(
    message: Message,
) -> None:
    if not message.from_user:
        return

    if message.from_user.is_bot:
        return

    if not is_group(message):
        return

    text = (
        message.text or ""
    ).strip()

    if not text:
        return

    if text in NAVIGATION_BUTTONS:
        return

    result = await execute_rp(
        message
    )

    if result is not None:
        if result.message:
            await reply(
                message,
                result.message,
            )
        return

    async with AsyncSessionLocal() as session:
        result = await handle_message(
            session=session,
            message=message,
        )

        await commit_result(
            session,
            result,
        )

    if result.level_up_message:
        await reply(
            message,
            result.level_up_message,
        )


# ============================================================================
# GLOBAL ERRORS
# ============================================================================

@router.errors()
async def global_error_handler(
    event,
) -> None:
    logger.exception(
        "Необработанная ошибка Telegram handler: %s",
        event.exception,
    )


# ============================================================================
# REGISTRATION
# ============================================================================

def register_handlers(
    dispatcher,
) -> None:
    dispatcher.include_router(
        router
    )

    logger.info(
        "Основной router зарегистрирован."
    )