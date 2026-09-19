"""
Lottery draft — the draft format the game actually wants.

The existing `draft/engine.py` offers snake, auction and salary-cap drafts, in
all of which a manager picks freely from the whole pool. This is a different
format and lives in its own module so none of those are disturbed:

    for each of 11 rounds:
        a club is drawn at random from the clubs still holding players
        the manager picks ONE player from THAT club's remaining roster
        that player, and optionally that club, is then unavailable

You do not choose the club. You choose inside it. That is the whole point:
the squad you end up with is a negotiation between luck and judgement, not a
shopping list.

This module is pure orchestration over ids and a seeded RNG - it contains no
football mathematics and never touches the simulation. The core is
deliberately written against plain data structures so it is testable without
pydantic or the data layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Optional, Sequence

SQUAD_SIZE = 11


class ClubReuse(Enum):
    """What happens to a club after you have taken a player from it."""

    ALLOW = "allow"          # the club can be drawn again
    ONCE = "once"            # one player per club, maximum
    UNTIL_EXHAUSTED = "until_exhausted"  # redrawable until its roster runs out


class DraftError(RuntimeError):
    """The draft was asked to do something its current state does not allow."""


@dataclass(frozen=True)
class LotteryPick:
    round_number: int
    club_id: str
    club_name: str
    player_id: str


@dataclass
class LotteryDraft:
    """
    One manager, eleven rounds, one drawn club per round.

    `clubs` maps club_id -> (display name, roster of player ids). The RNG must
    expose `randrange(n)`; `SeededRNG` and `random.Random` both do, so the same
    draft replays identically from the same seed.
    """

    clubs: dict[str, tuple[str, list[str]]]
    rng: object
    reuse: ClubReuse = ClubReuse.UNTIL_EXHAUSTED
    rounds: int = SQUAD_SIZE

    picks: list[LotteryPick] = field(default_factory=list)
    taken_players: set[str] = field(default_factory=set)
    used_clubs: set[str] = field(default_factory=set)
    current_club: Optional[str] = None

    # -- state -------------------------------------------------------------

    @property
    def round_number(self) -> int:
        return len(self.picks) + 1

    @property
    def complete(self) -> bool:
        return len(self.picks) >= self.rounds

    def available_clubs(self) -> list[str]:
        """Clubs that can still be drawn, in stable order."""
        out = []
        for club_id, (_, roster) in sorted(self.clubs.items()):
            if self.reuse is ClubReuse.ONCE and club_id in self.used_clubs:
                continue
            if any(pid not in self.taken_players for pid in roster):
                out.append(club_id)
        return out

    def options(self) -> list[str]:
        """Players you may pick this round - the drawn club's remaining roster."""
        if self.current_club is None:
            raise DraftError("no club has been drawn for this round yet")
        _, roster = self.clubs[self.current_club]
        return [pid for pid in roster if pid not in self.taken_players]

    # -- actions -----------------------------------------------------------

    def draw_club(self) -> str:
        """Draw this round's club. Idempotent within a round."""
        if self.complete:
            raise DraftError("the draft is already complete")
        if self.current_club is not None:
            return self.current_club
        pool = self.available_clubs()
        if not pool:
            raise DraftError("no club has any player left to offer")
        self.current_club = pool[int(self.rng.randrange(len(pool)))]
        return self.current_club

    def pick(self, player_id: str) -> LotteryPick:
        """Take one player from the club drawn this round."""
        if self.current_club is None:
            raise DraftError("draw a club before picking")
        if player_id not in self.options():
            raise DraftError(f"{player_id!r} is not available from the drawn club")

        club_id = self.current_club
        name, _ = self.clubs[club_id]
        entry = LotteryPick(
            round_number=self.round_number,
            club_id=club_id,
            club_name=name,
            player_id=player_id,
        )
        self.picks.append(entry)
        self.taken_players.add(player_id)
        self.used_clubs.add(club_id)
        self.current_club = None
        return entry

    def auto_pick(self, prefer_roles: Optional[Sequence[str]] = None,
                  roles_by_player: Optional[dict[str, str]] = None) -> LotteryPick:
        """
        Deterministic fallback pick, used for a skipped turn or an AI manager.

        If `prefer_roles` and `roles_by_player` are given, the first candidate
        matching the earliest-listed role wins; otherwise the first option in
        stable order is taken. No quality judgement is made here - ranking
        players is a game-design decision, not a draft-mechanics one.
        """
        options = self.options()
        if not options:
            raise DraftError("the drawn club has no player left to take")
        if prefer_roles and roles_by_player:
            for role in prefer_roles:
                for pid in options:
                    if roles_by_player.get(pid) == role:
                        return self.pick(pid)
        return self.pick(options[0])

    def squad(self) -> list[str]:
        return [p.player_id for p in self.picks]

    def state(self) -> dict:
        """Serializable snapshot - the API returns this verbatim."""
        return {
            "round": min(self.round_number, self.rounds),
            "rounds": self.rounds,
            "complete": self.complete,
            "current_club": self.current_club,
            "picks": [
                {
                    "round": p.round_number,
                    "club_id": p.club_id,
                    "club_name": p.club_name,
                    "player_id": p.player_id,
                }
                for p in self.picks
            ],
            "squad": self.squad(),
        }


def missing_roles(roles: Iterable[str]) -> list[str]:
    """
    Which of the essentials a squad still lacks. Advisory only - the draft
    never blocks a pick over it, because a squad with no keeper is a legal
    squad whose consequences the engine is perfectly able to produce.
    """
    have = set(roles)
    wanted = []
    if "GK" not in have:
        wanted.append("GK")
    if not have & {"CB", "FB"}:
        wanted.append("defender")
    if not have & {"DM", "CM", "AM", "WM"}:
        wanted.append("midfielder")
    if not have & {"FW", "WM"}:
        wanted.append("forward")
    return wanted
