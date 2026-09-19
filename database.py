"""
Ezzzy Game Bot
==============

database.py — модели и работа с базой данных.

Локально:
    SQLite

На VDS:
    PostgreSQL

SQLAlchemy 2.x + asyncio.

ВАЖНО:
    Файл содержит не только модели, но и минимальный механизм
    совместимой миграции существующей базы.

    create_all() сам по себе НЕ добавляет новые колонки в уже
    существующие таблицы, поэтому после создания таблиц выполняется
    проверка и добавление недостающих колонок.
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
    text,
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
    """
    Текущее время UTC без timezone-информации для БД.

    В проекте все timestamps храним в UTC.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ============================================================================
# ТИПЫ
# ============================================================================

# Для внутренних ID:
#
# SQLite:
#     INTEGER PRIMARY KEY
#
# PostgreSQL:
#     BIGINT
#
# Это позволяет использовать один код для обеих БД.
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

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
    )

    username: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
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

    Здесь находится всё состояние, которое относится к пользователю
    в конкретном чате:

        - XP;
        - уровень;
        - баланс;
        - статистика;
        - Battle Pass;
        - размер;
        - болезнь;
        - ребёнок;
        - cooldown;
        - выбранный tag.
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
        Index(
            "ix_chat_members_chat_size",
            "chat_id",
            "penis_size",
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

    # ------------------------------------------------------------------------
    # ПРОФИЛЬ
    # ------------------------------------------------------------------------

    profile_nick: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )

    # Старое поле оставляем для обратной совместимости.
    #
    # Новая система tag будет использовать UserTag + selected_tag_id.
    profile_tag: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )

    selected_tag_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
    )

    # ------------------------------------------------------------------------
    # XP / LEVEL
    # ------------------------------------------------------------------------

    xp: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )

    level: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    # ------------------------------------------------------------------------
    # BATTLE PASS
    # ------------------------------------------------------------------------

    battle_pass_xp: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )

    battle_pass_level: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    battle_pass_season: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    # ------------------------------------------------------------------------
    # ECONOMY
    # ------------------------------------------------------------------------

    balance: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )

    # ------------------------------------------------------------------------
    # STATISTICS
    # ------------------------------------------------------------------------

    messages: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )

    games_played: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )

    games_won: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )

    games_lost: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )

    total_won: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )

    total_lost: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )

    # ------------------------------------------------------------------------
    # MEMBER SIZE
    # ------------------------------------------------------------------------

    penis_size: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    # ------------------------------------------------------------------------
    # DISEASE
    # ------------------------------------------------------------------------

    has_disease: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    disease_since: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    next_disease_tick: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    # ------------------------------------------------------------------------
    # CHILD
    # ------------------------------------------------------------------------

    has_child: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    child_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    last_child_support: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    # ------------------------------------------------------------------------
    # COOLDOWNS
    # ------------------------------------------------------------------------

    last_adult_rp_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    last_masturbation_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    last_rob_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    # Для ежедневного бонуса Rubber Pussy.
    last_rubber_daily_bonus_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    # ------------------------------------------------------------------------
    # MESSAGE / DAILY BONUS
    # ------------------------------------------------------------------------

    last_message_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    last_bonus_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    # ------------------------------------------------------------------------
    # TIMESTAMPS
    # ------------------------------------------------------------------------

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

    Для одиночных игр достаточно user_id.

    Для PvP-игр:
        player2_id;
        status;
        metadata.
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

    player2_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
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

    status: Mapped[str] = mapped_column(
        String(32),
        default="finished",
        nullable=False,
    )

    metadata_json: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        index=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        onupdate=utcnow,
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

    # Ставка TTT.
    bet: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
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
# STAFF
# ============================================================================


class StaffMember(Base):
    """
    Внутренняя роль пользователя в конкретном чате.

    OWNER:
        определяется через Config.OWNER_ID.

    HEAD_ADMIN:
        назначается owner.

    ADMIN:
        назначается head admin.

    MODERATOR:
        назначается head admin.
    """

    __tablename__ = "staff_members"

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

    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    appointed_by: Mapped[Optional[int]] = mapped_column(
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

    __table_args__ = (
        UniqueConstraint(
            "chat_id",
            "user_id",
            name="uq_staff_member",
        ),
        Index(
            "ix_staff_members_chat_role",
            "chat_id",
            "role",
        ),
    )


# ============================================================================
# MODERATION PERMISSION
# ============================================================================


class ModPermission(Base):
    """
    Настройка доступа к конкретной moderation-команде.

    scope:

        STAFF
            moderator + admin + head admin

        ADMIN
            admin + head admin

        HEAD_ADMIN
            только head admin
    """

    __tablename__ = "mod_permissions"

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

    command: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    scope: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="STAFF",
    )

    updated_by: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        onupdate=utcnow,
    )

    __table_args__ = (
        UniqueConstraint(
            "chat_id",
            "command",
            name="uq_mod_permission",
        ),
    )


