"""
Ezzzy Game Bot
==============
handlers.py — Telegram handlers.

Здесь находится взаимодействие с Telegram:
    - команды;
    - обычные сообщения;
    - профили;
    - статистика;
    - экономика;
    - игры;
    - RP;
    - модерация;
    - inline-кнопки.
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
    balance_user,
    claim_daily_bonus,
    create_game,
    format_balance,
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
)


logger = logging.getLogger("EzzzyGameBot.handlers")

router = Router(name="main")


# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================


def is_group(message: Message) -> bool:
    """Проверяет, является ли сообщение сообщением группы."""

    return message.chat.type in {
        ChatType.GROUP,
        ChatType.SUPERGROUP,
    }


def user_display_name(
    message: Message,
) -> str:
    """Безопасное отображаемое имя пользователя."""

    if not message.from_user:
        return "Игрок"

    if message.from_user.username:
        return f"@{escape(message.from_user.username)}"

    return escape(
        message.from_user.full_name or "Игрок"
    )


def target_display_name(
    message: Message,
) -> Optional[str]:
    """Получает имя пользователя из reply."""

    if not message.reply_to_message:
        return None

    user = message.reply_to_message.from_user

    if not user:
        return None

    if user.username:
        return f"@{escape(user.username)}"

    return escape(
        user.full_name or "Игрок"
    )


def parse_integer(
    value: Optional[str],
) -> Optional[int]:
    """Безопасный парсинг целого числа."""

    if not value:
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


async def get_or_prepare_member(
    message: Message,
):
    """
    Создаёт/обновляет пользователя, группу и профиль участника.
    """

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


async def reply(
    message: Message,
    text: str,
    **kwargs,
) -> Optional[Message]:
    """Безопасный ответ на сообщение."""

    try:
        return await message.answer(
            text,
            **kwargs,
        )
    except TelegramForbiddenError:
        logger.warning(
            "Telegram запретил отправку сообщения в chat_id=%s",
            message.chat.id,
        )
    except TelegramBadRequest:
        logger.exception(
            "Telegram отклонил сообщение."
        )

    return None


def games_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура списка игр."""

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
                    text="⭕❌ Крестики-нолики",
                    callback_data="game:ttt",
                ),
            ],
        ]
    )


