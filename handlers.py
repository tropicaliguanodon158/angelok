"""
Ezzzy Game Bot
==============
handlers.py — Telegram handlers.
"""

from __future__ import annotations

import logging
from html import escape
from typing import Optional

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from database import (
    AsyncSessionLocal,
    get_or_create_chat,
    get_or_create_member,
    get_or_create_user,
)

from services import (
    ServiceResult,
    balance_user,
    claim_daily_bonus,
    create_game,
    format_balance,
    format_inventory,
    format_profile,
    format_stats,
    get_game_list,
    get_leaderboard,
    handle_message,
    play_coinflip,
    play_dice,
    play_roulette,
    play_slots,
    play_guess,
    start_tictactoe,
    tictactoe_move,
    set_profile_nick,
    set_profile_tag,
    perform_rp,
    moderate_ban,
    moderate_kick,
    moderate_mute,
    moderate_unmute,
    moderate_unban,
    add_warning,
    remove_warning,
    get_warnings,
    purge_messages,
    transfer_money,
    admin_give_money,
    admin_take_money,
    admin_set_level,
    admin_set_balance,
    get_tag_keyboard,
    select_tag,
    open_case,
)

logger = logging.getLogger("EzzzyGameBot.handlers")

router = Router(name="main")


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
    try:
        return await message.answer(text, **kwargs)
    except TelegramForbiddenError:
        logger.warning(
            "Telegram запретил отправку сообщения chat_id=%s",
            message.chat.id,
        )
    except TelegramBadRequest:
        logger.exception("Telegram отклонил сообщение.")

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
            "/stats\n"
            "/balance\n"
            "/inventory\n"
            "/tag\n"
            "/battlepass\n"
            "/top\n\n"
            "<b>🎮 Игры</b>\n"
            "/games\n"
            "/bonus\n"
            "/coinflip 100\n"
            "/dice 100\n"
            "/slots 100\n"
            "/roulette 100 red\n"
            "/guess 100 50\n"
            "/ttt\n\n"
            "<b>💰 Экономика</b>\n"
            "/pay 100\n"
            "/rob\n\n"
            "<b>🎭 RP</b>\n"
            "обычные RP-команды работают текстом\n"
            "18+ RP-команды работают текстом\n"
            "или через reply\n\n"
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
        ),
    )


@router.message(Command("profile"))
async def cmd_profile(message: Message) -> None:
    if not message.from_user:
        return

    await get_or_prepare_member(message)

    async with AsyncSessionLocal() as session:
        text = await format_profile(
            session=session,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
        )

    await reply(message, text)


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    if not message.from_user:
        return

    await get_or_prepare_member(message)

    async with AsyncSessionLocal() as session:
        text = await format_stats(
            session=session,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
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
            "Выбери тег кнопкой ниже."
        ),
        reply_markup=keyboard,
    )


@router.callback_query(F.data.startswith("tagselect:"))
async def callback_tag_select(callback: CallbackQuery) -> None:
    if not callback.from_user or not callback.message:
        await callback.answer()
        return

    raw_id = callback.data.split(":", 1)[1]
    tag_id = parse_integer(raw_id)

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

    await callback.answer(
        result.answer or result.message,
        show_alert=result.show_alert,
    )

    if result.success:
        async with AsyncSessionLocal() as session:
            keyboard = await get_tag_keyboard(
                session=session,
                chat_id=callback.message.chat.id,
                user_id=callback.from_user.id,
            )

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
        from services import format_battle_pass

        result = await format_battle_pass(
            session=session,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
        )

    await reply(message, result)


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
        await reply(
            message,
            "❌ Не удалось определить получателя.",
        )
        return

    if target.id == message.from_user.id:
        await reply(
            message,
            "😐 Самому себе переводить нельзя.",
        )
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


@router.message(Command("rob"))
async def cmd_rob(message: Message) -> None:
    if not message.from_user:
        return

    target = (
        message.reply_to_message.from_user
        if message.reply_to_message
        else None
    )

    if target is None:
        await reply(
            message,
            "🥷 Используй /rob ответом на сообщение цели.",
        )
        return

    if target.id == message.from_user.id:
        await reply(
            message,
            "😐 Себя ограбить нельзя.",
        )
        return

    async with AsyncSessionLocal() as session:
        from services import rob_user

        result = await rob_user(
            session=session,
            chat_id=message.chat.id,
            actor_id=message.from_user.id,
            target_id=target.id,
        )

        if result.success:
            await session.commit()

    await reply(message, result.message)


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
            (
                "🎡 Формат:\n"
                "<code>/roulette 100 red</code>\n\n"
                "Варианты: red, black, green"
            ),
        )
        return

    bet = parse_integer(args[0])
    choice = args[1].lower()

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
            choice=choice,
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

    if len(args) < 2:
        await reply(
            message,
            "🔢 Формат: <code>/guess 100 50</code>",
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
            guess=number,
        )

        if result.success:
            await session.commit()

    await reply(message, result.message)