# ============================================================================
# INVENTORY ITEM
# ============================================================================


class InventoryItem(Base):
    """
    Справочник предметов.

    Примеры code:

        case
        lubricant
        dildo
        rubber_pussy
        silicone_implant
        condom
    """

    __tablename__ = "inventory_items"

    id: Mapped[int] = mapped_column(
        AutoIncrementID,
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

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    item_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    stackable: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    max_quantity: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
    )


# ============================================================================
# USER ITEM
# ============================================================================


class UserItem(Base):
    """
    Инвентарь пользователя.

    quantity:
        количество предметов.

    uses_left:
        оставшиеся использования для предметов вроде Dildo.
    """

    __tablename__ = "user_items"

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

    item_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "inventory_items.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    uses_left: Mapped[Optional[int]] = mapped_column(
        Integer,
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

    item: Mapped["InventoryItem"] = relationship(
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint(
            "chat_id",
            "user_id",
            "item_id",
            name="uq_user_item",
        ),
    )


# ============================================================================
# TAG
# ============================================================================


class Tag(Base):
    """
    Справочник доступных тегов.
    """

    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(
        AutoIncrementID,
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

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
    )


# ============================================================================
# USER TAG
# ============================================================================


class UserTag(Base):
    """
    Теги, реально принадлежащие пользователю.

    Один tag можно получить только один раз.

    После получения пользователь может выбрать его через /tag.
    """

    __tablename__ = "user_tags"

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

    tag_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "tags.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    earned_from: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )

    earned_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
    )

    tag: Mapped["Tag"] = relationship(
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint(
            "chat_id",
            "user_id",
            "tag_id",
            name="uq_user_tag",
        ),
    )


# ============================================================================
# BATTLE PASS REWARD CLAIM
# ============================================================================


class BattlePassRewardClaim(Base):
    """
    История полученных Battle Pass наград.

    Нужна для idempotency:
    одна награда конкретного уровня не может быть выдана повторно.
    """

    __tablename__ = "battle_pass_reward_claims"

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

    season: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    reward_code: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    claimed_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
    )

    __table_args__ = (
        UniqueConstraint(
            "chat_id",
            "user_id",
            "season",
            "level",
            name="uq_battle_pass_reward_claim",
        ),
    )


# ============================================================================
# GIVEAWAY
# ============================================================================


class Giveaway(Base):
    """
    Розыгрыш.

    prize_type:

        peanuts
        item
        external
    """

    __tablename__ = "giveaways"

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

    creator_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    message_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
    )

    prize_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    prize_amount: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
    )

    prize_item_code: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )

    prize_description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    ends_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        default="active",
        nullable=False,
        index=True,
    )

    winner_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
    )

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )


# ============================================================================
# GIVEAWAY PARTICIPANT
# ============================================================================


