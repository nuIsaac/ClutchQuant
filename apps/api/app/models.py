from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    vlr_id: Mapped[int | None] = mapped_column(unique=True)

    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )

    abbreviation: Mapped[str | None] = mapped_column(String(10))
    region: Mapped[str | None] = mapped_column(String(50))


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True)
    vlr_id: Mapped[int | None] = mapped_column(unique=True)

    handle: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    real_name: Mapped[str | None] = mapped_column(String(150))
    country: Mapped[str | None] = mapped_column(String(50))


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    vlr_id: Mapped[int | None] = mapped_column(unique=True)

    team1_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id"),
        nullable=False,
    )

    team2_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id"),
        nullable=False,
    )

    team1_score: Mapped[int | None] = mapped_column()
    team2_score: Mapped[int | None] = mapped_column()

    event_name: Mapped[str | None] = mapped_column(String(150))
    stage: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str | None] = mapped_column(String(30))

    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )


class MatchMap(Base):
    __tablename__ = "match_maps"

    id: Mapped[int] = mapped_column(primary_key=True)

    vlr_game_id: Mapped[int] = mapped_column(
        unique=True,
        nullable=False,
    )

    match_id: Mapped[int] = mapped_column(
        ForeignKey("matches.id"),
        nullable=False,
    )

    map_number: Mapped[int] = mapped_column(nullable=False)

    map_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    team1_score: Mapped[int | None] = mapped_column()
    team2_score: Mapped[int | None] = mapped_column()

    duration_seconds: Mapped[int | None] = mapped_column()


class PlayerMapStat(Base):
    __tablename__ = "player_map_stats"

    __table_args__ = (
        UniqueConstraint(
            "match_map_id",
            "player_id",
            name="uq_player_map_stats_map_player",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    match_map_id: Mapped[int] = mapped_column(
        ForeignKey("match_maps.id"),
        nullable=False,
    )

    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id"),
        nullable=False,
    )

    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id"),
        nullable=False,
    )

    agents: Mapped[str | None] = mapped_column(String(100))

    rating_all: Mapped[float | None] = mapped_column(Float)
    rating_attack: Mapped[float | None] = mapped_column(Float)
    rating_defense: Mapped[float | None] = mapped_column(Float)

    acs_all: Mapped[int | None] = mapped_column()
    acs_attack: Mapped[int | None] = mapped_column()
    acs_defense: Mapped[int | None] = mapped_column()

    kills_all: Mapped[int | None] = mapped_column()
    kills_attack: Mapped[int | None] = mapped_column()
    kills_defense: Mapped[int | None] = mapped_column()

    deaths_all: Mapped[int | None] = mapped_column()
    deaths_attack: Mapped[int | None] = mapped_column()
    deaths_defense: Mapped[int | None] = mapped_column()

    assists_all: Mapped[int | None] = mapped_column()
    assists_attack: Mapped[int | None] = mapped_column()
    assists_defense: Mapped[int | None] = mapped_column()

    kill_diff_all: Mapped[int | None] = mapped_column()
    kill_diff_attack: Mapped[int | None] = mapped_column()
    kill_diff_defense: Mapped[int | None] = mapped_column()

    kast_all: Mapped[float | None] = mapped_column(Float)
    kast_attack: Mapped[float | None] = mapped_column(Float)
    kast_defense: Mapped[float | None] = mapped_column(Float)

    adr_all: Mapped[float | None] = mapped_column(Float)
    adr_attack: Mapped[float | None] = mapped_column(Float)
    adr_defense: Mapped[float | None] = mapped_column(Float)

    hs_pct_all: Mapped[float | None] = mapped_column(Float)
    hs_pct_attack: Mapped[float | None] = mapped_column(Float)
    hs_pct_defense: Mapped[float | None] = mapped_column(Float)

    first_kills_all: Mapped[int | None] = mapped_column()
    first_kills_attack: Mapped[int | None] = mapped_column()
    first_kills_defense: Mapped[int | None] = mapped_column()

    first_deaths_all: Mapped[int | None] = mapped_column()
    first_deaths_attack: Mapped[int | None] = mapped_column()
    first_deaths_defense: Mapped[int | None] = mapped_column()

    first_kill_diff_all: Mapped[int | None] = mapped_column()
    first_kill_diff_attack: Mapped[int | None] = mapped_column()
    first_kill_diff_defense: Mapped[int | None] = mapped_column()