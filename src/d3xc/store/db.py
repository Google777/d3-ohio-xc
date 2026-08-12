"""Normalized SQLite schema (SQLAlchemy 2.0 ORM) + engine/session helpers."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import (
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)

from d3xc import config


class Base(DeclarativeBase):
    pass


class Team(Base):
    __tablename__ = "teams"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    conference: Mapped[str] = mapped_column(String, index=True)
    tracked: Mapped[bool] = mapped_column(default=True, index=True)

    athletes: Mapped[list["Athlete"]] = relationship(back_populates="team")
    coaches: Mapped[list["CoachTenure"]] = relationship(back_populates="team")


class CoachTenure(Base):
    __tablename__ = "coach_tenures"
    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    gender: Mapped[str] = mapped_column(String, default="both")  # m|f|both
    coach_name: Mapped[str] = mapped_column(String)
    start_year: Mapped[int] = mapped_column(Integer)
    end_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    team: Mapped[Team] = relationship(back_populates="coaches")


class Athlete(Base):
    __tablename__ = "athletes"
    __table_args__ = (
        UniqueConstraint("name", "team_id", "gender", name="uq_athlete_identity"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    tfrrs_athlete_id: Mapped[Optional[str]] = mapped_column(
        String, nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String, index=True)
    gender: Mapped[str] = mapped_column(String, index=True)  # men|women
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    hometown: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    high_school: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    home_state: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)

    team: Mapped[Team] = relationship(back_populates="athletes")
    results: Mapped[list["Result"]] = relationship(back_populates="athlete")
    hs_marks: Mapped[list["HSMarkRow"]] = relationship(back_populates="athlete")


class Result(Base):
    __tablename__ = "results"
    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"), index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    gender: Mapped[str] = mapped_column(String, index=True)
    season: Mapped[int] = mapped_column(Integer, index=True)
    meet_name: Mapped[str] = mapped_column(String)
    meet_date: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    distance_m: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mark_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    place_overall: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    athlete: Mapped[Athlete] = relationship(back_populates="results")


class TeamPlacement(Base):
    """A team's finish at a specific meet (conference/regional/national/etc.)."""
    __tablename__ = "team_placements"
    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    gender: Mapped[str] = mapped_column(String, index=True)
    season: Mapped[int] = mapped_column(Integer, index=True)
    meet_name: Mapped[str] = mapped_column(String)
    meet_kind: Mapped[str] = mapped_column(String, index=True, default="invitational")
    team_place: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    team_points: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class HSMarkRow(Base):
    __tablename__ = "hs_marks"
    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("athletes.id"), nullable=True, index=True
    )
    athlete_name: Mapped[str] = mapped_column(String, index=True)
    college_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    gender: Mapped[str] = mapped_column(String)
    event: Mapped[str] = mapped_column(String)
    mark_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    hs_grad_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String)
    match_confidence: Mapped[float] = mapped_column(Float, default=0.0)

    athlete: Mapped[Optional[Athlete]] = relationship(back_populates="hs_marks")


# --------------------------------------------------------------------------
# engine / session
# --------------------------------------------------------------------------
def get_engine(db_path=None, echo: bool = False):
    config.ensure_dirs()
    path = db_path or config.DB_PATH
    return create_engine(f"sqlite:///{path}", echo=echo, future=True)


def get_sessionmaker(engine=None):
    engine = engine or get_engine()
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)


def init_db(engine=None, drop: bool = False):
    engine = engine or get_engine()
    if drop:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    return engine
