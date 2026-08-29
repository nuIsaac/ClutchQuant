from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
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