@router.message(Command("ttt"))
async def cmd_ttt(message: Message) -> None:
    if not message.from_user:
        return

    args = (message.text or "").split()

    bet = 0

    if len(args) >= 2:
        parsed = parse_integer(args[1])
        if parsed is not None:
            bet = parsed

    async with AsyncSessionLocal() as session:
        result = await start_tictactoe(
            session=session,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            bet=bet,
        )

        if result.success:
            await session.commit()

    await reply(
        message,
        result.message,
        reply_markup=result.keyboard,
    )


@router.callback_query(F.data.startswith("ttt:"))
async def callback_ttt(callback: CallbackQuery) -> None:
    if not callback.from_user or not callback.message:
        await callback.answer()
        return

    parts = callback.data.split(":")

    if len(parts) != 3:
        await callback.answer(
            "Некорректный ход.",
            show_alert=True,
        )
        return

    game_id = parse_integer(parts[1])
    position = parse_integer(parts[2])

    if game_id is None or position is None:
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
            position=position,
        )

        if result.success:
            await session.commit()

    await callback.answer(
        result.answer or "",
        show_alert=result.show_alert,
    )

    try:
        if result.keyboard is not None:
            await callback.message.edit_text(
                result.message,
                reply_markup=result.keyboard,
            )
        else:
            await callback.message.edit_text(
                result.message,
            )
    except TelegramBadRequest:
        pass


