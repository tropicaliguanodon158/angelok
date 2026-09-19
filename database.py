"""
Ezzzy Game Bot
==============
database.py — модели и работа с базой данных.

Локально:
    SQLite

На VDS:
    PostgreSQL

SQLAlchemy 2.x + asyncio.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
    select,
    func,
)
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)

from core import get_config


# ============================================================================
# ВСПОМОГАТЕЛЬНОЕ
# ============================================================================


def utcnow() -> datetime:
    """Текущее время UTC без timezone-информации для БД."""

    return datetime.now(timezone.utc).replace(tzinfo=None)


# ============================================================================
# ТИПЫ
# ============================================================================

# Telegram ID могут быть большими числами, поэтому для них используем
# BigInteger.
#
# Для внутренних автоинкрементных ID SQLite требует именно INTEGER PRIMARY KEY.
# PostgreSQL при этом продолжит использовать BIGINT.
#
# Получаем:
#   SQLite     -> INTEGER
#   PostgreSQL -> BIGINT
AutoIncrementID = BigInteger().with_variant(
    Integer,
    "sqlite",
)


# ============================================================================
# BASE
# ============================================================================


class Base(AsyncAttrs, DeclarativeBase):
    pass


# ============================================================================
# CHAT
# ============================================================================


class Chat(Base):
    """
    Telegram-группа/чат, в котором работает бот.
    """

    __tablename__ = "chats"

    # Telegram chat_id задаётся Telegram, поэтому автоинкремент здесь НЕ нужен.
    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        default="Telegram Chat",
    )

    chat_type: Mapped[str] = mapped_column(
        String(32),
        default="supergroup",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        onupdate=utcnow,
    )

    settings: Mapped[Optional["ChatSettings"]] = relationship(
        back_populates="chat",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    members: Mapped[list["ChatMember"]] = relationship(
        back_populates="chat",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


# ============================================================================
# CHAT SETTINGS
# ============================================================================


class ChatSettings(Base):
    """
    Настройки конкретной группы.
    """

    __tablename__ = "chat_settings"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    chat_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("chats.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    economy_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    games_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    rp_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    leveling_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    moderation_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    message_reward_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
    )

    chat: Mapped["Chat"] = relationship(
        back_populates="settings",
        lazy="selectin",
    )


# ============================================================================
# USER
# ============================================================================


class User(Base):
    """
    Глобальный Telegram-пользователь.

    Один Telegram ID = одна запись.
    """

    __tablename__ = "users"

    # Telegram user_id задаётся Telegram.
    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
    )

    username: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    first_name: Mapped[str] = mapped_column(
        String(255),
        default="Игрок",
    )

    last_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    is_bot: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        onupdate=utcnow,
    )

    members: Mapped[list["ChatMember"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


# ============================================================================
# CHAT MEMBER
# ============================================================================


class ChatMember(Base):
    """
    Профиль пользователя внутри конкретной группы.

    Именно здесь хранятся:
        - локальный ник;
        - XP;
        - уровень;
        - арахис;
        - сообщения;
        - тег;
        - игровая статистика.
    """

    __tablename__ = "chat_members"

    __table_args__ = (
        UniqueConstraint(
            "chat_id",
            "user_id",
            name="uq_chat_member",
        ),
        Index(
            "ix_chat_members_chat_messages",
            "chat_id",
            "messages",
        ),
        Index(
            "ix_chat_members_chat_balance",
            "chat_id",
            "balance",
        ),
        Index(
            "ix_chat_members_chat_xp",
            "chat_id",
            "xp",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    chat_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("chats.id", ondelete="CASCADE"),
        nullable=False,
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    profile_nick: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )

    profile_tag: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )

    xp: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
    )

    level: Mapped[int] = mapped_column(
        Integer,
        default=1,
    )

    balance: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
    )

    messages: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
    )

    games_played: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
    )

    games_won: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
    )

    games_lost: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
    )

    total_won: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
    )

    total_lost: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
    )

    last_message_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    last_bonus_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        onupdate=utcnow,
    )

    chat: Mapped["Chat"] = relationship(
        back_populates="members",
        lazy="selectin",
    )

    user: Mapped["User"] = relationship(
        back_populates="members",
        lazy="selectin",
    )


# ============================================================================
# ECONOMY TRANSACTION
# ============================================================================


class EconomyTransaction(Base):
    """
    Полная история изменения баланса.

    amount:
        положительное число — начисление;
        отрицательное — списание.

    balance_after:
        баланс пользователя после операции.
    """

    __tablename__ = "economy_transactions"

    id: Mapped[int] = mapped_column(
        AutoIncrementID,
        primary_key=True,
        autoincrement=True,
    )

    chat_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
    )

    amount: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    balance_after: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    transaction_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    description: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        index=True,
    )


# ============================================================================
# GAME
# ============================================================================


class Game(Base):
    """
    История всех игровых ставок.
    """

    __tablename__ = "games"

    id: Mapped[int] = mapped_column(
        AutoIncrementID,
        primary_key=True,
        autoincrement=True,
    )

    chat_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
    )

    game_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    bet: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    result: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    multiplier: Mapped[float] = mapped_column(
        Float,
        default=0.0,
    )

    payout: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
    )

    won: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        index=True,
    )


# ============================================================================
# TICTACTOE
# ============================================================================


class TicTacToeGame(Base):
    """
    PvP-состояние игры крестики-нолики.
    """

    __tablename__ = "tictactoe_games"

    id: Mapped[int] = mapped_column(
        AutoIncrementID,
        primary_key=True,
        autoincrement=True,
    )

    chat_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
    )

    player_x_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    player_o_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
    )

    board: Mapped[str] = mapped_column(
        String(9),
        default="---------",
    )

    current_player_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        default="waiting",
    )

    winner_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        onupdate=utcnow,
    )


# ============================================================================
# WARN
# ============================================================================


class Warning(Base):
    """
    Предупреждение пользователя.
    """

    __tablename__ = "warnings"

    id: Mapped[int] = mapped_column(
        AutoIncrementID,
        primary_key=True,
        autoincrement=True,
    )

    chat_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
    )

    moderator_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
    )


# ============================================================================
# MODERATION ACTION
# ============================================================================


class ModerationAction(Base):
    """
    Журнал действий модераторов.
    """

    __tablename__ = "moderation_actions"

    id: Mapped[int] = mapped_column(
        AutoIncrementID,
        primary_key=True,
        autoincrement=True,
    )

    chat_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
    )

    target_user_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
    )

    moderator_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    action: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    duration: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
    )


# ============================================================================
# ACHIEVEMENT
# ============================================================================


class Achievement(Base):
    """
    Справочник достижений.
    """

    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    code: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    reward: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
    )


# ============================================================================
# USER ACHIEVEMENT
# ============================================================================


class UserAchievement(Base):
    """
    Полученные пользователями достижения.
    """

    __tablename__ = "user_achievements"

    id: Mapped[int] = mapped_column(
        AutoIncrementID,
        primary_key=True,
        autoincrement=True,
    )

    chat_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
    )

    achievement_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "achievements.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    earned_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
    )

    __table_args__ = (
        UniqueConstraint(
            "chat_id",
            "user_id",
            "achievement_id",
            name="uq_user_achievement",
        ),
    )


# ============================================================================
# DATABASE ENGINE
# ============================================================================


_config = get_config()

engine = create_async_engine(
    _config.database_url,
    echo=False,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ============================================================================
# DATABASE INITIALIZATION
# ============================================================================


async def initialize_database() -> None:
    """
    Создаёт все таблицы, если их ещё нет.
    """

    async with engine.begin() as connection:
        await connection.run_sync(
            Base.metadata.create_all,
        )


async def close_database() -> None:
    """
    Закрывает соединение с БД.
    """

    await engine.dispose()


# ============================================================================
# SESSION
# ============================================================================


def get_session() -> AsyncSession:
    """
    Создаёт новую асинхронную сессию БД.

    Использование:

        async with get_session() as session:
            ...
    """

    return AsyncSessionLocal()


# ============================================================================
# USER FUNCTIONS
# ============================================================================


async def get_or_create_user(
    session: AsyncSession,
    user_id: int,
    username: Optional[str],
    first_name: str,
    last_name: Optional[str],
    is_bot: bool = False,
) -> User:
    """
    Получает существующего пользователя либо создаёт нового.
    """

    user = await session.get(
        User,
        user_id,
    )

    if user is None:
        user = User(
            id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            is_bot=is_bot,
        )

        session.add(user)
        await session.flush()

    else:
        user.username = username
        user.first_name = first_name
        user.last_name = last_name
        user.is_bot = is_bot
        user.updated_at = utcnow()

    return user


# ============================================================================
# CHAT FUNCTIONS
# ============================================================================


async def get_or_create_chat(
    session: AsyncSession,
    chat_id: int,
    title: str,
    chat_type: str,
) -> Chat:
    """
    Получает существующий чат либо создаёт новый.

    Важно:
    здесь не используется chat.settings через lazy-load.
    Настройки проверяются отдельным SQL-запросом, поэтому функция
    безопасна для async SQLAlchemy.
    """

    chat = await session.get(
        Chat,
        chat_id,
    )

    if chat is None:
        chat = Chat(
            id=chat_id,
            title=title,
            chat_type=chat_type,
        )

        session.add(chat)

        await session.flush()

        settings = ChatSettings(
            chat_id=chat_id,
        )

        session.add(settings)

        await session.flush()

    else:
        chat.title = title
        chat.chat_type = chat_type
        chat.updated_at = utcnow()

        settings_result = await session.execute(
            select(ChatSettings).where(
                ChatSettings.chat_id == chat_id,
            )
        )

        settings = settings_result.scalar_one_or_none()

        if settings is None:
            settings = ChatSettings(
                chat_id=chat_id,
            )

            session.add(settings)

            await session.flush()

    return chat


# ============================================================================
# CHAT MEMBER FUNCTIONS
# ============================================================================


async def get_or_create_member(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
) -> ChatMember:
    """
    Получает профиль пользователя в конкретном чате.
    """

    result = await session.execute(
        select(ChatMember).where(
            ChatMember.chat_id == chat_id,
            ChatMember.user_id == user_id,
        )
    )

    member = result.scalar_one_or_none()

    if member is None:
        member = ChatMember(
            chat_id=chat_id,
            user_id=user_id,
        )

        session.add(member)

        await session.flush()

    return member


# ============================================================================
# LEADERBOARDS
# ============================================================================


async def get_top_by_balance(
    session: AsyncSession,
    chat_id: int,
    limit: int = 10,
) -> list[ChatMember]:
    """Топ пользователей по арахису."""

    result = await session.execute(
        select(ChatMember)
        .where(ChatMember.chat_id == chat_id)
        .order_by(ChatMember.balance.desc())
        .limit(limit)
    )

    return list(result.scalars().all())


async def get_top_by_xp(
    session: AsyncSession,
    chat_id: int,
    limit: int = 10,
) -> list[ChatMember]:
    """Топ пользователей по XP."""

    result = await session.execute(
        select(ChatMember)
        .where(ChatMember.chat_id == chat_id)
        .order_by(
            ChatMember.xp.desc(),
            ChatMember.level.desc(),
        )
        .limit(limit)
    )

    return list(result.scalars().all())


async def get_top_by_messages(
    session: AsyncSession,
    chat_id: int,
    limit: int = 10,
) -> list[ChatMember]:
    """Топ пользователей по сообщениям."""

    result = await session.execute(
        select(ChatMember)
        .where(ChatMember.chat_id == chat_id)
        .order_by(ChatMember.messages.desc())
        .limit(limit)
    )

    return list(result.scalars().all())


# ============================================================================
# STATISTICS
# ============================================================================


async def get_member_rank_by_xp(
    session: AsyncSession,
    member: ChatMember,
) -> int:
    """Возвращает место пользователя в XP-рейтинге."""

    count_result = await session.execute(
        select(func.count(ChatMember.id))
        .where(
            ChatMember.chat_id == member.chat_id,
            ChatMember.xp > member.xp,
        )
    )

    higher_count = count_result.scalar_one() or 0

    return int(higher_count) + 1


async def get_member_rank_by_balance(
    session: AsyncSession,
    member: ChatMember,
) -> int:
    """Возвращает место пользователя по балансу."""

    count_result = await session.execute(
        select(func.count(ChatMember.id))
        .where(
            ChatMember.chat_id == member.chat_id,
            ChatMember.balance > member.balance,
        )
    )

    higher_count = count_result.scalar_one() or 0

    return int(higher_count) + 1


# ============================================================================
# TRANSACTION
# ============================================================================


async def add_transaction(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    amount: int,
    balance_after: int,
    transaction_type: str,
    description: Optional[str] = None,
) -> EconomyTransaction:
    """
    Записывает экономическую операцию.
    """

    transaction = EconomyTransaction(
        chat_id=chat_id,
        user_id=user_id,
        amount=amount,
        balance_after=balance_after,
        transaction_type=transaction_type,
        description=description,
    )

    session.add(transaction)

    await session.flush()

    return transaction


# ============================================================================
# CLEANUP
# ============================================================================


async def delete_chat_data(
    session: AsyncSession,
    chat_id: int,
) -> None:
    """
    Полностью удаляет профильную информацию конкретного чата.

    Используется только административными функциями.
    """

    members_result = await session.execute(
        select(ChatMember).where(
            ChatMember.chat_id == chat_id,
        )
    )

    members = list(members_result.scalars().all())

    for member in members:
        await session.delete(member)

    await session.flush()