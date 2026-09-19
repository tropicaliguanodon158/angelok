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

import os
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
    inspect,
    select,
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


# ============================================================================
# TIME
# ============================================================================


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ============================================================================
# DATABASE URL
# ============================================================================


def get_database_url() -> str:
    value = os.getenv(
        "DATABASE_URL",
        "sqlite+aiosqlite:///./data/ezzzy.db",
    ).strip()

    if value.startswith("postgresql://"):
        value = value.replace(
            "postgresql://",
            "postgresql+asyncpg://",
            1,
        )

    if value.startswith("postgres://"):
        value = value.replace(
            "postgres://",
            "postgresql+asyncpg://",
            1,
        )

    return value


DATABASE_URL = get_database_url()

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
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
    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
    )

    title: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    chat_type: Mapped[str] = mapped_column(
        String(32),
        default="group",
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )

    settings: Mapped[Optional["ChatSettings"]] = relationship(
        back_populates="chat",
        uselist=False,
        cascade="all, delete-orphan",
    )

    members: Mapped[list["ChatMember"]] = relationship(
        back_populates="chat",
        cascade="all, delete-orphan",
    )


class ChatSettings(Base):
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
        index=True,
    )

    economy_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    games_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    rp_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    leveling_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    moderation_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    message_reward_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )

    chat: Mapped["Chat"] = relationship(
        back_populates="settings",
    )


# ============================================================================
# USER
# ============================================================================


class User(Base):
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

    first_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    last_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    is_bot: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )


# ============================================================================
# CHAT MEMBER
# ============================================================================


class ChatMember(Base):
    __tablename__ = "chat_members"

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
        String(32),
        nullable=True,
    )

    profile_tag: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
    )

    selected_tag_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("tags.id", ondelete="SET NULL"),
        nullable=True,
    )

    xp: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    level: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    battle_pass_xp: Mapped[int] = mapped_column(
        Integer,
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

    balance: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )

    messages: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    games_played: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    games_won: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    games_lost: Mapped[int] = mapped_column(
        Integer,
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

    penis_size: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

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

    last_rubber_daily_bonus_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
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
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )

    chat: Mapped["Chat"] = relationship(
        back_populates="members",
    )

    user: Mapped["User"] = relationship()

    selected_tag: Mapped[Optional["Tag"]] = relationship(
        foreign_keys=[selected_tag_id],
    )

    __table_args__ = (
        UniqueConstraint(
            "chat_id",
            "user_id",
            name="uq_chat_members_chat_user",
        ),
        Index(
            "ix_chat_members_messages",
            "chat_id",
            "messages",
        ),
        Index(
            "ix_chat_members_balance",
            "chat_id",
            "balance",
        ),
        Index(
            "ix_chat_members_xp",
            "chat_id",
            "xp",
        ),
        Index(
            "ix_chat_members_chat_size",
            "chat_id",
            "penis_size",
        ),
    )


# ============================================================================
# ECONOMY
# ============================================================================


class EconomyTransaction(Base):
    __tablename__ = "economy_transactions"

    id: Mapped[int] = mapped_column(
        Integer,
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
        index=True,
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        nullable=False,
    )


# ============================================================================
# GAMES
# ============================================================================


class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(
        Integer,
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
        String(32),
        nullable=False,
        index=True,
    )

    bet: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )

    result: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )

    multiplier: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )

    payout: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )

    won: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
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
        nullable=False,
    )

    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )


# ============================================================================
# TIC TAC TOE
# ============================================================================


class TicTacToeGame(Base):
    __tablename__ = "tictactoe_games"

    id: Mapped[int] = mapped_column(
        Integer,
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
        index=True,
    )

    player_o_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        index=True,
    )

    current_player_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
    )

    board: Mapped[str] = mapped_column(
        String(9),
        default="         ",
        nullable=False,
    )

    bet: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        default="waiting",
        nullable=False,
    )

    winner_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
    )

    message_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )


# ============================================================================
# MODERATION
# ============================================================================