def back_keyboard() -> InlineKeyboardMarkup:
    """Кнопка возврата к играм."""

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
# START / HELP
# ============================================================================


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    """Стартовая команда."""

    if message.from_user:
        await get_or_prepare_member(message)

    text = (
        "<b>🥜 Ezzzy Game Bot</b>\n\n"
        "Добро пожаловать!\n\n"
        "Я умею:\n"
        "🥜 выдавать арахис за активность\n"
        "⭐ прокачивать уровни\n"
        "🎰 запускать мини-игры\n"
        "🫂 выполнять RP-команды\n"
        "🏆 вести рейтинги\n"
        "👤 хранить профиль отдельно для каждой группы\n"
        "🔨 помогать администрации\n\n"
        "Нажми /help, чтобы посмотреть команды."
    )

    await reply(message, text)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Список возможностей."""

    text = (
        "<b>📚 Команды Ezzzy</b>\n\n"
        "<b>👤 Профиль</b>\n"
        "/profile — профиль\n"
        "/stats — статистика\n"
        "/balance — баланс\n"
        "/top — рейтинг\n\n"
        "<b>🎮 Игры</b>\n"
        "/games — мини-игры\n"
        "/bonus — ежедневный бонус\n"
        "/coinflip [ставка] — монетка\n"
        "/dice [ставка] — кубики\n"
        "/slots [ставка] — слоты\n"
        "/roulette [ставка] — рулетка\n"
        "/guess [ставка] [число] — угадай число\n"
        "/ttt — крестики-нолики\n\n"
        "<b>💰 Экономика</b>\n"
        "/pay [сумма] — перевод в reply\n\n"
        "<b>🎭 RP</b>\n"
        "обнять @user\n"
        "пожать @user\n"
        "поцеловать @user\n"
        "пнуть @user\n"
        "ударить @user\n"
        "погладить @user\n"
        "подмигнуть @user\n"
        "дать пять @user\n"
        "поздравить @user\n"
        "пожалеть @user\n"
        "рассмешить @user\n"
        "напугать @user\n"
        "ткнуть @user\n"
        "укусить @user\n"
        "дать подзатыльник @user\n"
        "кинуть тапок @user\n"
        "или ответь на сообщение и напиши:\n"
        "<code>обнять</code>\n\n"
        "<b>🛡 Модерация</b>\n"
        "/warn\n"
        "/warnings\n"
        "/mute\n"
        "/unmute\n"
        "/ban\n"
        "/unban\n"
        "/kick\n"
        "/setnick\n"
        "/settag\n"
        "/purge\n"
    )

    await reply(message, text)


# ============================================================================
# PROFILE
# ============================================================================


@router.message(Command("profile"))
async def cmd_profile(message: Message) -> None:
    """Профиль пользователя."""

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
    """Статистика пользователя."""

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
    """Баланс пользователя."""

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
        f"🥜 Твой баланс: <b>{balance:,}</b>".replace(",", " "),
    )


@router.message(Command("top"))
async def cmd_top(message: Message) -> None:
    """Таблица лидеров."""

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


# ============================================================================
# DAILY BONUS
# ============================================================================


@router.message(Command("bonus"))
async def cmd_bonus(message: Message) -> None:
    """Ежедневный бонус."""

    if not message.from_user:
        return

    await get_or_prepare_member(message)

    async with AsyncSessionLocal() as session:
        result = await claim_daily_bonus(
            session=session,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
        )

        await session.commit()

    await reply(
        message,
        result.message,
    )


# ============================================================================
# ECONOMY
# ============================================================================


@router.message(Command("pay"))
async def cmd_pay(
    message: Message,
    command: CommandObject,
) -> None:
    """Перевод арахиса другому пользователю."""

    if not message.from_user:
        return

    if not message.reply_to_message:
        await reply(
            message,
            "💸 Используй команду ответом на сообщение:\n"
            "<code>/pay 500</code>",
        )
        return

    amount = parse_integer(command.args)

    if amount is None or amount <= 0:
        await reply(
            message,
            "❌ Укажи положительную сумму.\n"
            "Пример: <code>/pay 500</code>",
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
            "😐 Самому себе переводить арахис нельзя.",
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

    await reply(
        message,
        result.message,
    )


# ============================================================================
# GAMES
# ============================================================================


@router.message(Command("games"))
async def cmd_games(message: Message) -> None:
    """Меню мини-игр."""

    await reply(
        message,
        (
            "<b>🎮 Мини-игры</b>\n\n"
            "Выбирай игру кнопкой ниже.\n"
            "Для большинства игр понадобится ставка."
        ),
        reply_markup=games_keyboard(),
    )


@router.message(Command("coinflip"))
async def cmd_coinflip(
    message: Message,
    command: CommandObject,
) -> None:
    """Монетка."""

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

    await reply(
        message,
        result.message,
    )


@router.message(Command("dice"))
async def cmd_dice(
    message: Message,
    command: CommandObject,
) -> None:
    """Кубики."""

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

    await reply(
        message,
        result.message,
    )


@router.message(Command("slots"))
async def cmd_slots(
    message: Message,
    command: CommandObject,
) -> None:
    """Слоты."""

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

    await reply(
        message,
        result.message,
    )


@router.message(Command("roulette"))
async def cmd_roulette(
    message: Message,
    command: CommandObject,
) -> None:
    """Рулетка."""

    if not message.from_user:
        return

    args = (command.args or "").split()

    if len(args) < 2:
        await reply(
            message,
            "🎡 Формат:\n"
            "<code>/roulette 100 red</code>\n\n"
            "Варианты: red, black, green",
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

    await reply(
        message,
        result.message,
    )


@router.message(Command("guess"))
async def cmd_guess(
    message: Message,
    command: CommandObject,
) -> None:
    """Угадай число."""

    if not message.from_user:
        return

    args = (command.args or "").split()

    if len(args) != 2:
        await reply(
            message,
            "🔢 Формат:\n"
            "<code>/guess 100 7</code>\n\n"
            "Число должно быть от 1 до 10.",
        )
        return

    bet = parse_integer(args[0])
    number = parse_integer(args[1])

    if bet is None or number is None:
        await reply(
            message,
            "❌ Некорректные данные.",
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

    await reply(
        message,
        result.message,
    )


# ============================================================================
# TIC TAC TOE
# ============================================================================


@router.message(Command("ttt"))
async def cmd_ttt(message: Message) -> None:
    """Создание игры крестики-нолики."""

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


# ============================================================================
# GAME CALLBACKS
# ============================================================================


@router.callback_query(F.data == "games:menu")
async def callback_games_menu(
    callback: CallbackQuery,
) -> None:
    """Возврат в меню игр."""

    await callback.answer()

    if callback.message:
        await callback.message.edit_text(
            "<b>🎮 Мини-игры</b>\n\nВыбирай игру:",
            reply_markup=games_keyboard(),
        )


@router.callback_query(F.data.startswith("game:"))
async def callback_game(
    callback: CallbackQuery,
) -> None:
    """Обработка выбора игры."""

    game_name = callback.data.split(":", 1)[1]

    descriptions = {
        "coinflip": (
            "🪙 <b>Монетка</b>\n\n"
            "Используй:\n"
            "<code>/coinflip 100</code>"
        ),
        "dice": (
            "🎲 <b>Кубики</b>\n\n"
            "Используй:\n"
            "<code>/dice 100</code>"
        ),
        "slots": (
            "🎰 <b>Слоты</b>\n\n"
            "Используй:\n"
            "<code>/slots 100</code>"
        ),
        "roulette": (
            "🎡 <b>Рулетка</b>\n\n"
            "Используй:\n"
            "<code>/roulette 100 red</code>"
        ),
        "guess": (
            "🔢 <b>Угадай число</b>\n\n"
            "Используй:\n"
            "<code>/guess 100 7</code>"
        ),
        "ttt": (
            "⭕❌ <b>Крестики-нолики</b>\n\n"
            "Используй /ttt."
        ),
    }

    text = descriptions.get(
        game_name,
        "❌ Неизвестная игра.",
    )

    await callback.answer()

    if callback.message:
        await callback.message.edit_text(
            text,
            reply_markup=back_keyboard(),
        )


@router.callback_query(F.data.startswith("ttt:"))
async def callback_ttt(
    callback: CallbackQuery,
) -> None:
    """Ходы крестиков-ноликов."""

    if not callback.from_user:
        return

    parts = callback.data.split(":")

    if len(parts) != 3:
        await callback.answer(
            "❌ Некорректный ход.",
            show_alert=True,
        )
        return

    try:
        game_id = int(parts[1])
        position = int(parts[2])
    except ValueError:
        await callback.answer(
            "❌ Некорректный ход.",
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

    if callback.message:
        try:
            await callback.message.edit_text(
                result.message,
                reply_markup=result.keyboard,
            )
        except TelegramBadRequest:
            pass


# ============================================================================
# RP
# ============================================================================


@router.message(
    F.text.regexp(
        r"^(?:[/!])?(обнять|пожать|поцеловать|пнуть|ударить|"
        r"погладить|подмигнуть|дать\s*пять|поздравить|пожалеть|"
        r"рассмешить|напугать|ткнуть|укусить|дать\s+подзатыльник|"
        r"кинуть\s+тапок)(?:\s+.+)?$"
    )
)
async def rp_handler(message: Message) -> None:
    """RP-команды."""

    if not message.from_user:
        return

    if not is_group(message):
        return

    text = (message.text or "").strip()

    if text.startswith("/") or text.startswith("!"):
        text = text[1:]

    parts = text.split(maxsplit=1)

    if not parts:
        return

    action = parts[0].lower().replace(" ", "_")

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
            if entity.type == "text_mention":
                if entity.user:
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

    if target_user_id == message.from_user.id:
        await reply(
            message,
            "😐 Себя обнимать немного странно.",
        )
        return

    async with AsyncSessionLocal() as session:
        result = await perform_rp(
            session=session,
            chat_id=message.chat.id,
            actor_id=message.from_user.id,
            action=action,
            target_id=target_user_id,
            target_name=target_name,
        )

    await reply(
        message,
        result.message,
    )


# ============================================================================
# PROFILE NICK / TAG
# ============================================================================


@router.message(Command("setnick"))
async def cmd_setnick(
    message: Message,
    command: CommandObject,
) -> None:
    """Изменение игрового ника."""

    if not message.from_user:
        return

    nick = (command.args or "").strip()

    if not nick:
        await reply(
            message,
            "✏️ Пример:\n"
            "<code>/setnick Батя</code>",
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

    await reply(
        message,
        result.message,
    )


@router.message(Command("settag"))
async def cmd_settag(
    message: Message,
    command: CommandObject,
) -> None:
    """Изменение Telegram/profile tag."""

    if not message.from_user:
        return

    tag = (command.args or "").strip()

    if not tag:
        await reply(
            message,
            "🏷 Пример:\n"
            "<code>/settag Батяра</code>",
        )
        return

    async with AsyncSessionLocal() as session:
        result = await set_profile_tag(
            session=session,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            tag=tag,
        )

        if result.success:
            await session.commit()

    await reply(
        message,
        result.message,
    )


# ============================================================================
# MODERATION
# ============================================================================


@router.message(Command("warn"))
async def cmd_warn(
    message: Message,
    command: CommandObject,
) -> None:
    """Выдать предупреждение."""

    if not message.reply_to_message:
        await reply(
            message,
            "⚠️ Используй /warn ответом на сообщение пользователя.",
        )
        return

    if not message.from_user:
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

    await reply(
        message,
        result.message,
    )


@router.message(Command("warnings"))
async def cmd_warnings(
    message: Message,
) -> None:
    """Показать предупреждения пользователя."""

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

    await reply(
        message,
        result,
    )


@router.message(Command("unwarn"))
async def cmd_unwarn(
    message: Message,
) -> None:
    """Снять последнее предупреждение."""

    if not message.reply_to_message:
        await reply(
            message,
            "Используй /unwarn ответом на сообщение.",
        )
        return

    if not message.from_user:
        return

    target = message.reply_to_message.from_user

    if not target:
        return

    async with AsyncSessionLocal() as session:
        from services import remove_warning

        result = await remove_warning(
            session=session,
            chat_id=message.chat.id,
            user_id=target.id,
            moderator_id=message.from_user.id,
        )

        if result.success:
            await session.commit()

    await reply(
        message,
        result.message,
    )


@router.message(Command("mute"))
async def cmd_mute(
    message: Message,
    command: CommandObject,
) -> None:
    """Мут пользователя."""

    if not message.reply_to_message:
        await reply(
            message,
            "🔇 Используй /mute ответом на сообщение.\n"
            "Можно указать минуты:\n"
            "<code>/mute 30</code>",
        )
        return

    if not message.from_user:
        return

    target = message.reply_to_message.from_user

    if not target:
        return

    args = (command.args or "").split()

    duration = 60

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

    await reply(
        message,
        result.message,
    )


@router.message(Command("unmute"))
async def cmd_unmute(
    message: Message,
) -> None:
    """Снять мут."""

    if not message.reply_to_message:
        await reply(
            message,
            "Используй /unmute ответом на сообщение.",
        )
        return

    if not message.from_user:
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

    await reply(
        message,
        result.message,
    )


@router.message(Command("ban"))
async def cmd_ban(
    message: Message,
    command: CommandObject,
) -> None:
    """Забанить пользователя."""

    if not message.reply_to_message:
        await reply(
            message,
            "Используй /ban ответом на сообщение.",
        )
        return

    if not message.from_user:
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

    await reply(
        message,
        result.message,
    )


@router.message(Command("unban"))
async def cmd_unban(
    message: Message,
    command: CommandObject,
) -> None:
    """Разбанить пользователя по Telegram ID."""

    if not message.from_user:
        return

    target_id = parse_integer(
        (command.args or "").strip()
    )

    if target_id is None:
        await reply(
            message,
            "Пример:\n"
            "<code>/unban 123456789</code>",
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

    await reply(
        message,
        result.message,
    )


@router.message(Command("kick"))
async def cmd_kick(
    message: Message,
    command: CommandObject,
) -> None:
    """Кик пользователя."""

    if not message.reply_to_message:
        await reply(
            message,
            "Используй /kick ответом на сообщение.",
        )
        return

    if not message.from_user:
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

    await reply(
        message,
        result.message,
    )


@router.message(Command("purge"))
async def cmd_purge(
    message: Message,
    command: CommandObject,
) -> None:
    """Удалить последние сообщения."""

    if not message.from_user:
        return

    amount = parse_integer(command.args)

    if amount is None:
        amount = 10

    if amount < 1 or amount > 100:
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

    await reply(
        message,
        result.message,
    )


# ============================================================================
# OWNER / ECONOMY ADMIN
# ============================================================================


@router.message(Command("give"))
async def cmd_give(
    message: Message,
    command: CommandObject,
) -> None:
    """Выдать арахис владельцем бота."""

    if not message.from_user:
        return

    args = (command.args or "").split()

    if len(args) != 2:
        await reply(
            message,
            "Пример:\n"
            "<code>/give 123456789 1000</code>",
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

    await reply(
        message,
        result.message,
    )


@router.message(Command("take"))
async def cmd_take(
    message: Message,
    command: CommandObject,
) -> None:
    """Забрать арахис."""

    if not message.from_user:
        return

    args = (command.args or "").split()

    if len(args) != 2:
        await reply(
            message,
            "Пример:\n"
            "<code>/take 123456789 1000</code>",
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

    await reply(
        message,
        result.message,
    )


@router.message(Command("setbalance"))
async def cmd_setbalance(
    message: Message,
    command: CommandObject,
) -> None:
    """Установить баланс."""

    if not message.from_user:
        return

    args = (command.args or "").split()

    if len(args) != 2:
        await reply(
            message,
            "Пример:\n"
            "<code>/setbalance 123456789 5000</code>",
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

    await reply(
        message,
        result.message,
    )


@router.message(Command("setlevel"))
async def cmd_setlevel(
    message: Message,
    command: CommandObject,
) -> None:
    """Установить уровень."""

    if not message.from_user:
        return

    args = (command.args or "").split()

    if len(args) != 2:
        await reply(
            message,
            "Пример:\n"
            "<code>/setlevel 123456789 10</code>",
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

    await reply(
        message,
        result.message,
    )


# ============================================================================
# ОБЫЧНЫЕ СООБЩЕНИЯ
# ============================================================================


@router.message()
async def ordinary_message(
    message: Message,
) -> None:
    """
    Главный обработчик обычных сообщений.

    Здесь:
        - регистрируется пользователь;
        - считается сообщение;
        - начисляется XP;
        - начисляется арахис;
        - проверяется повышение уровня.
    """

    if not message.from_user:
        return

    # Не учитываем сообщения от ботов.
    if message.from_user.is_bot:
        return

    # Личные сообщения тоже поддерживаем для регистрации,
    # но игровая статистика группы используется только в группах.
    if not is_group(message):
        return

    async with AsyncSessionLocal() as session:
        result = await handle_message(
            session=session,
            message=message,
        )

        if result.changed:
            await session.commit()

    # Сообщение об уровне отправляем только при повышении.
    if result.level_up_message:
        await reply(
            message,
            result.level_up_message,
        )


# ============================================================================
# ERROR HANDLER
# ============================================================================


@router.errors()
async def global_error_handler(
    event,
) -> None:
    """Глобальная защита от необработанных ошибок."""

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
    """
    Регистрирует основной Router в Dispatcher.
    """

    dispatcher.include_router(router)

    logger.info(
        "Основной router зарегистрирован."
    )