class GiveawayParticipant(Base):
    """
    Участник розыгрыша.

    Один пользователь может участвовать в конкретном giveaway
    только один раз.
    """

    __tablename__ = "giveaway_participants"

    id: Mapped[int] = mapped_column(
        AutoIncrementID,
        primary_key=True,
        autoincrement=True,
    )

    giveaway_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "giveaways.id",
            ondelete="CASCADE",
        ),
        nullable=False,
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

    joined_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
    )

    __table_args__ = (
        UniqueConstraint(
            "giveaway_id",
            "user_id",
            name="uq_giveaway_participant",
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
# MIGRATION
# ============================================================================


# Новые колонки, которые добавляются в существующую chat_members таблицу.
#
# Важно:
# SQLite и PostgreSQL поддерживают ALTER TABLE ... ADD COLUMN.
#
# Значения DEFAULT нужны для уже существующих пользователей.
CHAT_MEMBER_MIGRATION_COLUMNS: dict[str, str] = {
    "selected_tag_id": "BIGINT",
    "battle_pass_xp": "BIGINT NOT NULL DEFAULT 0",
    "battle_pass_level": "INTEGER NOT NULL DEFAULT 1",
    "battle_pass_season": "INTEGER NOT NULL DEFAULT 1",
    "penis_size": "DOUBLE PRECISION NOT NULL DEFAULT 0",
    "has_disease": "BOOLEAN NOT NULL DEFAULT FALSE",
    "disease_since": "TIMESTAMP NULL",
    "next_disease_tick": "TIMESTAMP NULL",
    "has_child": "BOOLEAN NOT NULL DEFAULT FALSE",
    "child_until": "TIMESTAMP NULL",
    "last_child_support": "TIMESTAMP NULL",
    "last_adult_rp_at": "TIMESTAMP NULL",
    "last_masturbation_at": "TIMESTAMP NULL",
    "last_rob_at": "TIMESTAMP NULL",
    "last_rubber_daily_bonus_at": "TIMESTAMP NULL",
}


GAME_MIGRATION_COLUMNS: dict[str, str] = {
    "player2_id": "BIGINT NULL",
    "status": "VARCHAR(32) NOT NULL DEFAULT 'finished'",
    "metadata_json": "TEXT NULL",
    "updated_at": "TIMESTAMP NULL",
}


TICTACTOE_MIGRATION_COLUMNS: dict[str, str] = {
    "bet": "BIGINT NOT NULL DEFAULT 0",
}


async def _add_missing_columns(
    connection,
    table_name: str,
    columns: dict[str, str],
) -> None:
    """
    Добавляет отсутствующие колонки в существующую таблицу.

    Функция вызывается внутри run_sync(), поэтому здесь используется
    обычный SQLAlchemy Connection.
    """

    from sqlalchemy import inspect

    inspector = inspect(connection)

    existing_columns = {
        column["name"]
        for column in inspector.get_columns(table_name)
    }

    for column_name, column_definition in columns.items():
        if column_name in existing_columns:
            continue

        statement = text(
            f"ALTER TABLE {table_name} "
            f"ADD COLUMN {column_name} {column_definition}"
        )

        connection.execute(statement)


def _run_schema_migrations(connection) -> None:
    """
    Синхронная часть совместимой миграции.

    Выполняется внутри AsyncConnection.run_sync().
    """

    from sqlalchemy import inspect

    inspector = inspect(connection)
    table_names = set(inspector.get_table_names())

    if "chat_members" in table_names:
        _add_missing_columns_sync(
            connection,
            "chat_members",
            CHAT_MEMBER_MIGRATION_COLUMNS,
        )

    if "games" in table_names:
        _add_missing_columns_sync(
            connection,
            "games",
            GAME_MIGRATION_COLUMNS,
        )

    if "tictactoe_games" in table_names:
        _add_missing_columns_sync(
            connection,
            "tictactoe_games",
            TICTACTOE_MIGRATION_COLUMNS,
        )


def _add_missing_columns_sync(
    connection,
    table_name: str,
    columns: dict[str, str],
) -> None:
    """
    Синхронная версия добавления отсутствующих колонок.

    Отдельная функция нужна потому, что миграция выполняется
    внутри SQLAlchemy run_sync().
    """

    from sqlalchemy import inspect

    inspector = inspect(connection)

    existing_columns = {
        column["name"]
        for column in inspector.get_columns(table_name)
    }

    for column_name, column_definition in columns.items():
        if column_name in existing_columns:
            continue

        statement = text(
            f"ALTER TABLE {table_name} "
            f"ADD COLUMN {column_name} {column_definition}"
        )

        connection.execute(statement)


# ============================================================================
# DATABASE INITIALIZATION
# ============================================================================


async def initialize_database() -> None:
    """
    Создаёт отсутствующие таблицы и выполняет совместимую миграцию.

    Порядок:

        1. create_all()
        2. добавить отсутствующие колонки существующих таблиц

    Благодаря этому старую БД не требуется удалять.
    """

    async with engine.begin() as connection:
        await connection.run_sync(
            Base.metadata.create_all,
        )

        await connection.run_sync(
            _run_schema_migrations,
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

    Настройки проверяются отдельным SQL-запросом, чтобы не зависеть
    от async lazy-loading.
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
# STAFF FUNCTIONS
# ============================================================================


async def get_staff_member(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
) -> Optional[StaffMember]:
    """
    Возвращает внутреннюю staff-роль пользователя.
    """

    result = await session.execute(
        select(StaffMember).where(
            StaffMember.chat_id == chat_id,
            StaffMember.user_id == user_id,
        )
    )

    return result.scalar_one_or_none()


async def get_staff_role(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
) -> Optional[str]:
    """
    Возвращает роль пользователя или None.
    """

    staff = await get_staff_member(
        session,
        chat_id,
        user_id,
    )

    if staff is None:
        return None

    return staff.role


# ============================================================================
# MODERATION PERMISSIONS
# ============================================================================


async def get_mod_permission(
    session: AsyncSession,
    chat_id: int,
    command: str,
) -> Optional[ModPermission]:
    """
    Получает настройку доступа к moderation-команде.
    """

    result = await session.execute(
        select(ModPermission).where(
            ModPermission.chat_id == chat_id,
            ModPermission.command == command,
        )
    )

    return result.scalar_one_or_none()


# ============================================================================
# INVENTORY
# ============================================================================


async def get_inventory_item(
    session: AsyncSession,
    code: str,
) -> Optional[InventoryItem]:
    """
    Получает предмет по уникальному коду.
    """

    result = await session.execute(
        select(InventoryItem).where(
            InventoryItem.code == code,
        )
    )

    return result.scalar_one_or_none()


async def get_user_item(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    item_code: str,
) -> Optional[UserItem]:
    """
    Получает предмет пользователя по code.
    """

    result = await session.execute(
        select(UserItem)
        .join(
            InventoryItem,
            InventoryItem.id == UserItem.item_id,
        )
        .where(
            UserItem.chat_id == chat_id,
            UserItem.user_id == user_id,
            InventoryItem.code == item_code,
        )
    )

    return result.scalar_one_or_none()


async def get_user_items(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
) -> list[UserItem]:
    """
    Возвращает весь инвентарь пользователя.
    """

    result = await session.execute(
        select(UserItem)
        .where(
            UserItem.chat_id == chat_id,
            UserItem.user_id == user_id,
        )
        .order_by(UserItem.id.asc())
    )

    return list(result.scalars().all())


# ============================================================================
# TAGS
# ============================================================================


async def get_tag_by_code(
    session: AsyncSession,
    code: str,
) -> Optional[Tag]:
    """
    Получает tag по code.
    """

    result = await session.execute(
        select(Tag).where(
            Tag.code == code,
        )
    )

    return result.scalar_one_or_none()


async def get_user_tags(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
) -> list[UserTag]:
    """
    Возвращает все теги пользователя.
    """

    result = await session.execute(
        select(UserTag)
        .where(
            UserTag.chat_id == chat_id,
            UserTag.user_id == user_id,
        )
        .order_by(UserTag.earned_at.asc())
    )

    return list(result.scalars().all())


# ============================================================================
# GIVEAWAYS
# ============================================================================


async def get_giveaway(
    session: AsyncSession,
    giveaway_id: int,
) -> Optional[Giveaway]:
    """
    Получает giveaway по ID.
    """

    return await session.get(
        Giveaway,
        giveaway_id,
    )


async def get_giveaway_participants(
    session: AsyncSession,
    giveaway_id: int,
) -> list[GiveawayParticipant]:
    """
    Возвращает участников giveaway.
    """

    result = await session.execute(
        select(GiveawayParticipant).where(
            GiveawayParticipant.giveaway_id == giveaway_id,
        )
    )

    return list(result.scalars().all())


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
        .where(
            ChatMember.chat_id == chat_id,
        )
        .order_by(
            ChatMember.balance.desc(),
            ChatMember.user_id.asc(),
        )
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
        .where(
            ChatMember.chat_id == chat_id,
        )
        .order_by(
            ChatMember.xp.desc(),
            ChatMember.level.desc(),
            ChatMember.user_id.asc(),
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
        .where(
            ChatMember.chat_id == chat_id,
        )
        .order_by(
            ChatMember.messages.desc(),
            ChatMember.user_id.asc(),
        )
        .limit(limit)
    )

    return list(result.scalars().all())


async def get_top_by_penis_size(
    session: AsyncSession,
    chat_id: int,
    limit: int = 10,
) -> list[ChatMember]:
    """
    Топ пользователей по размеру.

    Используется будущей командой /topsize.
    """

    result = await session.execute(
        select(ChatMember)
        .where(
            ChatMember.chat_id == chat_id,
        )
        .order_by(
            ChatMember.penis_size.desc(),
            ChatMember.user_id.asc(),
        )
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


async def get_member_rank_by_penis_size(
    session: AsyncSession,
    member: ChatMember,
) -> int:
    """Возвращает место пользователя по размеру."""

    count_result = await session.execute(
        select(func.count(ChatMember.id))
        .where(
            ChatMember.chat_id == member.chat_id,
            ChatMember.penis_size > member.penis_size,
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

    Удаление выполняется для основных связанных сущностей до удаления
    самих ChatMember.
    """

    # ------------------------------------------------------------------------
    # GIVEAWAYS
    # ------------------------------------------------------------------------

    giveaway_result = await session.execute(
        select(Giveaway).where(
            Giveaway.chat_id == chat_id,
        )
    )

    giveaways = list(
        giveaway_result.scalars().all()
    )

    for giveaway in giveaways:
        participants_result = await session.execute(
            select(GiveawayParticipant).where(
                GiveawayParticipant.giveaway_id == giveaway.id,
            )
        )

        for participant in participants_result.scalars().all():
            await session.delete(participant)

        await session.delete(giveaway)

    # ------------------------------------------------------------------------
    # USER TAGS
    # ------------------------------------------------------------------------

    user_tags_result = await session.execute(
        select(UserTag).where(
            UserTag.chat_id == chat_id,
        )
    )

    for user_tag in user_tags_result.scalars().all():
        await session.delete(user_tag)

    # ------------------------------------------------------------------------
    # USER ITEMS
    # ------------------------------------------------------------------------

    user_items_result = await session.execute(
        select(UserItem).where(
            UserItem.chat_id == chat_id,
        )
    )

    for user_item in user_items_result.scalars().all():
        await session.delete(user_item)

    # ------------------------------------------------------------------------
    # BATTLE PASS CLAIMS
    # ------------------------------------------------------------------------

    bp_claims_result = await session.execute(
        select(BattlePassRewardClaim).where(
            BattlePassRewardClaim.chat_id == chat_id,
        )
    )

    for claim in bp_claims_result.scalars().all():
        await session.delete(claim)

    # ------------------------------------------------------------------------
    # STAFF
    # ------------------------------------------------------------------------

    staff_result = await session.execute(
        select(StaffMember).where(
            StaffMember.chat_id == chat_id,
        )
    )

    for staff in staff_result.scalars().all():
        await session.delete(staff)

    # ------------------------------------------------------------------------
    # MOD PERMISSIONS
    # ------------------------------------------------------------------------

    permissions_result = await session.execute(
        select(ModPermission).where(
            ModPermission.chat_id == chat_id,
        )
    )

    for permission in permissions_result.scalars().all():
        await session.delete(permission)

    # ------------------------------------------------------------------------
    # TRANSACTIONS
    # ------------------------------------------------------------------------

    transactions_result = await session.execute(
        select(EconomyTransaction).where(
            EconomyTransaction.chat_id == chat_id,
        )
    )

    for transaction in transactions_result.scalars().all():
        await session.delete(transaction)

    # ------------------------------------------------------------------------
    # GAMES
    # ------------------------------------------------------------------------

    games_result = await session.execute(
        select(Game).where(
            Game.chat_id == chat_id,
        )
    )

    for game in games_result.scalars().all():
        await session.delete(game)

    # ------------------------------------------------------------------------
    # TTT
    # ------------------------------------------------------------------------

    ttt_result = await session.execute(
        select(TicTacToeGame).where(
            TicTacToeGame.chat_id == chat_id,
        )
    )

    for game in ttt_result.scalars().all():
        await session.delete(game)

    # ------------------------------------------------------------------------
    # WARNINGS
    # ------------------------------------------------------------------------

    warnings_result = await session.execute(
        select(Warning).where(
            Warning.chat_id == chat_id,
        )
    )

    for warning in warnings_result.scalars().all():
        await session.delete(warning)

    # ------------------------------------------------------------------------
    # MODERATION ACTIONS
    # ------------------------------------------------------------------------

    moderation_result = await session.execute(
        select(ModerationAction).where(
            ModerationAction.chat_id == chat_id,
        )
    )

    for action in moderation_result.scalars().all():
        await session.delete(action)

    # ------------------------------------------------------------------------
    # ACHIEVEMENTS
    # ------------------------------------------------------------------------

    achievements_result = await session.execute(
        select(UserAchievement).where(
            UserAchievement.chat_id == chat_id,
        )
    )

    for achievement in achievements_result.scalars().all():
        await session.delete(achievement)

    # ------------------------------------------------------------------------
    # MEMBERS
    # ------------------------------------------------------------------------

    members_result = await session.execute(
        select(ChatMember).where(
            ChatMember.chat_id == chat_id,
        )
    )

    for member in members_result.scalars().all():
        await session.delete(member)

    # ------------------------------------------------------------------------
    # SETTINGS
    # ------------------------------------------------------------------------

    settings_result = await session.execute(
        select(ChatSettings).where(
            ChatSettings.chat_id == chat_id,
        )
    )

    settings = settings_result.scalar_one_or_none()

    if settings is not None:
        await session.delete(settings)

    # ------------------------------------------------------------------------
    # CHAT
    # ------------------------------------------------------------------------

    chat = await session.get(
        Chat,
        chat_id,
    )

    if chat is not None:
        await session.delete(chat)

    await session.flush()