class Warning(Base):
    __tablename__ = "warnings"

    id: Mapped[int] = mapped_column(
        Integer,
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
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        nullable=False,
    )

    removed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )


class ModerationAction(Base):
    __tablename__ = "moderation_actions"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    chat_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
    )

    moderator_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    target_user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
    )

    action: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )

    reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        nullable=False,
    )


class StaffMember(Base):
    __tablename__ = "staff_members"

    id: Mapped[int] = mapped_column(
        Integer,
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

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "chat_id",
            "user_id",
            name="uq_staff_members_chat_user",
        ),
    )


class ModPermission(Base):
    __tablename__ = "mod_permissions"

    id: Mapped[int] = mapped_column(
        Integer,
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

    required_role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    updated_by: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "chat_id",
            "command",
            name="uq_mod_permissions_chat_command",
        ),
    )


# ============================================================================
# ACHIEVEMENTS
# ============================================================================


class Achievement(Base):
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
        String(255),
        nullable=False,
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        nullable=False,
    )


class UserAchievement(Base):
    __tablename__ = "user_achievements"

    id: Mapped[int] = mapped_column(
        Integer,
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
        nullable=False,
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
# INVENTORY
# ============================================================================


class InventoryItem(Base):
    __tablename__ = "inventory_items"

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
        String(255),
        nullable=False,
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    item_type: Mapped[str] = mapped_column(
        String(32),
        default="item",
        nullable=False,
    )

    max_quantity: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    stackable: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    one_use: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        nullable=False,
    )


class UserItem(Base):
    __tablename__ = "user_items"

    id: Mapped[int] = mapped_column(
        Integer,
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
        Integer,
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
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )

    item: Mapped["InventoryItem"] = relationship()

    __table_args__ = (
        UniqueConstraint(
            "chat_id",
            "user_id",
            "item_id",
            name="uq_user_item",
        ),
    )


# ============================================================================
# TAGS
# ============================================================================


class Tag(Base):
    __tablename__ = "tags"

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
        String(255),
        nullable=False,
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        nullable=False,
    )


class UserTag(Base):
    __tablename__ = "user_tags"

    id: Mapped[int] = mapped_column(
        Integer,
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
        Integer,
        ForeignKey(
            "tags.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    earned_from: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
    )

    earned_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        nullable=False,
    )

    tag: Mapped["Tag"] = relationship()

    __table_args__ = (
        UniqueConstraint(
            "chat_id",
            "user_id",
            "tag_id",
            name="uq_user_tag",
        ),
    )


# ============================================================================
# BATTLE PASS
# ============================================================================


class BattlePassRewardClaim(Base):
    __tablename__ = "battle_pass_reward_claims"

    id: Mapped[int] = mapped_column(
        Integer,
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
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "chat_id",
            "user_id",
            "season",
            "level",
            name="uq_bp_reward_claim",
        ),
    )


# ============================================================================
# GIVEAWAYS
# ============================================================================


class Giveaway(Base):
    __tablename__ = "giveaways"

    id: Mapped[int] = mapped_column(
        Integer,
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

    prize_external: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    winners_count: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    ends_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        default="active",
        nullable=False,
    )

    winner_user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        nullable=False,
    )

    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )


class GiveawayParticipant(Base):
    __tablename__ = "giveaway_participants"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    giveaway_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "giveaways.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    joined_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "giveaway_id",
            "user_id",
            name="uq_giveaway_participant",
        ),
    )


# ============================================================================
# DATABASE HELPERS
# ============================================================================


async def get_or_create_chat(
    session: AsyncSession,
    chat_id: int,
    title: Optional[str] = None,
    chat_type: str = "group",
) -> Chat:
    chat = await session.get(Chat, chat_id)

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

        return chat

    changed = False

    if title is not None and chat.title != title:
        chat.title = title
        changed = True

    if chat_type and chat.chat_type != chat_type:
        chat.chat_type = chat_type
        changed = True

    if changed:
        chat.updated_at = utcnow()

    settings_result = await session.execute(
        select(ChatSettings).where(
            ChatSettings.chat_id == chat_id,
        )
    )

    if settings_result.scalar_one_or_none() is None:
        session.add(
            ChatSettings(
                chat_id=chat_id,
            )
        )
        await session.flush()

    return chat