@router.callback_query(F.data.startswith("game:"))
async def callback_game(callback: CallbackQuery) -> None:
    if not callback.message or not callback.from_user:
        await callback.answer()
        return

    game = callback.data.split(":", 1)[1]

    await callback.answer()

    if game == "coinflip":
        await callback.message.answer(
            "🪙 Используй <code>/coinflip ставка</code>."
        )
        return

    if game == "dice":
        await callback.message.answer(
            "🎲 Используй <code>/dice ставка</code>."
        )
        return

    if game == "slots":
        await callback.message.answer(
            "🎰 Используй <code>/slots ставка</code>."
        )
        return

    if game == "roulette":
        await callback.message.answer(
            "🎡 Используй <code>/roulette ставка red</code>."
        )
        return

    if game == "guess":
        await callback.message.answer(
            "🔢 Используй <code>/guess ставка число</code>."
        )
        return

    if game == "football":
        await callback.message.answer(
            "⚽ Используй <code>/football ставка</code>."
        )
        return

    if game == "basketball":
        await callback.message.answer(
            "🏀 Используй <code>/basketball ставка</code>."
        )
        return

    if game == "tictactoe":
        await callback.message.answer(
            "⭕❌ Используй <code>/ttt</code>."
        )
        return

    await callback.message.answer(
        "❌ Неизвестная игра."
    )


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
        from services import play_telegram_dice_game

        result = await play_telegram_dice_game(
            session=session,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            game_type="football",
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
        from services import play_telegram_dice_game

        result = await play_telegram_dice_game(
            session=session,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            game_type="basketball",
            bet=bet,
        )

        if result.success:
            await session.commit()

    await reply(message, result.message)


@router.message(
    F.text.regexp(
        r"^(?:[/!])?(обнять|пожать|поцеловать|пнуть|ударить|"
        r"погладить|подмигнуть|дать\s+пять|поздравить|пожалеть|"
        r"рассмешить|напугать|ткнуть|укусить|дать\s+подзатыльник|"
        r"кинуть\s+тапок)(?:\s+.+)?$"
    )
)
async def rp_handler(message: Message) -> None:
    if not message.from_user or not is_group(message):
        return

    text = (message.text or "").strip()

    if text.startswith("/") or text.startswith("!"):
        text = text[1:]

    parts = text.split(maxsplit=1)

    if not parts:
        return

    if len(parts) == 1:
        action = parts[0].lower()
        target_text = ""
    else:
        first, rest = parts

        multiword = {
            "дать пять",
            "дать подзатыльник",
            "кинуть тапок",
        }

        if f"{first.lower()} {rest.lower().split()[0] if rest else ''}" in multiword:
            words = text.split(maxsplit=2)
            action = " ".join(words[:2]).lower()
            target_text = words[2] if len(words) > 2 else ""
        else:
            action = first.lower()
            target_text = rest

    target_user_id: Optional[int] = None
    target_name: Optional[str] = None

    if message.reply_to_message:
        target = message.reply_to_message.from_user

        if target:
            target_user_id = target.id
            target_name = (
                f"@{escape(target.username)}"
                if target.username
                else escape(target.full_name or "Игрок")
            )

    elif message.entities:
        for entity in message.entities:
            if entity.type == "text_mention" and entity.user:
                target_user_id = entity.user.id
                target_name = escape(
                    entity.user.full_name or "Игрок"
                )
                break

            if entity.type == "mention":
                offset = entity.offset
                length = entity.length
                mention = text[offset:offset + length]

                if mention.startswith("@"):
                    target_name = escape(mention)
                    break

    elif target_text.startswith("@"):
        target_name = escape(
            target_text.split()[0]
        )

    async with AsyncSessionLocal() as session:
        result = await perform_rp(
            session=session,
            chat_id=message.chat.id,
            actor_id=message.from_user.id,
            action=action,
            target_id=target_user_id,
            target_name=target_name,
        )

        if result.success:
            await session.commit()

    await reply(message, result.message)


@router.message(Command("setnick"))
async def cmd_setnick(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    nick = (command.args or "").strip()

    if not nick:
        await reply(
            message,
            "✏️ Пример: <code>/setnick Батя</code>",
        )
        return

    async with AsyncSessionLocal() as session:
        result = await set_profile_nick(
            session=session,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            nick=nick,
        )

        if result.success:
            await session.commit()

    await reply(message, result.message)


@router.message(Command("settag"))
async def cmd_settag(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    tag = (command.args or "").strip()

    async with AsyncSessionLocal() as session:
        result = await set_profile_tag(
            session=session,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            tag=tag,
        )

    await reply(message, result.message)


@router.message(Command("warn"))
async def cmd_warn(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user:
        return

    if not message.reply_to_message:
        await reply(
            message,
            "⚠️ Используй /warn ответом на сообщение.",
        )
        return

    target = message.reply_to_message.from_user

    if not target:
        return

    reason = (command.args or "").strip()

    async with AsyncSessionLocal() as session:
        result = await add_warning(
            session=session,
            chat_id=message.chat.id,
            target_user_id=target.id,
            moderator_id=message.from_user.id,
            reason=reason,
        )

        if result.success:
            await session.commit()

    await reply(message, result.message)


@router.message(Command("warnings"))
async def cmd_warnings(message: Message) -> None:
    if not message.from_user:
        return

    target_id = (
        message.reply_to_message.from_user.id
        if message.reply_to_message
        and message.reply_to_message.from_user
        else message.from_user.id
    )

    async with AsyncSessionLocal() as session:
        result = await get_warnings(
            session=session,
            chat_id=message.chat.id,
            user_id=target_id,
        )

    await reply(message, result)


@router.message(Command("unwarn"))
async def cmd_unwarn(message: Message) -> None:
    if not message.from_user:
        return

    if not message.reply_to_message:
        await reply(
            message,
            "Используй /unwarn ответом на сообщение.",
        )
        return

    target = message.reply_to_message.from_user

    if not target:
        return

    async with AsyncSessionLocal() as session:
        result = await remove_warning(
            session=session,
            chat_id=message.chat.id,
            user_id=target.id,
            moderator_id=message.from_user.id,
        )

        if result.success:
            await session.commit()

    await reply(message, result.message)


@router.message(Command("mute"))
async def cmd_mute(
    message: Message,
    command: CommandObject,
) -> None:
    if not message.from_user or not message.reply_to_message:
        await reply(
            message,
            "🔇 Используй /mute ответом на сообщение.",
        )
        return

    target = message.reply_to_message.from_user

    if not target:
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
            target_user_id=target.id,
            moderator_id=message.from_user.id,
            duration_minutes=duration,
        )

        if result.success:
            await session.commit()

    await reply(message, result.message)


@router.message(Command("unmute"))
async def cmd_unmute(message: Message) -> None:
    if not message.from_user or not message.reply_to_message:
        await reply(
            message,
            "Используй /unmute ответом на сообщение.",
        )
        return

    target = message.reply_to_message.from_user

    if not target:
        return

    async with AsyncSessionLocal() as session:
        result = await moderate_unmute(
            session=session,
            bot=message.bot,
            chat_id=message.chat.id,
            target_user_id=target.id,
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
    if not message.from_user or not message.reply_to_message:
        await reply(
            message,
            "Используй /ban ответом на сообщение.",
        )
        return

    target = message.reply_to_message.from_user

    if not target:
        return

    reason = (command.args or "").strip()

    async with AsyncSessionLocal() as session:
        result = await moderate_ban(
            session=session,
            bot=message.bot,
            chat_id=message.chat.id,
            target_user_id=target.id,
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
    if not message.from_user or not message.reply_to_message:
        await reply(
            message,
            "Используй /kick ответом на сообщение.",
        )
        return

    target = message.reply_to_message.from_user

    if not target:
        return

    reason = (command.args or "").strip()

    async with AsyncSessionLocal() as session:
        result = await moderate_kick(
            session=session,
            bot=message.bot,
            chat_id=message.chat.id,
            target_user_id=target.id,
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

    async with AsyncSessionLocal() as session:
        result = await purge_messages(
            bot=message.bot,
            chat_id=message.chat.id,
            moderator_id=message.from_user.id,
            count=amount,
        )

    await reply(message, result.message)


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


@router.message(
    F.text
)
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


@router.errors()
async def global_error_handler(event) -> None:
    logger.exception(
        "Необработанная ошибка Telegram handler: %s",
        event.exception,
    )


def register_handlers(dispatcher) -> None:
    dispatcher.include_router(router)
    logger.info("Основной router зарегистрирован.")