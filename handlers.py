"""
Ezzzy Game Bot
==============
handlers.py — Telegram handlers.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from html import escape
from typing import Optional

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from core import (
    ADULT_RP_ACTIONS,
    BATTLE_PASS_MAX_LEVEL,
    BATTLE_PASS_REWARDS,
    RP_ACTIONS,
    get_adult_rp_action,
    get_rp_action_by_alias,
)

from database import (
    AsyncSessionLocal,
    User,
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
    get_game_list,
    get_leaderboard,
    get_tag_keyboard,
    get_warnings,
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
    play_coinflip,
    play_dice,
    play_football,
    play_guess,
    play_roulette,
    play_slots,
    purge_messages,
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
# GENERAL
# ============================================================================


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


async def reply(
    message: Message,
    text: str,
    **kwargs,
) -> Optional[Message]:
    if not text:
        return None

    try:
        return await message.answer(text, **kwargs)
    except TelegramForbiddenError:
        logger.warning(
            "Telegram запретил отправку сообщения chat_id=%s",
            message.chat.id,
        )
    except TelegramBadRequest:
        logger.exception(
            "Telegram отклонил сообщение chat_id=%s",
            message.chat.id,
        )

    return None


async def get_or_prepare_member(message: Message):
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


def games_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🪙 Монетка",
                    callback_data="game:coinflip",
                ),
                InlineKeyboardButton(
                    text="🎲 Кубики",
                    callback_data="game:dice",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🎰 Слоты",
                    callback_data="game:slots",
                ),
                InlineKeyboardButton(
                    text="🎡 Рулетка",
                    callback_data="game:roulette",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔢 Угадай число",
                    callback_data="game:guess",
                ),
                InlineKeyboardButton(
                    text="⚽ Футбол",
                    callback_data="game:football",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🏀 Баскетбол",
                    callback_data="game:basketball",
                ),
                InlineKeyboardButton(
                    text="⭕❌ TTT",
                    callback_data="game:tictactoe",
                ),
            ],
        ]
    )


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ Игры",
                    callback_data="games:menu",
                )
            ]
        ]
    )


# ============================================================================
# PROFILE TARGET
# ============================================================================


async def resolve_user_id(
    message: Message,
    command: Optional[CommandObject] = None,
) -> Optional[int]:
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user.id

    args = (command.args if command else "") or ""
    args = args.strip()

    if not args:
        return message.from_user.id if message.from_user else None

    first = args.split()[0]

    parsed = parse_integer(first)

    if parsed is not None:
        return parsed

    username = first.lstrip("@").lower()

    if not username:
        return None

    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        result = await session.execute(
            select(User.id).where(
                User.username.ilike(username)
            )
        )

        return result.scalar_one_or_none()


def reply_target_id(message: Message) -> Optional[int]:
    if not message.reply_to_message:
        return None

    if not message.reply_to_message.from_user:
        return None

    return message.reply_to_message.from_user.id


# ============================================================================
# START / HELP
# ============================================================================


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
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
            "🎭 RP\n"
            "🛡 Модерация\n\n"
            "Используй /help."
        ),
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
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
            "/ttt\n\n"
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
            "/purge\n"
            "/setnick\n"
            "/setrole\n"
            "/delrole\n"
            "/setperm\n\n"
            "<b>🎁 Розыгрыши</b>\n"
            "/giveaway\n"
            "/giveaway_join ID\n"
            "/giveaway_finish ID"
        ),
    )


# ============================================================================
# PROFILE
# ============================================================================


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
            text = await format_profile(
                session=session,
                chat_id=message.chat.id,
                user_id=target_id,
            )
        else:
            text = await format_other_profile(
                session=session,
                chat_id=message.chat.id,
                user_id=target_id,
            )

        keyboard = None

        if target_id == message.from_user.id:
            member = await get_or_create_member(
                session=session,
                chat_id=message.chat.id,
                user_id=target_id,
            )

            buttons = []

            if member.has_disease:
                buttons.append(
                    [
                        InlineKeyboardButton(
                            text="💊 Лекарство",
                            callback_data=f"profile:medicine:{target_id}",
                        ),
                        InlineKeyboardButton(
                            text="🧑‍⚕️ Венеролог",
                            callback_data=f"profile:venereologist:{target_id}",
                        ),
                    ]
                )

            if member.has_child:
                buttons.append(
                    [
                        InlineKeyboardButton(
                            text="🏥 Аборт",
                            callback_data=f"profile:abort:{target_id}",
                        )
                    ]
                )

            if buttons:
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=buttons
                )

    await reply(
        message,
        text,
        reply_markup=keyboard,
    )


@router.callback_query(F.data.startswith("profile:"))
async def callback_profile_action(
    callback: CallbackQuery,
) -> None:
    if not callback.message or not callback.from_user:
        await callback.answer()
        return

    parts = (callback.data or "").split(":")

    if len(parts) != 3:
        await callback.answer(
            "Некорректное действие.",
            show_alert=True,
        )
        return

    action = parts[1]

    try:
        target_id = int(parts[2])
    except ValueError:
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

        if result.success:
            await session.commit()

        text = await format_profile(
            session=session,
            chat_id=callback.message.chat.id,
            user_id=target_id,
        )

        member = await get_or_create_member(
            session=session,
            chat_id=callback.message.chat.id,
            user_id=target_id,
        )

        buttons = []

        if member.has_disease:
            buttons.append(
                [
                    InlineKeyboardButton(
                        text="💊 Лекарство",
                        callback_data=f"profile:medicine:{target_id}",
                    ),
                    InlineKeyboardButton(
                        text="🧑‍⚕️ Венеролог",
                        callback_data=f"profile:venereologist:{target_id}",
                    ),
                ]
            )

        if member.has_child:
            buttons.append(
                [
                    InlineKeyboardButton(
                        text="🏥 Аборт",
                        callback_data=f"profile:abort:{target_id}",
                    )
                ]
            )

        keyboard = (
            InlineKeyboardMarkup(
                inline_keyboard=buttons
            )
            if buttons
            else None
        )

    await callback.answer(
        result.answer or result.message,
        show_alert=result.show_alert,
    )

    try:
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
        )
    except TelegramBadRequest:
        pass


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    if not message.from_user:
        return

    await get_or_prepare_member(message)

    target_id = await resolve_user_id(message)

    if target_id is None:
        return

    async with AsyncSessionLocal() as session:
        text = await format_stats(
            session=session,
            chat_id=message.chat.id,
            user_id=target_id,
        )

    await reply(message, text)


@router.message(Command("balance"))
async def cmd_balance(message: Message) -> None:
    if not message.from_user:
        return

    await get_or_prepare_member(message)

    async with AsyncSessionLocal() as session:
        balance = await balance_user(
            session=session,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
        )

    await reply(
        message,
        f"🥜 Баланс: <b>{format_balance(balance)}</b>",
    )


@router.message(Command("inventory"))
async def cmd_inventory(message: Message) -> None:
    if not message.from_user:
        return

    await get_or_prepare_member(message)

    async with AsyncSessionLocal() as session:
        text = await format_inventory(
            session=session,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
        )

    await reply(message, text)


@router.message(Command("tag"))
async def cmd_tag(message: Message) -> None:
    if not message.from_user:
        return

    await get_or_prepare_member(message)

    async with AsyncSessionLocal() as session:
        keyboard = await get_tag_keyboard(
            session=session,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
        )

    await reply(
        message,
        (
            "🏷 <b>Твои теги</b>\n\n"
            "Выбери полученный тег:"
        ),
        reply_markup=keyboard,
    )


@router.callback_query(F.data.startswith("tagselect:"))
async def callback_tag_select(callback: CallbackQuery) -> None:
    if not callback.message or not callback.from_user:
        await callback.answer()
        return

    tag_id = parse_integer(
        callback.data.split(":", 1)[1]
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

        if result.success:
            await session.commit()

        keyboard = await get_tag_keyboard(
            session=session,
            chat_id=callback.message.chat.id,
            user_id=callback.from_user.id,
        )

    await callback.answer(
        result.answer or result.message,
        show_alert=result.show_alert,
    )

    if result.success:
        try:
            await callback.message.edit_reply_markup(
                reply_markup=keyboard,
            )
        except TelegramBadRequest:
            pass


@router.message(Command("battlepass"))
async def cmd_battlepass(message: Message) -> None:
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
            max(1, member.battle_pass_level),
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
                getattr(reward, "description", None)
                or getattr(reward, "name", None)
                or getattr(reward, "reward_type", None)
                or reward
            )

    await reply(
        message,
        (
            "<b>🏆 Battle Pass</b>\n\n"
            f"Уровень: <b>{level}/{BATTLE_PASS_MAX_LEVEL}</b>\n"
            f"XP сезона: <b>{current_xp}</b>\n"
            f"До следующего уровня: <b>{remaining}</b>\n\n"
            f"🎁 Награда текущего уровня:\n{escape(reward_text)}"
        ),
    )


@router.message(Command("top"))
async def cmd_top(message: Message) -> None:
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

    await reply(message, text)


@router.message(Command("topsize"))
async def cmd_topsize(message: Message) -> None:
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

        for index, member in enumerate(members, 1):
            lines.append(
                f'{index}. '
                f'<a href="tg://user?id={member.user_id}">Игрок</a> — '
                f"<b>{member.penis_size:.2f} см</b>"
            )

    await reply(
        message,
        "\n".join(lines),
    )


@router.message(Command("bonus"))
async def cmd_bonus(message: Message) -> None:
    if not message.from_user:
        return

    await get_or_prepare_member(message)

    async with AsyncSessionLocal() as session:
        result = await claim_daily_bonus(
            session=session,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
        )

        if result.success:
            await session.commit()

    await reply(message, result.message)


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
            "💸 Используй /pay ответом на сообщение.\n"
            "Пример: <code>/pay 500</code>",
        )
        return

    amount = parse_integer(command.args)

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

        if result.success:
            await session.commit()

    await reply(message, result.message)


@router.message(Command("masturbate"))
async def cmd_masturbate(message: Message) -> None:
    if not message.from_user:
        return

    async with AsyncSessionLocal() as session:
        result = await masturbate(
            session=session,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
        )

        if result.success:
            await session.commit()

    await reply(message, result.message)


@router.message(Command("rob"))
async def cmd_rob(message: Message) -> None:
    if not message.from_user:
        return

    if not message.reply_to_message:
        await reply(
            message,
            "🥷 Используй /rob ответом на сообщение цели.",
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

        if result.success:
            await session.commit()

    await reply(message, result.message)


# ============================================================================
# GAMES
# ============================================================================


@router.message(Command("games"))
async def cmd_games(message: Message) -> None:
    await reply(
        message,
        (
            "<b>🎮 Мини-игры</b>\n\n"
            "Выбери игру:"
        ),
        reply_markup=games_keyboard(),
    )


@router.message(Command("coinflip"))
async def cmd_coinflip(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    bet = parse_integer(command.args)

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

        if result.success:
            await session.commit()

    await reply(message, result.message)


@router.message(Command("dice"))
async def cmd_dice(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    bet = parse_integer(command.args)

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

        if result.success:
            await session.commit()

    await reply(message, result.message)


@router.message(Command("slots"))
async def cmd_slots(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    bet = parse_integer(command.args)

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

        if result.success:
            await session.commit()

    await reply(message, result.message)


@router.message(Command("roulette"))
async def cmd_roulette(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    args = (command.args or "").split()

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
            color=args[1],
        )

        if result.success:
            await session.commit()

    await reply(message, result.message)


@router.message(Command("guess"))
async def cmd_guess(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    args = (command.args or "").split()

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

        if result.success:
            await session.commit()

    await reply(message, result.message)


@router.message(Command("football"))
async def cmd_football(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    bet = parse_integer(command.args)

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

        if result.success:
            await session.commit()

    await reply(message, result.message)


@router.message(Command("basketball"))
async def cmd_basketball(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    bet = parse_integer(command.args)

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

        if result.success:
            await session.commit()

    await reply(message, result.message)


@router.message(Command("ttt"))
async def cmd_ttt(message: Message) -> None:
    if not message.from_user:
        return

    async with AsyncSessionLocal() as session:
        result = await start_tictactoe(
            session=session,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
        )

        if result.success:
            await session.commit()

    await reply(
        message,
        result.message,
        reply_markup=result.keyboard,
    )


@router.callback_query(F.data.startswith("tttjoin:"))
async def callback_ttt_join(callback: CallbackQuery) -> None:
    if not callback.message or not callback.from_user:
        await callback.answer()
        return

    try:
        game_id = int(
            (callback.data or "").split(":", 1)[1]
        )
    except (ValueError, IndexError):
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

        if result.success:
            await session.commit()

    await callback.answer(
        result.answer or result.message,
        show_alert=result.show_alert,
    )

    if result.success:
        try:
            await callback.message.edit_text(
                result.message,
                reply_markup=result.keyboard,
            )
        except TelegramBadRequest:
            pass


@router.callback_query(F.data.startswith("tttmove:"))
async def callback_ttt_move(callback: CallbackQuery) -> None:
    if not callback.message or not callback.from_user:
        await callback.answer()
        return

    parts = (callback.data or "").split(":")

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
            cell=cell,
        )

        if result.success:
            await session.commit()

    await callback.answer(
        result.answer or result.message,
        show_alert=result.show_alert,
    )

    if result.success:
        try:
            await callback.message.edit_text(
                result.message,
                reply_markup=result.keyboard,
            )
        except TelegramBadRequest:
            pass


@router.callback_query(F.data == "games:menu")
async def callback_games_menu(
    callback: CallbackQuery,
) -> None:
    if not callback.message:
        await callback.answer()
        return

    await callback.answer()

    try:
        await callback.message.edit_text(
            (
                "<b>🎮 Мини-игры</b>\n\n"
                "Выбери игру:"
            ),
            reply_markup=games_keyboard(),
        )
    except TelegramBadRequest:
        pass


# ============================================================================
# RP
# ============================================================================


def parse_rp_text(
    message: Message,
) -> tuple[str, str]:
    text = (message.text or "").strip()

    if text.startswith("/") or text.startswith("!"):
        text = text[1:].strip()

    parts = text.split()

    if not parts:
        return "", ""

    words = [part.lower() for part in parts]
    candidates: set[str] = set()

    for data in RP_ACTIONS.values():
        for alias in data.get("aliases", ()):
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

    action_alias, target_text = parse_rp_text(message)

    if not action_alias:
        return None

    adult_action = get_adult_rp_action(action_alias)

    if adult_action is not None:
        target_id = None

        if message.reply_to_message:
            target = message.reply_to_message.from_user

            if target:
                target_id = target.id

        if target_id is None and target_text:
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

            if result.success:
                await session.commit()

        return result

    action = get_rp_action_by_alias(action_alias)

    if action is None:
        return None

    target_id = None

    if message.reply_to_message:
        target = message.reply_to_message.from_user

        if target:
            target_id = target.id

    if target_id is None and target_text:
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
            action=action.key,
        )

        if result.success:
            await session.commit()

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

    reason = (command.args or "").strip()

    async with AsyncSessionLocal() as session:
        result = await add_warning(
            session=session,
            chat_id=message.chat.id,
            user_id=target_id,
            moderator_id=message.from_user.id,
            reason=reason,
        )

        if result.success:
            await session.commit()

    await reply(message, result.message)


@router.message(Command("unwarn"))
async def cmd_unwarn(message: Message) -> None:
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

        if result.success:
            await session.commit()

    await reply(message, result.message)


@router.message(Command("warnings"))
async def cmd_warnings(message: Message) -> None:
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

    await reply(message, text)


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

    args = (command.args or "").split()

    if args:
        parsed = parse_integer(args[0])

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

        if result.success:
            await session.commit()

    await reply(message, result.message)


@router.message(Command("unmute"))
async def cmd_unmute(message: Message) -> None:
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

        if result.success:
            await session.commit()

    await reply(message, result.message)


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

    reason = (command.args or "").strip()

    async with AsyncSessionLocal() as session:
        result = await moderate_ban(
            session=session,
            bot=message.bot,
            chat_id=message.chat.id,
            target_user_id=target_id,
            moderator_id=message.from_user.id,
            reason=reason,
        )

        if result.success:
            await session.commit()

    await reply(message, result.message)


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

        if result.success:
            await session.commit()

    await reply(message, result.message)


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

    reason = (command.args or "").strip()

    async with AsyncSessionLocal() as session:
        result = await moderate_kick(
            session=session,
            bot=message.bot,
            chat_id=message.chat.id,
            target_user_id=target_id,
            moderator_id=message.from_user.id,
            reason=reason,
        )

        if result.success:
            await session.commit()

    await reply(message, result.message)


@router.message(Command("purge"))
async def cmd_purge(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    amount = parse_integer(command.args)

    if amount is None:
        amount = 10

    if not 1 <= amount <= 100:
        await reply(
            message,
            "Количество сообщений должно быть от 1 до 100.",
        )
        return

    result = await purge_messages(
        bot=message.bot,
        chat_id=message.chat.id,
        moderator_id=message.from_user.id,
        count=amount,
    )

    await reply(message, result.message)


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

    args = (command.args or "").split()

    if target_id is None and args:
        target_id = parse_integer(args[0])
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

        if result.success:
            await session.commit()

    await reply(message, result.message)


@router.message(Command("delrole"))
async def cmd_delrole(message: Message) -> None:
    if not message.from_user:
        return

    target_id = reply_target_id(message)

    if target_id is None:
        target_id = parse_integer(
            (message.text or "").split(maxsplit=1)[1]
            if len((message.text or "").split()) > 1
            else ""
        )

    if target_id is None:
        await reply(
            message,
            "Используй /delrole ответом или укажи USER_ID.",
        )
        return

    async with AsyncSessionLocal() as session:
        result = await remove_staff_role(
            session=session,
            chat_id=message.chat.id,
            actor_id=message.from_user.id,
            target_id=target_id,
        )

        if result.success:
            await session.commit()

    await reply(message, result.message)


@router.message(Command("setperm"))
async def cmd_setperm(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    args = (command.args or "").split()

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

        if result.success:
            await session.commit()

    await reply(message, result.message)


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

    args = (command.args or "").split()

    if len(args) != 2:
        await reply(
            message,
            "Пример: <code>/give 123456789 1000</code>",
        )
        return

    target_id = parse_integer(args[0])
    amount = parse_integer(args[1])

    if target_id is None or amount is None or amount <= 0:
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

        if result.success:
            await session.commit()

    await reply(message, result.message)


@router.message(Command("take"))
async def cmd_take(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    args = (command.args or "").split()

    if len(args) != 2:
        await reply(
            message,
            "Пример: <code>/take 123456789 1000</code>",
        )
        return

    target_id = parse_integer(args[0])
    amount = parse_integer(args[1])

    if target_id is None or amount is None or amount <= 0:
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

        if result.success:
            await session.commit()

    await reply(message, result.message)


@router.message(Command("setbalance"))
async def cmd_setbalance(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    args = (command.args or "").split()

    if len(args) != 2:
        await reply(
            message,
            "Пример: <code>/setbalance 123456789 5000</code>",
        )
        return

    target_id = parse_integer(args[0])
    amount = parse_integer(args[1])

    if target_id is None or amount is None or amount < 0:
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

        if result.success:
            await session.commit()

    await reply(message, result.message)


@router.message(Command("setlevel"))
async def cmd_setlevel(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    args = (command.args or "").split()

    if len(args) != 2:
        await reply(
            message,
            "Пример: <code>/setlevel 123456789 10</code>",
        )
        return

    target_id = parse_integer(args[0])
    level = parse_integer(args[1])

    if target_id is None or level is None or level < 1:
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

        if result.success:
            await session.commit()

    await reply(message, result.message)


# ============================================================================
# CASES
# ============================================================================


@router.callback_query(F.data.startswith("case:"))
async def callback_case(callback: CallbackQuery) -> None:
    if not callback.message or not callback.from_user:
        await callback.answer()
        return

    case_code = callback.data.split(":", 1)[1]

    async with AsyncSessionLocal() as session:
        result = await open_case(
            session=session,
            chat_id=callback.message.chat.id,
            user_id=callback.from_user.id,
            case_code=case_code,
        )

        if result.success:
            await session.commit()

    await callback.answer(
        result.answer or result.message,
        show_alert=result.show_alert,
    )

    if callback.message:
        await reply(
            callback.message,
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

    args = (command.args or "").split(maxsplit=3)

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
        duration_minutes = int(args[-1])
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
        prize_amount = parse_integer(args[1])

        if prize_amount is None or prize_amount <= 0:
            await reply(
                message,
                "❌ Укажи положительное количество арахиса.",
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

        if result.success:
            await session.commit()

    await reply(
        message,
        result.message,
        reply_markup=result.keyboard,
    )


@router.callback_query(
    F.data.startswith("giveaway:join:")
)
async def callback_giveaway_join(
    callback: CallbackQuery,
) -> None:
    if not callback.message or not callback.from_user:
        await callback.answer()
        return

    try:
        giveaway_id = int(
            (callback.data or "").split(":")[2]
        )
    except (ValueError, IndexError):
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

        if result.success:
            await session.commit()

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

    giveaway_id = parse_integer(command.args)

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

        if result.success:
            await session.commit()

    await reply(message, result.message)


@router.message(Command("giveaway_finish"))
async def cmd_giveaway_finish(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    giveaway_id = parse_integer(command.args)

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
        )

        if result.success:
            await session.commit()

    await reply(message, result.message)


# ============================================================================
# ORDINARY MESSAGE / XP / RP
# ============================================================================


@router.message(F.text)
async def ordinary_message(message: Message) -> None:
    if not message.from_user:
        return

    if message.from_user.is_bot:
        return

    if not is_group(message):
        return

    text = (message.text or "").strip()

    if not text:
        return

    result = await execute_rp(message)

    if result is not None:
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

        if result.changed:
            await session.commit()

    if result.level_up_message:
        await reply(
            message,
            result.level_up_message,
        )


# ============================================================================
# GLOBAL ERRORS
# ============================================================================


@router.errors()
async def global_error_handler(event) -> None:
    logger.exception(
        "Необработанная ошибка Telegram handler: %s",
        event.exception,
    )


# ============================================================================
# REGISTRATION
# ============================================================================


def register_handlers(dispatcher) -> None:
    dispatcher.include_router(router)

    logger.info(
        "Основной router зарегистрирован."
    )