async def get_or_create_user(
    session: AsyncSession,
    user_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    is_bot: bool = False,
) -> User:
    user = await session.get(User, user_id)

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
        return user

    changed = False

    if user.username != username:
        user.username = username
        changed = True

    if first_name is not None and user.first_name != first_name:
        user.first_name = first_name
        changed = True

    if last_name != user.last_name:
        user.last_name = last_name
        changed = True

    if user.is_bot != is_bot:
        user.is_bot = is_bot
        changed = True

    if changed:
        user.updated_at = utcnow()

    return user


async def get_or_create_member(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
) -> ChatMember:
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


async def get_staff_member(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
) -> Optional[StaffMember]:
    result = await session.execute(
        select(StaffMember).where(
            StaffMember.chat_id == chat_id,
            StaffMember.user_id == user_id,
            StaffMember.is_active.is_(True),
        )
    )

    return result.scalar_one_or_none()


async def get_staff_role(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
) -> Optional[str]:
    staff = await get_staff_member(
        session,
        chat_id,
        user_id,
    )

    return staff.role if staff else None


async def get_mod_permission(
    session: AsyncSession,
    chat_id: int,
    command: str,
) -> Optional[ModPermission]:
    result = await session.execute(
        select(ModPermission).where(
            ModPermission.chat_id == chat_id,
            ModPermission.command == command,
        )
    )

    return result.scalar_one_or_none()


async def get_inventory_item(
    session: AsyncSession,
    code: str,
) -> Optional[InventoryItem]:
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
    result = await session.execute(
        select(UserItem)
        .join(
            InventoryItem,
            UserItem.item_id == InventoryItem.id,
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
    result = await session.execute(
        select(UserItem)
        .where(
            UserItem.chat_id == chat_id,
            UserItem.user_id == user_id,
        )
        .order_by(UserItem.id.asc())
    )

    return list(result.scalars().all())


async def get_tag_by_code(
    session: AsyncSession,
    code: str,
) -> Optional[Tag]:
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
    result = await session.execute(
        select(UserTag)
        .where(
            UserTag.chat_id == chat_id,
            UserTag.user_id == user_id,
        )
        .order_by(UserTag.id.asc())
    )

    return list(result.scalars().all())


async def get_giveaway(
    session: AsyncSession,
    giveaway_id: int,
) -> Optional[Giveaway]:
    return await session.get(
        Giveaway,
        giveaway_id,
    )


async def get_giveaway_participants(
    session: AsyncSession,
    giveaway_id: int,
) -> list[GiveawayParticipant]:
    result = await session.execute(
        select(GiveawayParticipant).where(
            GiveawayParticipant.giveaway_id == giveaway_id,
        )
    )

    return list(result.scalars().all())


async def get_top_by_balance(
    session: AsyncSession,
    chat_id: int,
    limit: int = 10,
) -> list[ChatMember]:
    result = await session.execute(
        select(ChatMember)
        .where(ChatMember.chat_id == chat_id)
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
    result = await session.execute(
        select(ChatMember)
        .where(ChatMember.chat_id == chat_id)
        .order_by(
            ChatMember.xp.desc(),
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
    result = await session.execute(
        select(ChatMember)
        .where(ChatMember.chat_id == chat_id)
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
    result = await session.execute(
        select(ChatMember)
        .where(ChatMember.chat_id == chat_id)
        .order_by(
            ChatMember.penis_size.desc(),
            ChatMember.user_id.asc(),
        )
        .limit(limit)
    )

    return list(result.scalars().all())


async def get_member_rank_by_xp(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
) -> int:
    member = await get_or_create_member(
        session,
        chat_id,
        user_id,
    )

    result = await session.execute(
        select(ChatMember.id)
        .where(
            ChatMember.chat_id == chat_id,
            ChatMember.xp > member.xp,
        )
    )

    return len(result.scalars().all()) + 1


async def get_member_rank_by_balance(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
) -> int:
    member = await get_or_create_member(
        session,
        chat_id,
        user_id,
    )

    result = await session.execute(
        select(ChatMember.id)
        .where(
            ChatMember.chat_id == chat_id,
            ChatMember.balance > member.balance,
        )
    )

    return len(result.scalars().all()) + 1


async def get_member_rank_by_penis_size(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
) -> int:
    member = await get_or_create_member(
        session,
        chat_id,
        user_id,
    )

    result = await session.execute(
        select(ChatMember.id)
        .where(
            ChatMember.chat_id == chat_id,
            ChatMember.penis_size > member.penis_size,
        )
    )

    return len(result.scalars().all()) + 1


async def add_transaction(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    amount: int,
    balance_after: int,
    transaction_type: str,
    description: Optional[str] = None,
) -> EconomyTransaction:
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
# DATABASE INITIALIZATION
# ============================================================================


async def _column_names(
    connection,
    table_name: str,
) -> set[str]:
    result = await connection.execute(
        text(f"PRAGMA table_info({table_name})")
    )

    return {
        row[1]
        for row in result.fetchall()
    }


async def _sqlite_table_exists(
    connection,
    table_name: str,
) -> bool:
    result = await connection.execute(
        text(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name=:name"
        ),
        {"name": table_name},
    )

    return result.scalar_one_or_none() is not None


async def _postgres_table_exists(
    connection,
    table_name: str,
) -> bool:
    result = await connection.execute(
        text(
            "SELECT to_regclass(:name)"
        ),
        {"name": table_name},
    )

    return result.scalar_one_or_none() is not None


async def _add_column_if_missing(
    connection,
    table_name: str,
    column_name: str,
    definition: str,
) -> None:
    dialect = connection.dialect.name

    if dialect == "sqlite":
        if not await _sqlite_table_exists(
            connection,
            table_name,
        ):
            return

        columns = await _column_names(
            connection,
            table_name,
        )

        if column_name not in columns:
            await connection.execute(
                text(
                    f'ALTER TABLE "{table_name}" '
                    f'ADD COLUMN "{column_name}" {definition}'
                )
            )

        return

    if dialect == "postgresql":
        await connection.execute(
            text(
                f'ALTER TABLE "{table_name}" '
                f'ADD COLUMN IF NOT EXISTS '
                f'"{column_name}" {definition}'
            )
        )


async def _create_sqlite_index_if_missing(
    connection,
    index_name: str,
    table_name: str,
    columns: str,
) -> None:
    await connection.execute(
        text(
            f'CREATE INDEX IF NOT EXISTS "{index_name}" '
            f'ON "{table_name}" ({columns})'
        )
    )


async def _create_postgres_index_if_missing(
    connection,
    index_name: str,
    table_name: str,
    columns: str,
) -> None:
    await connection.execute(
        text(
            f'CREATE INDEX IF NOT EXISTS "{index_name}" '
            f'ON "{table_name}" ({columns})'
        )
    )


async def run_migrations(connection) -> None:
    """
    Добавляет новые колонки в уже существующую БД.

    Важно:
        сначала create_all() создаёт новые таблицы,
        затем сюда попадают старые таблицы.

    Индексы на новые колонки создаются ПОСЛЕ миграций.
    """

    dialect = connection.dialect.name

    if dialect == "sqlite":
        chat_members_exists = await _sqlite_table_exists(
            connection,
            "chat_members",
        )

        games_exists = await _sqlite_table_exists(
            connection,
            "games",
        )

        if chat_members_exists:
            await _add_column_if_missing(
                connection,
                "chat_members",
                "profile_nick",
                "VARCHAR(32)",
            )

            await _add_column_if_missing(
                connection,
                "chat_members",
                "profile_tag",
                "VARCHAR(32)",
            )

            await _add_column_if_missing(
                connection,
                "chat_members",
                "selected_tag_id",
                "INTEGER",
            )

            await _add_column_if_missing(
                connection,
                "chat_members",
                "battle_pass_xp",
                "INTEGER DEFAULT 0 NOT NULL",
            )

            await _add_column_if_missing(
                connection,
                "chat_members",
                "battle_pass_level",
                "INTEGER DEFAULT 1 NOT NULL",
            )

            await _add_column_if_missing(
                connection,
                "chat_members",
                "battle_pass_season",
                "INTEGER DEFAULT 1 NOT NULL",
            )

            await _add_column_if_missing(
                connection,
                "chat_members",
                "penis_size",
                "FLOAT DEFAULT 0 NOT NULL",
            )

            await _add_column_if_missing(
                connection,
                "chat_members",
                "has_disease",
                "BOOLEAN DEFAULT 0 NOT NULL",
            )

            await _add_column_if_missing(
                connection,
                "chat_members",
                "disease_since",
                "DATETIME",
            )

            await _add_column_if_missing(
                connection,
                "chat_members",
                "next_disease_tick",
                "DATETIME",
            )

            await _add_column_if_missing(
                connection,
                "chat_members",
                "has_child",
                "BOOLEAN DEFAULT 0 NOT NULL",
            )

            await _add_column_if_missing(
                connection,
                "chat_members",
                "child_until",
                "DATETIME",
            )

            await _add_column_if_missing(
                connection,
                "chat_members",
                "last_child_support",
                "DATETIME",
            )

            await _add_column_if_missing(
                connection,
                "chat_members",
                "last_adult_rp_at",
                "DATETIME",
            )

            await _add_column_if_missing(
                connection,
                "chat_members",
                "last_masturbation_at",
                "DATETIME",
            )

            await _add_column_if_missing(
                connection,
                "chat_members",
                "last_rob_at",
                "DATETIME",
            )

            await _add_column_if_missing(
                connection,
                "chat_members",
                "last_rubber_daily_bonus_at",
                "DATETIME",
            )

            await _add_column_if_missing(
                connection,
                "chat_members",
                "last_message_at",
                "DATETIME",
            )

            await _add_column_if_missing(
                connection,
                "chat_members",
                "last_bonus_at",
                "DATETIME",
            )

            await _create_sqlite_index_if_missing(
                connection,
                "ix_chat_members_chat_size",
                "chat_members",
                "chat_id, penis_size",
            )

            await _create_sqlite_index_if_missing(
                connection,
                "ix_chat_members_messages",
                "chat_members",
                "chat_id, messages",
            )

            await _create_sqlite_index_if_missing(
                connection,
                "ix_chat_members_balance",
                "chat_members",
                "chat_id, balance",
            )

            await _create_sqlite_index_if_missing(
                connection,
                "ix_chat_members_xp",
                "chat_members",
                "chat_id, xp",
            )

        if games_exists:
            await _add_column_if_missing(
                connection,
                "games",
                "player2_id",
                "BIGINT",
            )

            await _add_column_if_missing(
                connection,
                "games",
                "metadata_json",
                "TEXT",
            )

            await _add_column_if_missing(
                connection,
                "games",
                "finished_at",
                "DATETIME",
            )

            await _create_sqlite_index_if_missing(
                connection,
                "ix_games_player2_id",
                "games",
                "player2_id",
            )

    elif dialect == "postgresql":
        await _add_column_if_missing(
            connection,
            "chat_members",
            "profile_nick",
            "VARCHAR(32)",
        )

        await _add_column_if_missing(
            connection,
            "chat_members",
            "profile_tag",
            "VARCHAR(32)",
        )

        await _add_column_if_missing(
            connection,
            "chat_members",
            "selected_tag_id",
            "INTEGER",
        )

        await _add_column_if_missing(
            connection,
            "chat_members",
            "battle_pass_xp",
            "INTEGER DEFAULT 0 NOT NULL",
        )

        await _add_column_if_missing(
            connection,
            "chat_members",
            "battle_pass_level",
            "INTEGER DEFAULT 1 NOT NULL",
        )

        await _add_column_if_missing(
            connection,
            "chat_members",
            "battle_pass_season",
            "INTEGER DEFAULT 1 NOT NULL",
        )

        await _add_column_if_missing(
            connection,
            "chat_members",
            "penis_size",
            "DOUBLE PRECISION DEFAULT 0 NOT NULL",
        )

        await _add_column_if_missing(
            connection,
            "chat_members",
            "has_disease",
            "BOOLEAN DEFAULT FALSE NOT NULL",
        )

        await _add_column_if_missing(
            connection,
            "chat_members",
            "disease_since",
            "TIMESTAMP",
        )

        await _add_column_if_missing(
            connection,
            "chat_members",
            "next_disease_tick",
            "TIMESTAMP",
        )

        await _add_column_if_missing(
            connection,
            "chat_members",
            "has_child",
            "BOOLEAN DEFAULT FALSE NOT NULL",
        )

        await _add_column_if_missing(
            connection,
            "chat_members",
            "child_until",
            "TIMESTAMP",
        )

        await _add_column_if_missing(
            connection,
            "chat_members",
            "last_child_support",
            "TIMESTAMP",
        )

        await _add_column_if_missing(
            connection,
            "chat_members",
            "last_adult_rp_at",
            "TIMESTAMP",
        )

        await _add_column_if_missing(
            connection,
            "chat_members",
            "last_masturbation_at",
            "TIMESTAMP",
        )

        await _add_column_if_missing(
            connection,
            "chat_members",
            "last_rob_at",
            "TIMESTAMP",
        )

        await _add_column_if_missing(
            connection,
            "chat_members",
            "last_rubber_daily_bonus_at",
            "TIMESTAMP",
        )

        await _add_column_if_missing(
            connection,
            "chat_members",
            "last_message_at",
            "TIMESTAMP",
        )

        await _add_column_if_missing(
            connection,
            "chat_members",
            "last_bonus_at",
            "TIMESTAMP",
        )

        await _create_postgres_index_if_missing(
            connection,
            "ix_chat_members_chat_size",
            "chat_members",
            "chat_id, penis_size",
        )

        await _create_postgres_index_if_missing(
            connection,
            "ix_chat_members_messages",
            "chat_members",
            "chat_id, messages",
        )

        await _create_postgres_index_if_missing(
            connection,
            "ix_chat_members_balance",
            "chat_members",
            "chat_id, balance",
        )

        await _create_postgres_index_if_missing(
            connection,
            "ix_chat_members_xp",
            "chat_members",
            "chat_id, xp",
        )

        await _add_column_if_missing(
            connection,
            "games",
            "player2_id",
            "BIGINT",
        )

        await _add_column_if_missing(
            connection,
            "games",
            "metadata_json",
            "TEXT",
        )

        await _add_column_if_missing(
            connection,
            "games",
            "finished_at",
            "TIMESTAMP",
        )

        await _create_postgres_index_if_missing(
            connection,
            "ix_games_player2_id",
            "games",
            "player2_id",
        )


async def initialize_database() -> None:
    """
    Создаёт таблицы и затем выполняет совместимые миграции.
    """

    async with engine.begin() as connection:
        await connection.run_sync(
            Base.metadata.create_all
        )

        await run_migrations(connection)


async def close_database() -> None:
    await engine.dispose()


# ============================================================================
# DELETE CHAT DATA
# ============================================================================


async def delete_chat_data(
    session: AsyncSession,
    chat_id: int,
) -> None:
    """
    Удаляет игровые данные чата.

    Используется только административными процедурами.
    """

    tables = [
        GiveawayParticipant,
        Giveaway,
        BattlePassRewardClaim,
        UserTag,
        UserItem,
        UserAchievement,
        Warning,
        ModerationAction,
        ModPermission,
        StaffMember,
        TicTacToeGame,
        Game,
        EconomyTransaction,
        ChatMember,
        ChatSettings,
        Chat,
    ]

    for model in tables:
        if model is Chat:
            continue

        if hasattr(model, "chat_id"):
            await session.execute(
                model.__table__.delete().where(
                    model.chat_id == chat_id
                )
            )

    await session.execute(
        Chat.__table__.delete().where(
            Chat.id == chat_id
        )
    )

    await session.flush()